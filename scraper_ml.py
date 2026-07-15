#!/usr/bin/env python3
"""
Scraper de MercadoLibre (Uruguay) para Montevideo, vía Playwright headless.
MercadoLibre bloquea requests simples (anti-bot), por eso usa un navegador real.

Uso:
    python scraper_ml.py --out data/raw_mercadolibre.csv --paginas 3
"""
import argparse
import csv
import hashlib
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

BASE = {
    "venta": "https://listado.mercadolibre.com.uy/inmuebles/venta/montevideo/",
    "alquiler": "https://listado.mercadolibre.com.uy/inmuebles/alquiler/montevideo/",
}

# se ejecuta en el navegador antes de que cargue cualquier pagina: intenta
# ocultar las señales mas obvias de que es un navegador automatizado
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['es-UY', 'es'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = window.chrome || { runtime: {} };
"""

# Dominios de publicidad/analytics que suelen frenar la carga de paginas
# pesadas: son requests sincronicos que a veces tardan muchisimo (o nunca
# resuelven) y hacen que el navegador quede "cargando" por muchos segundos.
# Bloquearlos no afecta los datos que leemos (son solo texto/HTML), pero
# acelera la carga y evita esos cuelgues.
DOMINIOS_BLOQUEADOS = (
    "doubleclick.net", "googlesyndication.com", "googletagmanager.com",
    "google-analytics.com", "cxense.com", "facebook.net", "facebook.com",
)


def bloquear_recursos_innecesarios(route):
    """Aborta imagenes/fuentes/medios y scripts de ads/analytics conocidos."""
    req = route.request
    if req.resource_type in ("image", "media", "font"):
        return route.abort()
    if any(dominio in req.url for dominio in DOMINIOS_BLOQUEADOS):
        return route.abort()
    return route.continue_()


def page_url(base, n):
    if n == 1:
        return base
    offset = (n - 1) * 48 + 1
    return f"{base}_Desde_{offset}_NoIndex_True"


def extract(page):
    """Extrae los avisos visibles en la pagina actual usando el DOM."""
    return page.evaluate(
        """
        () => {
            function clean(u) { return u ? u.split('?')[0].split('#')[0] : ''; }
            function realUrl(c, titleEl) {
                // 1) href directo en el elemento de titulo
                if (titleEl) {
                    const direct = titleEl.getAttribute('href');
                    if (direct) return direct;
                    // 2) el titulo puede estar dentro de un <a> padre
                    const wrapA = titleEl.closest('a[href]');
                    if (wrapA) return wrapA.getAttribute('href');
                }
                // 3) cualquier <a> de la tarjeta que apunte a una publicacion real
                const anchors = Array.from(c.querySelectorAll('a[href]'));
                const real = anchors.find(a => /MLU-\\d+|articulo\\.mercadolibre|casa\\.mercadolibre|inmuebles\\.mercadolibre/i.test(a.getAttribute('href') || ''));
                if (real) return real.getAttribute('href');
                // 4) ultimo recurso: el primer link de la tarjeta
                if (anchors.length) return anchors[0].getAttribute('href');
                return '';
            }
            const cards = document.querySelectorAll('.ui-search-layout__item');
            const out = [];
            cards.forEach(c => {
                const titleEl = c.querySelector('.poly-component__title');
                const title = titleEl ? titleEl.textContent.trim() : '';
                const url = clean(realUrl(c, titleEl));
                const priceEl = c.querySelector('.poly-price__current .andes-money-amount__fraction');
                const currEl = c.querySelector('.poly-price__current .andes-money-amount__currency-symbol');
                const attrs = Array.from(c.querySelectorAll('.poly-attributes_list__item')).map(a => a.textContent.trim());
                const loc = c.querySelector('.poly-component__location');
                const isProject = c.textContent.includes('PROYECTO');
                out.push({
                    title, url,
                    price: priceEl ? priceEl.textContent.trim() : '',
                    currency: currEl ? currEl.textContent.trim() : '',
                    attrs: attrs.join(' / '),
                    loc: loc ? loc.textContent.trim() : '',
                    isProject
                });
            });
            return out;
        }
        """
    )


def parse_attrs(attrs):
    dorm, banos, m2 = "", "", ""
    m = re.search(r"(\d+)\s*a?\s*\d*\s*dormitorio", attrs, re.I)
    if m:
        dorm = m.group(1)
    elif "mono" in attrs.lower():
        dorm = "0"
    m = re.search(r"(\d+)\s*a?\s*\d*\s*baño", attrs, re.I)
    if m:
        banos = m.group(1)
    m = re.search(r"([\d.,]+)\s*m²", attrs)
    if m:
        m2 = m.group(1).replace(".", "").replace(",", ".")
    return dorm, banos, m2


def guess_tipo(title):
    for t in ["Apartamento", "Casa", "Oficina", "Local", "Terreno", "Depósito", "Cochera"]:
        if t.lower() in title.lower():
            return t
    return ""


def fallback_id(it):
    """ID estable (no es un link real) para avisos donde no se pudo extraer la URL.
    Se usa como clave interna para el diff nuevo/mantenido; el sitio no lo muestra
    como link clickeable porque no empieza con http."""
    basis = f"{it['title']}|{it['loc']}|{it['price']}"
    h = hashlib.md5(basis.encode("utf-8")).hexdigest()[:12]
    return f"mercadolibre-sin-link-{h}"


def diagnosticar_bloqueo(page, url):
    """Cuando falla la espera del selector, deja pistas en el log sobre si
    el sitio mostro un captcha/bloqueo o simplemente tardo demasiado, para
    poder diagnosticar sin tener que reproducirlo a mano."""
    try:
        title = page.title()
        body_snippet = page.evaluate("document.body ? document.body.innerText.slice(0, 200) : ''")
        print(f"  [diag] {url} -> title={title!r}", file=sys.stderr)
        print(f"  [diag] primeros 200 caracteres del body: {body_snippet!r}", file=sys.stderr)
    except Exception as e:
        print(f"  [diag] no se pudo inspeccionar la pagina: {e}", file=sys.stderr)


def cargar_pagina_ml(page, url, intentos=2):
    """Navega a una pagina de MercadoLibre y espera a que aparezcan las
    tarjetas. Reintenta una vez mas si la primera pasada falla, antes de
    darse por vencido."""
    for intento in range(1, intentos + 1):
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector(".ui-search-layout__item", timeout=20000)
            return True
        except Exception as e:
            print(f"  [warn] intento {intento}/{intentos} {url} -> {e}", file=sys.stderr)
            if intento < intentos:
                time.sleep(3)
            else:
                diagnosticar_bloqueo(page, url)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--paginas", type=int, default=3)
    args = ap.parse_args()

    all_rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            locale="es-UY",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={
                "Accept-Language": "es-UY,es;q=0.9,en;q=0.8",
            },
        )
        context.add_init_script(STEALTH_JS)
        context.route("**/*", bloquear_recursos_innecesarios)
        page = context.new_page()

        for operacion, base in BASE.items():
            for n in range(1, args.paginas + 1):
                url = page_url(base, n)
                print(f"  fetching {url}", file=sys.stderr)
                if not cargar_pagina_ml(page, url):
                    continue
                items = extract(page)
                print(f"    -> {len(items)} avisos", file=sys.stderr)
                for it in items:
                    dorm, banos, m2 = parse_attrs(it["attrs"])
                    barrio = it["loc"].split(",")[-2].strip() if it["loc"].count(",") >= 1 else it["loc"]
                    all_rows.append({
                        "portal": "MercadoLibre",
                        "operacion": operacion,
                        "url": it["url"] or fallback_id(it),
                        "titulo": it["title"],
                        "tipo_inmueble": "Proyecto" if it["isProject"] else guess_tipo(it["title"]),
                        "barrio": barrio,
                        "precio_moneda": "USD" if "US$" in it["currency"] else "UYU",
                        "precio_valor": it["price"].replace(".", ""),
                        "gastos_comunes": "",
                        "dormitorios": dorm,
                        "banos": banos,
                        "m2": m2,
                    })
                time.sleep(2)
        browser.close()

    dedup = {}
    for r in all_rows:
        dedup[r["url"]] = r
    all_rows = list(dedup.values())

    cols = ["portal", "operacion", "url", "titulo", "tipo_inmueble", "barrio",
            "precio_moneda", "precio_valor", "gastos_comunes", "dormitorios", "banos", "m2"]
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in all_rows:
            w.writerow(r)
    print(f"TOTAL: {len(all_rows)} avisos -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
