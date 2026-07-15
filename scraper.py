#!/usr/bin/env python3
"""
Scraper de InfoCasas y Gallito para Montevideo (venta + alquiler).

InfoCasas se descarga con pedidos HTTP normales (requests).
Gallito bloquea los pedidos HTTP normales (error 403 con Cloudflare, tanto
desde servidores de GitHub como desde una conexion residencial), asi que se
descarga con un navegador real headless (Playwright), igual que MercadoLibre.

Uso:
    python scraper.py --out data/raw_infocasas_gallito.csv --paginas 5
"""
import argparse
import csv
import os
import random
import re
import sys
import time

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-UY,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# se ejecuta en el navegador antes de que cargue cualquier pagina: intenta
# ocultar las señales mas obvias de que es un navegador automatizado
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['es-UY', 'es'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = window.chrome || { runtime: {} };
"""

# Dominios de publicidad/analytics que suelen frenar la carga de paginas ASP.NET
# clasicas como Gallito: son requests sincronicos que a veces tardan muchisimo
# (o directamente nunca resuelven) y hacen que el navegador quede "cargando"
# durante 45+ segundos. Bloquearlos no afecta los datos que leemos (son solo
# texto/HTML), pero acelera la carga y evita esos cuelgues.
DOMINIOS_BLOQUEADOS = (
    "doubleclick.net", "googlesyndication.com", "googletagmanager.com",
    "google-analytics.com", "cxense.com", "facebook.net", "facebook.com",
)


def bloquear_recursos_innecesarios(route):
    """Aborta imagenes/fuentes/medios y scripts de ads/analytics conocidos.
    Se usa con context.route('**/*', ...) tanto para Gallito como para
    cualquier otra pagina pesada que carguemos con Playwright."""
    req = route.request
    if req.resource_type in ("image", "media", "font"):
        return route.abort()
    if any(dominio in req.url for dominio in DOMINIOS_BLOQUEADOS):
        return route.abort()
    return route.continue_()


TIPOS = ["Apartamento", "Casa", "Oficina", "Local Comercial", "Local", "Terreno",
         "Garage", "Chacra", "Edificio", "Galpón", "Piso", "Pieza", "Cochera"]
TIPO_RE = "|".join(re.escape(t) for t in TIPOS)

GALLITO_BASE = {
    "venta": "https://www.gallito.com.uy/inmuebles/venta/montevideo",
    "alquiler": "https://www.gallito.com.uy/inmuebles/alquiler/montevideo",
}

# ---------------------------------------------------------------------------
# InfoCasas (requests normales — este portal no bloquea)
# ---------------------------------------------------------------------------

# una sesion por dominio para reutilizar cookies (ayuda contra bloqueos tipo
# Cloudflare que exigen una cookie de "challenge" obtenida en la home antes de
# dejar pasar a paginas internas)
_sessions = {}
_warmed = set()


def _session_for(url):
    from urllib.parse import urlparse
    host = urlparse(url).netloc
    if host not in _sessions:
        s = requests.Session()
        s.headers.update(BASE_HEADERS)
        _sessions[host] = s
    return _sessions[host], host


def _warmup(session, host):
    """Visita la home del sitio una vez por corrida para conseguir cookies
    antes de pedir paginas internas (asi el pedido no parece 'en frio')."""
    if host in _warmed:
        return
    _warmed.add(host)
    try:
        session.get(f"https://{host}/", timeout=20)
        time.sleep(1)
    except requests.RequestException:
        pass


def fetch(url, retries=4, referer=None):
    session, host = _session_for(url)
    _warmup(session, host)
    headers = {}
    if referer:
        headers["Referer"] = referer
    for i in range(retries):
        try:
            r = session.get(url, headers=headers, timeout=25)
            if r.status_code == 200:
                return r.text
            print(f"  [warn] {url} -> HTTP {r.status_code}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  [warn] {url} -> {e}", file=sys.stderr)
        # backoff creciente + jitter, mas cortes que un sleep fijo
        time.sleep(2 * (i + 1) + random.uniform(0, 1.5))
    return None


def parse_infocasas(html, operacion):
    """InfoCasas: cada aviso es un <a> cuyo href termina en /<digitos>, el texto
    completo de esa card sigue el patron: PRECIO Tipo en Barrio, Montevideo
    Dorm Baño m² descripcion... Contactar"""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    seen = set()
    for a in soup.find_all("a", href=re.compile(r"/\d{5,}$")):
        href = a.get("href", "")
        if not href.startswith("http"):
            href = "https://www.infocasas.com.uy" + href
        if href in seen:
            continue
        text = a.get_text(" ", strip=True)
        if not text or ("Dorm" not in text and "Ambiente" not in text):
            continue
        is_project = "Unidades desde" in text or "unidades disponibles" in text.lower()
        m_precio = re.search(r"(U\$S|US\$|\$)\s*([\d.,]+)", text)
        moneda = "USD" if m_precio and m_precio.group(1) in ("U$S", "US$") else ("UYU" if m_precio else "")
        precio = m_precio.group(2).replace(".", "").replace(",", "") if m_precio else ""
        m_gc = re.search(r"\+\s*\$\s*([\d.,]+)\s*GC", text)
        gastos = m_gc.group(1).replace(".", "") if m_gc else ""
        m_tipo = re.search(rf"({TIPO_RE})\s+en\s+([^,]+),\s*Montevideo", text)
        tipo = m_tipo.group(1) if m_tipo else ""
        barrio = m_tipo.group(2).strip() if m_tipo else ""
        m_dorm = re.search(r"\b(Mono|\d+\s*Dorms?\.?)\b", text)
        dorm = "0" if (m_dorm and "Mono" in m_dorm.group(1)) else (re.sub(r"\D", "", m_dorm.group(1)) if m_dorm else "")
        m_banos = re.search(r"(\d+)\s*Baños?", text)
        banos = m_banos.group(1) if m_banos else ""
        m_m2 = re.search(r"([\d.,]+)\s*m²", text)
        m2 = m_m2.group(1).replace(",", ".") if m_m2 else ""
        seen.add(href)
        rows.append({
            "portal": "InfoCasas", "operacion": operacion, "url": href,
            "titulo": a.get("title", "") or text[:80],
            "tipo_inmueble": "Proyecto" if is_project else tipo,
            "barrio": barrio, "precio_moneda": moneda, "precio_valor": precio,
            "gastos_comunes": gastos, "dormitorios": dorm, "banos": banos, "m2": m2,
        })
    return rows


def collect(base_url, paginas, pagina_fmt, parser, operacion, sleep=1.5):
    rows = []
    referer = None
    for p in range(1, paginas + 1):
        url = base_url if p == 1 else pagina_fmt.format(base=base_url, p=p)
        print(f"  fetching {url}", file=sys.stderr)
        html = fetch(url, referer=referer)
        referer = url
        if not html:
            continue
        page_rows = parser(html, operacion)
        print(f"    -> {len(page_rows)} avisos", file=sys.stderr)
        rows.extend(page_rows)
        time.sleep(sleep + random.uniform(0, 1))
    return rows


# ---------------------------------------------------------------------------
# Gallito (via navegador real — este portal bloquea requests normales con 403)
# ---------------------------------------------------------------------------

def extract_gallito_cards(page):
    """Extrae los avisos visibles en la pagina actual usando el DOM.
    Estructura confirmada en vivo (julio 2026):
      <article> (con un <a href*="-inmuebles-">)
        .contenedor-info
          div
            p       -> "Casas en Aguada"        (tipo plural + " en " + barrio)
            strong  -> "108.000"  (con <span> adentro = moneda, ej "U$S")
          .mas-info
            a
              span  -> "3 Dormitorios" (puede faltar, ej. oficinas)
              h2    -> "Casa en Venta" / "Apartamento en Venta - Villa Española"
    """
    return page.evaluate(
        """
        () => {
            function clean(u) { return u ? u.split('?')[0].split('#')[0] : ''; }
            const articles = Array.from(document.querySelectorAll('article'));
            const cards = articles.filter(a => a.querySelector('a[href*="-inmuebles-"]'));
            const out = [];
            cards.forEach(card => {
                const linkEl = card.querySelector('a[href*="-inmuebles-"]');
                const href = clean(linkEl ? linkEl.href : '');
                const info = card.querySelector('.contenedor-info');
                if (!info) return;
                const firstDiv = info.children[0];
                const p = firstDiv ? firstDiv.querySelector('p') : null;
                const strong = firstDiv ? firstDiv.querySelector('strong') : null;
                const currSpan = strong ? strong.querySelector('span') : null;
                const masInfo = info.querySelector('.mas-info');
                const dormSpan = masInfo ? masInfo.querySelector('a > span') : null;
                const h2 = masInfo ? masInfo.querySelector('a > h2') : null;
                let precioText = '';
                if (strong) {
                    precioText = Array.from(strong.childNodes)
                        .filter(n => n.nodeType === 3)
                        .map(n => n.textContent.trim())
                        .join(' ').trim();
                }
                out.push({
                    href,
                    barrio_tipo: p ? p.textContent.trim() : '',
                    precio: precioText,
                    moneda: currSpan ? currSpan.textContent.trim() : '',
                    dorm_text: dormSpan ? dormSpan.textContent.trim() : '',
                    titulo: h2 ? h2.textContent.trim() : ''
                });
            });
            return out;
        }
        """
    )


def parse_gallito_items(items, operacion):
    rows = []
    for it in items:
        href = it.get("href") or ""
        if not href:
            continue
        barrio_tipo = it.get("barrio_tipo") or ""
        m = re.match(r"^(.*?)\s+en\s+(.+)$", barrio_tipo)
        tipo_plural = m.group(1).strip() if m else ""
        barrio = m.group(2).strip() if m else ""
        tipo = ""
        for t in TIPOS:
            singular = t.lower().rstrip("s")
            if singular and singular in tipo_plural.lower():
                tipo = t
                break
        titulo = it.get("titulo") or barrio_tipo
        precio_raw = it.get("precio") or ""
        precio = re.sub(r"\D", "", precio_raw)
        moneda_raw = it.get("moneda") or ""
        moneda = "USD" if ("U$S" in moneda_raw or "US$" in moneda_raw) else ("UYU" if moneda_raw else "")
        dorm_text = it.get("dorm_text") or ""
        m_dorm = re.search(r"(\d+)", dorm_text)
        dorm = m_dorm.group(1) if m_dorm else ("0" if "mono" in dorm_text.lower() else "")
        rows.append({
            "portal": "Gallito", "operacion": operacion, "url": href,
            "titulo": titulo, "tipo_inmueble": tipo, "barrio": barrio,
            "precio_moneda": moneda, "precio_valor": precio, "gastos_comunes": "",
            "dormitorios": dorm, "banos": "", "m2": "",
        })
    # dedup por url dentro de esta tanda (una pagina puede repetir avisos destacados)
    dedup = {}
    for r in rows:
        dedup[r["url"]] = r
    return list(dedup.values())


def cargar_pagina_gallito(page, url, intentos=2):
    """Navega a una pagina de Gallito y espera a que aparezcan las tarjetas.
    Reintenta una vez mas si la primera pasada falla (timeouts intermitentes
    por scripts de ads/analytics lentos), antes de darse por vencido."""
    for intento in range(1, intentos + 1):
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            # OJO: no usar el estado por defecto ("visible") aca. Hay ~330
            # anchors que matchean este selector en la pagina y Playwright
            # esperaria a que el PRIMERO de ellos (en orden del DOM) sea
            # visible; ese primero suele ser un link oculto/duplicado, no una
            # tarjeta real. Con "attached" alcanza con que exista en el DOM
            # (los datos se leen via evaluate() igual).
            page.wait_for_selector('a[href*="-inmuebles-"]', timeout=20000, state="attached")
            return True
        except Exception as e:
            print(f"  [warn] intento {intento}/{intentos} {url} -> {e}", file=sys.stderr)
            if intento < intentos:
                time.sleep(3)
    return False


def collect_gallito_playwright(paginas):
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent=UA,
            locale="es-UY",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={
                "Accept-Language": "es-UY,es;q=0.9,en;q=0.8",
            },
        )
        context.add_init_script(STEALTH_JS)
        # Gallito es un sitio ASP.NET clasico con ~90 requests por pagina entre
        # imagenes y scripts de ads/analytics (doubleclick, googlesyndication,
        # tags de analytics, cxense) que a veces cuelgan la carga 45+ segundos.
        # No los necesitamos para leer los datos (son solo texto), asi que se
        # bloquean para acelerar la carga y evitar esos cuelgues.
        context.route("**/*", bloquear_recursos_innecesarios)
        page = context.new_page()

        for operacion, base in GALLITO_BASE.items():
            for n in range(1, paginas + 1):
                url = base if n == 1 else f"{base}?pag={n}"
                print(f"  fetching {url}", file=sys.stderr)
                if cargar_pagina_gallito(page, url):
                    items = extract_gallito_cards(page)
                    page_rows = parse_gallito_items(items, operacion)
                    print(f"    -> {len(page_rows)} avisos", file=sys.stderr)
                    rows.extend(page_rows)
                else:
                    print(f"  [warn] se omite {url} tras reintentos", file=sys.stderr)
                time.sleep(1.5)
        browser.close()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--paginas", type=int, default=5)
    args = ap.parse_args()

    all_rows = []

    print("InfoCasas venta...", file=sys.stderr)
    all_rows += collect(
        "https://www.infocasas.com.uy/venta/inmuebles/montevideo", args.paginas,
        "{base}/pagina{p}", parse_infocasas, "venta")

    print("InfoCasas alquiler...", file=sys.stderr)
    all_rows += collect(
        "https://www.infocasas.com.uy/alquiler/inmuebles/montevideo", args.paginas,
        "{base}/pagina{p}", parse_infocasas, "alquiler")

    print("Gallito (venta + alquiler, via navegador)...", file=sys.stderr)
    all_rows += collect_gallito_playwright(args.paginas)

    # dedup por url
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
