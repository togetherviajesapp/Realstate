#!/usr/bin/env python3
"""
Scraper de InfoCasas y Gallito para Montevideo (venta + alquiler).
Pensado para correr en GitHub Actions (tiene internet real, sin restricciones de proxy).

Uso:
    python scraper.py --out data/raw_infocasas_gallito.csv --paginas 5
"""
import argparse
import csv
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "es-UY,es;q=0.9",
}

TIPOS = ["Apartamento", "Casa", "Oficina", "Local Comercial", "Local", "Terreno",
         "Garage", "Chacra", "Edificio", "Galpón", "Piso", "Pieza", "Cochera"]
TIPO_RE = "|".join(re.escape(t) for t in TIPOS)


def fetch(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 200:
                return r.text
            print(f"  [warn] {url} -> HTTP {r.status_code}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  [warn] {url} -> {e}", file=sys.stderr)
        time.sleep(2)
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


def parse_gallito(html, operacion):
    """Gallito: cada aviso tiene un <a> con href tipo .../inmuebles-<digitos>.
    El precio suele estar en un elemento hermano/cercano con U$S o $."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    seen = set()
    for a in soup.find_all("a", href=re.compile(r"-inmuebles-\d+")):
        href = a.get("href", "")
        if not href.startswith("http"):
            href = "https://www.gallito.com.uy" + href
        if href in seen or not a.get_text(strip=True):
            continue
        titulo = a.get_text(" ", strip=True)
        # buscar precio en el contenedor padre (hasta 3 niveles arriba)
        container = a
        precio_text = ""
        for _ in range(4):
            if container.parent is None:
                break
            container = container.parent
            t = container.get_text(" ", strip=True)
            m = re.search(r"(U\$S|US\$|\$)\s*([\d.,]+)", t)
            if m:
                precio_text = m.group(0)
                break
        m_precio = re.search(r"(U\$S|US\$|\$)\s*([\d.,]+)", precio_text)
        moneda = "USD" if m_precio and m_precio.group(1) in ("U$S", "US$") else ("UYU" if m_precio else "")
        precio = m_precio.group(2).replace(".", "") if m_precio else ""
        m_dorm = re.search(r"(\d+)\s*Dormitorios?", titulo, re.I)
        dorm = m_dorm.group(1) if m_dorm else ""
        m_tipo = re.search(rf"({TIPO_RE})", titulo, re.I)
        tipo = m_tipo.group(1).capitalize() if m_tipo else ""
        m_barrio = re.search(r"\ben\s+([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ. ]+)$", titulo)
        barrio = m_barrio.group(1).strip() if m_barrio else ""
        seen.add(href)
        rows.append({
            "portal": "Gallito", "operacion": operacion, "url": href,
            "titulo": titulo, "tipo_inmueble": tipo, "barrio": barrio,
            "precio_moneda": moneda, "precio_valor": precio, "gastos_comunes": "",
            "dormitorios": dorm, "banos": "", "m2": "",
        })
    return rows


def collect(base_url, paginas, pagina_fmt, parser, operacion, sleep=1.5):
    rows = []
    for p in range(1, paginas + 1):
        url = base_url if p == 1 else pagina_fmt.format(base=base_url, p=p)
        print(f"  fetching {url}", file=sys.stderr)
        html = fetch(url)
        if not html:
            continue
        page_rows = parser(html, operacion)
        print(f"    -> {len(page_rows)} avisos", file=sys.stderr)
        rows.extend(page_rows)
        time.sleep(sleep)
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

    print("Gallito venta...", file=sys.stderr)
    all_rows += collect(
        "https://www.gallito.com.uy/inmuebles/venta/montevideo", args.paginas,
        "{base}?pag={p}", parse_gallito, "venta")

    print("Gallito alquiler...", file=sys.stderr)
    all_rows += collect(
        "https://www.gallito.com.uy/inmuebles/alquiler/montevideo", args.paginas,
        "{base}?pag={p}", parse_gallito, "alquiler")

    # dedup por url
    dedup = {}
    for r in all_rows:
        dedup[r["url"]] = r
    all_rows = list(dedup.values())

    cols = ["portal", "operacion", "url", "titulo", "tipo_inmueble", "barrio",
            "precio_moneda", "precio_valor", "gastos_comunes", "dormitorios", "banos", "m2"]
    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in all_rows:
            w.writerow(r)
    print(f"TOTAL: {len(all_rows)} avisos -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
