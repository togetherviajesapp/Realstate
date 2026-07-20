#!/usr/bin/env python3
"""
Scraper de Veocasas (Montevideo, venta + alquiler), via Playwright.

20/7/2026: se investigo el sitio (dominio real veocasas.com, sin ".uy" --
el dominio veocasas.com.uy solo redirige). A diferencia de lo que se penso
en un primer momento, SI tiene paginacion por URL real:

    https://veocasas.com/properties?location=1&recenter=1&page=N              (venta)
    https://veocasas.com/properties?location=1&recenter=1&operation=RENT&page=N (alquiler)

"location=1" ya filtra a Montevideo (confirmado en vivo: el filtro de
Ubicacion queda marcado en "Montevideo" con ese parametro). Cada pagina
tiene ~20 avisos; venta llega hasta la pagina 375 y alquiler hasta la 67,
pero -- igual que con los demas portales -- solo se scrapean las primeras
paginas (orden "Mas nuevos", que es el que trae el sitio por default).

Cada tarjeta es un <a href="/properties/{id}"> que envuelve toda su
informacion (imagen, precio, gastos comunes, titulo, dormitorios, banos,
m2). El sitio muestra la MISMA tarjeta dos veces en el DOM (una version
para mobile y otra para desktop, ocultada por CSS segun el ancho de
pantalla) -- por eso se filtra por `offsetParent !== null` (solo la version
realmente visible en el viewport que usa este scraper) antes de deduplicar
por id.

El sitio no expone el barrio como campo aparte: se intenta encontrar el
nombre de un barrio oficial de Montevideo como substring del titulo
(reutilizando la lista de barrios.py) y se deja vacio si no aparece
ninguno -- no tiene sentido geocodificar un titulo de marketing como si
fuera una direccion.

Uso:
    python scraper_veocasas.py --out data/raw_veocasas.csv --paginas 5
"""
import argparse
import csv
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

from barrios import _match_conocido

BASE = {
    "venta": "https://veocasas.com/properties?location=1&recenter=1",
    "alquiler": "https://veocasas.com/properties?location=1&recenter=1&operation=RENT",
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


def guess_tipo(titulo):
    t = titulo.lower()
    if "monoambiente" in t:
        return "Apartamento"
    for tipo in TIPOS:
        if tipo.lower() in t:
            return tipo
    return ""


def page_url(base, n):
    return f"{base}&page={n}"


def extract_veocasas_cards(page):
    """Lee las tarjetas visibles de la pagina actual. Cada tarjeta es el
    propio <a href="/properties/{id}"> que envuelve toda su info; se leen
    TODOS los nodos de texto en orden (no solo los elementos hoja) porque
    el precio comparte un mismo <p> con el span de gastos comunes."""
    return page.evaluate(
        """
        () => {
            function textNodes(el) {
                const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
                const out = [];
                let n;
                while ((n = walker.nextNode())) {
                    const t = n.textContent.trim();
                    if (t) out.push(t);
                }
                return out;
            }
            const anchors = Array.from(document.querySelectorAll('a[href^="/properties/"]'));
            // el sitio duplica cada tarjeta (version mobile oculta por CSS +
            // version desktop visible); nos quedamos solo con la visible.
            const visible = anchors.filter(a => a.offsetParent !== null);
            const seen = new Set();
            const out = [];
            for (const a of visible) {
                const href = a.getAttribute('href').split('#')[0];
                const id = href.split('/').pop();
                if (seen.has(id)) continue;
                seen.add(id);
                const texts = textNodes(a);
                if (!texts.length) continue;
                out.push({ id, texts });
            }
            return out;
        }
        """
    )


def parse_veocasas_items(items, operacion):
    rows = []
    for it in items:
        texts = it.get("texts") or []
        prop_id = it.get("id") or ""
        if not prop_id:
            continue

        # precio: primer texto que matchee "US$ 123.456" / "$ 123.456" / "Consultar"
        idx = None
        for i, t in enumerate(texts):
            if re.match(r"^(US\$|\$)\s?[\d.,]+$", t) or t == "Consultar":
                idx = i
                break
        if idx is None:
            continue

        precio_tok = texts[idx]
        precio_valor, precio_moneda = "", ""
        if precio_tok != "Consultar":
            precio_moneda = "USD" if precio_tok.startswith("US$") else "UYU"
            precio_valor = re.sub(r"\D", "", precio_tok)

        cursor = idx + 1
        gastos = ""
        # gastos comunes: aparecen como "+" seguido de "$ 6.000 GC" (o "US$ ... GC")
        if cursor < len(texts) and texts[cursor] == "+":
            if cursor + 1 < len(texts):
                gastos = re.sub(r"\D", "", texts[cursor + 1])
            cursor += 2

        if cursor >= len(texts):
            continue  # no hay titulo, tarjeta incompleta -- se descarta

        titulo = texts[cursor]
        cursor += 1
        resto = texts[cursor:]

        # m2: el texto justo antes de un token "m²"
        m2 = ""
        m2_idx = None
        for i in range(len(resto) - 1):
            if resto[i + 1].startswith("m²"):
                m2 = re.sub(r"[^\d.,]", "", resto[i]).replace(",", ".")
                m2_idx = i
                break
        descartar = {m2_idx, m2_idx + 1} if m2_idx is not None else set()
        resto_sin_m2 = [t for j, t in enumerate(resto) if j not in descartar]

        # dormitorios/banos: los primeros 1-2 valores que queden (en ese orden);
        # "Monoambiente" en vez de un numero significa 0 dormitorios
        dorm, banos = "", ""
        if len(resto_sin_m2) >= 1:
            dorm = "0" if "monoamb" in resto_sin_m2[0].lower() else re.sub(r"\D", "", resto_sin_m2[0])
        if len(resto_sin_m2) >= 2:
            banos = re.sub(r"\D", "", resto_sin_m2[1])

        barrio = _match_conocido(titulo) or ""

        rows.append({
            "portal": "Veocasas",
            "operacion": operacion,
            "url": f"https://veocasas.com/properties/{prop_id}",
            "titulo": titulo,
            "tipo_inmueble": guess_tipo(titulo),
            "barrio": barrio,
            "precio_moneda": precio_moneda,
            "precio_valor": precio_valor,
            "gastos_comunes": gastos,
            "dormitorios": dorm,
            "banos": banos,
            "m2": m2,
        })

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


def cargar_pagina_veocasas(page, url, intentos=2):
    for intento in range(1, intentos + 1):
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector('a[href^="/properties/"]', timeout=20000, state="attached")
            time.sleep(1)
            return True
        except Exception as e:
            print(f"  [warn] intento {intento}/{intentos} {url} -> {e}", file=sys.stderr)
            if intento < intentos:
                time.sleep(3)
    return False


def cargar_veocasas(browser, operacion, paginas=5):
    context = _nuevo_contexto(browser)
    page = context.new_page()
    rows = []
    try:
        for n in range(1, paginas + 1):
            url = page_url(BASE[operacion], n)
            if not cargar_pagina_veocasas(page, url):
                print(f"    pagina {n}: no se pudo cargar, se omite ({operacion})", file=sys.stderr)
                continue
            items = extract_veocasas_cards(page)
            page_rows = parse_veocasas_items(items, operacion)
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
            print(f"Veocasas {operacion}...", file=sys.stderr)
            all_rows.extend(cargar_veocasas(browser, operacion, paginas=args.paginas))
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
