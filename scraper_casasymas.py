#!/usr/bin/env python3
"""
Scraper de Casasymas.com.uy (Montevideo, venta + alquiler), via Playwright.

20/7/2026: hasta ahora este scraper aplicaba el filtro "Departamento =
Montevideo" con clicks reales (simulando a una persona) y despues clickeaba
la flecha de "pagina siguiente" varias veces. Ese click de paginacion fallaba
de forma intermitente (paginas devolviendo 0 avisos sin motivo aparente,
sobre todo la 2da-3ra pagina), probablemente porque la tarjeta todavia no
habia terminado de re-renderizarse cuando leiamos el DOM.

Investigando en vivo encontre que el sitio en realidad SI tiene una URL
real por pagina (aunque no lo parecia navegando con clicks): por ejemplo
https://www.casasymas.com.uy/propiedades/venta/montevideo/pagina-3 carga
directo, con el filtro de Montevideo ya aplicado por el propio path de la
URL. Es mucho mas simple y confiable navegar directo a esa URL en cada
pagina (igual que se hace con InfoCasas y Gallito) que simular clicks de
paginacion -- asi que este scraper ya no aplica ningun filtro por click,
solo visita cada URL de pagina directamente.

Uso:
    python scraper_casasymas.py --out data/raw_casasymas.csv --paginas 5
"""
import argparse
import csv
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

BASE = {
    "venta": "https://www.casasymas.com.uy/propiedades/venta/montevideo",
    "alquiler": "https://www.casasymas.com.uy/propiedades/alquiler/montevideo",
}

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['es-UY', 'es'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = window.chrome || { runtime: {} };
"""

DOMINIOS_BLOQUEADOS = (
    "doubleclick.net", "googlesyndication.com", "googletagmanager.com",
    "google-analytics.com", "analytics.google.com", "cxense.com",
    "facebook.net", "facebook.com", "connect.facebook.net",
)


def bloquear_recursos_innecesarios(route):
    req = route.request
    if req.resource_type in ("image", "media", "font"):
        return route.abort()
    if any(dominio in req.url for dominio in DOMINIOS_BLOQUEADOS):
        return route.abort()
    return route.continue_()


TIPOS = ["Apartamento", "Casa", "Oficina", "Local Comercial", "Local", "Terreno",
         "Garage", "Chacra", "Edificio", "Galpón", "Piso", "Pieza", "Cochera",
         "Depósito"]


def page_url(base, n):
    """Pagina 1 es la URL base; de ahi en mas se agrega /pagina-N."""
    return base if n == 1 else f"{base}/pagina-{n}"


def extract_casasymas_cards(page):
    """Lee las tarjetas de la pagina actual. Devuelve una lista de dicts con
    los campos crudos tal como aparecen en el DOM (sin parsear precio/tipo
    todavia -- eso se hace en Python, es mas facil de ajustar despues)."""
    return page.evaluate(
        """
        () => {
            function clean(u) { return u ? u.split('?')[0].split('#')[0] : ''; }
            const arts = Array.from(document.querySelectorAll('article'));
            return arts.map(a => {
                const linkEl = a.querySelector('a[href*="/propiedad/"]') || a.querySelector('a');
                const href = linkEl ? clean(linkEl.href) : '';
                const heading = a.querySelector('h1, h2, h3, h4');
                const titulo = heading ? heading.textContent.trim() : '';

                let dormitorios = '', banos = '', m2 = '';
                const list = a.querySelector('ul, ol');
                if (list) {
                    Array.from(list.children).forEach(li => {
                        const img = li.querySelector('img');
                        const alt = img ? (img.getAttribute('alt') || '') : '';
                        const text = li.textContent.trim();
                        if (alt === 'Dormitorios') dormitorios = text;
                        else if (alt === 'Baños' || alt === 'Banos') banos = text;
                        else if (text.includes('m²') && !m2) m2 = text;
                    });
                }

                const leafTexts = Array.from(a.querySelectorAll('*'))
                    .filter(el => el.children.length === 0 && el.textContent.trim())
                    .map(el => el.textContent.trim());

                return { href, titulo, dormitorios, banos, m2, leafTexts };
            });
        }
        """
    )


def parse_casasymas_items(items, operacion):
    """Convierte lo leido del DOM en filas con nuestro esquema comun.
    Nota sobre 'operacion': una misma tarjeta puede mostrar precio de Venta
    Y de Alquiler a la vez (son propiedades que se ofrecen para ambas). Solo
    tomamos el precio que corresponde a la operacion que estamos scrapeando
    en este momento (Venta o Alquiler); si esa operacion no tiene precio en
    esta tarjeta, se omite (no aplica a esta lista)."""
    rows = []
    for it in items:
        href = it.get("href") or ""
        if not href:
            continue
        leaf = it.get("leafTexts") or []
        titulo = it.get("titulo") or ""

        # precio: en el DOM aparece como un texto tipo "U$S 123.000" / "$U 123.000"
        # (o "Consultar" si no hay precio publicado) seguido INMEDIATAMENTE por
        # la etiqueta "Venta" o "Alquiler" a la que corresponde. Buscamos ese
        # par (precio, etiqueta) que coincida con la operacion actual.
        precio_valor, precio_moneda = "", ""
        encontrada = False
        for i in range(len(leaf) - 1):
            t, lbl = leaf[i], leaf[i + 1]
            es_precio = bool(re.match(r"^(U\$S|US\$|\$U|\$)\s?[\d.,]+$", t)) or t.strip() == "Consultar"
            if not es_precio or lbl.strip().lower() != operacion:
                continue
            encontrada = True
            if t.strip() != "Consultar":
                if "U$S" in t or "US$" in t:
                    precio_moneda = "USD"
                elif "$U" in t:
                    precio_moneda = "UYU"
                precio_valor = re.sub(r"[^\d]", "", t)
            break

        if not encontrada:
            # esta tarjeta no ofrece la operacion que estamos scrapeando ahora mismo
            continue

        gastos = ""

        gc_match = next((t for t in leaf if t.startswith("G.C.")), "")
        if gc_match:
            gastos = re.sub(r"[^\d]", "", gc_match)

        # tipo + zona: suelen ser las dos lineas de texto cortas que no son
        # precio/etiqueta/gastos/numero suelto, ubicadas despues del titulo
        candidatos = [
            t for t in leaf
            if t != titulo
            and not re.match(r"^(U\$S|US\$|\$U|\$)\s?[\d.,]+$", t)
            and t not in ("Venta", "Alquiler", "Consultar", "Destacada")
            and not t.startswith("G.C.")
            and not re.match(r"^\d+([.,]\d+)?\s?m?²?$", t)
        ]
        tipo, zona = "", ""
        for t in TIPOS:
            if any(t.lower() == c.lower() for c in candidatos):
                tipo = t
                break
        # zona: el primer candidato que no sea el tipo encontrado
        zona_candidatos = [c for c in candidatos if c.lower() != tipo.lower()]
        zona = zona_candidatos[0] if zona_candidatos else ""

        m2_raw = it.get("m2") or ""
        m2 = re.sub(r"[^\d.,]", "", m2_raw).replace(",", ".") if m2_raw else ""

        rows.append({
            "portal": "Casasymas",
            "operacion": operacion,
            # el mismo aviso puede aparecer tanto en venta como en alquiler
            # (con precios distintos); se distingue con #<operacion> para
            # no perder ninguna de las dos filas al deduplicar por url,
            # el link sigue funcionando igual (el fragmento se ignora).
            "url": f"{href}#{operacion}",
            "titulo": titulo,
            "tipo_inmueble": tipo,
            "barrio": zona,
            "precio_moneda": precio_moneda,
            "precio_valor": precio_valor,
            "gastos_comunes": gastos,
            "dormitorios": re.sub(r"\D", "", it.get("dormitorios") or ""),
            "banos": re.sub(r"\D", "", it.get("banos") or ""),
            "m2": m2,
        })
    # dedup por url dentro de esta tanda
    dedup = {}
    for r in rows:
        dedup[r["url"]] = r
    return list(dedup.values())


def _nuevo_contexto(browser):
    context = browser.new_context(
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        locale="es-UY",
        viewport={"width": 1366, "height": 900},
        extra_http_headers={"Accept-Language": "es-UY,es;q=0.9,en;q=0.8"},
    )
    context.add_init_script(STEALTH_JS)
    context.route("**/*", bloquear_recursos_innecesarios)
    return context


def cargar_pagina_casasymas(page, url, intentos=2):
    """Navega directo a la URL de una pagina especifica y espera a que
    aparezcan las tarjetas. Reintenta si la primera pasada falla."""
    for intento in range(1, intentos + 1):
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector("article", timeout=20000, state="attached")
            time.sleep(1)
            return True
        except Exception as e:
            print(f"  [warn] intento {intento}/{intentos} {url} -> {e}", file=sys.stderr)
            if intento < intentos:
                time.sleep(3)
    return False


def cargar_casasymas(browser, operacion, paginas=5):
    context = _nuevo_contexto(browser)
    page = context.new_page()
    rows = []
    try:
        for n in range(1, paginas + 1):
            url = page_url(BASE[operacion], n)
            if not cargar_pagina_casasymas(page, url):
                print(f"    pagina {n}: no se pudo cargar, se omite ({operacion})", file=sys.stderr)
                continue
            items = extract_casasymas_cards(page)
            page_rows = parse_casasymas_items(items, operacion)
            print(f"    pagina {n}: {len(page_rows)} avisos ({operacion})", file=sys.stderr)
            rows.extend(page_rows)
            time.sleep(1.5)
    finally:
        context.close()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--paginas", type=int, default=5)
    args = ap.parse_args()

    all_rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"],
        )
        for operacion in ("venta", "alquiler"):
            print(f"Casasymas {operacion}...", file=sys.stderr)
            all_rows.extend(cargar_casasymas(browser, operacion, paginas=args.paginas))
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
