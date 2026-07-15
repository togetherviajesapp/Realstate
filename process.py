#!/usr/bin/env python3
"""
Combina los CSV crudos de los 3 portales, compara contra data.json existente
(nuevo / mantenido / baja) y escribe data.json actualizado para el sitio estatico.

Ademas de los avisos activos (listado), esta corrida mantiene:
  - historial_precio por aviso: cada vez que el precio de un aviso cambia entre
    corridas, se agrega una entrada {fecha, precio_valor, precio_moneda}. Sirve
    para ver la variacion de precio de una publicacion en el tiempo.
  - bajas_historico: registro ACUMULATIVO (nunca se borra) de cada aviso que
    deja de aparecer en el portal, con sus datos completos al momento de la
    baja (tipo, barrio, precio, cuanto tiempo estuvo publicado). Como no se
    puede confirmar con certeza que una baja sea una venta/alquiler concretado
    (el portal tambien puede darlo de baja por vencimiento u otro motivo), el
    sitio lo muestra siempre como "posible venta/alquiler", nunca como venta
    confirmada.

Uso:
    python process.py --csvs data/raw_infocasas_gallito.csv data/raw_mercadolibre.csv \
                       --data data.json --fecha 2026-07-20
"""
import argparse
import json
import os
import sys
from datetime import date

import pandas as pd

from barrios import normalizar_barrios

COLS = ["portal", "operacion", "url", "titulo", "tipo_inmueble", "barrio",
        "precio_moneda", "precio_valor", "gastos_comunes", "dormitorios", "banos", "m2"]


def load_existing(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dias_entre(f1, f2):
    """Dias entre dos fechas ISO (yyyy-mm-dd). Devuelve None si no se puede calcular."""
    try:
        d1 = date.fromisoformat(f1)
        d2 = date.fromisoformat(f2)
        return (d2 - d1).days
    except Exception:
        return None


def precio_cambio(row):
    """Tupla (precio_valor, precio_moneda) normalizada para comparar si cambio el precio."""
    return (str(row.get("precio_valor", "") or ""), str(row.get("precio_moneda", "") or ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csvs", nargs="+", required=True)
    ap.add_argument("--data", required=True, help="ruta de data.json (se lee y se sobreescribe)")
    ap.add_argument("--fecha", default=date.today().isoformat())
    args = ap.parse_args()

    dfs = []
    for path in args.csvs:
        if os.path.exists(path):
            dfs.append(pd.read_csv(path, dtype=str, encoding="utf-8-sig"))
        else:
            print(f"[warn] no existe {path}, se omite", file=sys.stderr)
    if not dfs:
        print("ERROR: ningun CSV disponible", file=sys.stderr)
        sys.exit(1)

    df_new = pd.concat(dfs, ignore_index=True)
    df_new = df_new.drop_duplicates(subset=["url"])
    for c in COLS:
        if c not in df_new.columns:
            df_new[c] = ""
    df_new = df_new[COLS].fillna("")

    existing = load_existing(args.data)
    fecha = args.fecha
    bajas_historico = list(existing.get("bajas_historico", [])) if existing else []

    if existing is None:
        listado = df_new.to_dict("records")
        for r in listado:
            r["primera_vez_visto"] = fecha
            r["ultima_vez_visto"] = fecha
            r["estado"] = "Nuevo"
            r["historial_precio"] = [{
                "fecha": fecha,
                "precio_valor": r.get("precio_valor", ""),
                "precio_moneda": r.get("precio_moneda", ""),
            }]
        historico = []
        nuevos_count = len(listado)
        mantenidos_count = 0
        bajas_count = 0
    else:
        old_listado = {r["url"]: r for r in existing.get("listado", [])}
        new_urls = set(df_new["url"])
        old_urls = set(old_listado.keys())

        nuevos_urls = new_urls - old_urls
        mantenidos_urls = new_urls & old_urls
        bajas_urls = old_urls - new_urls

        listado = []
        for row in df_new.to_dict("records"):
            url = row["url"]
            if url in nuevos_urls:
                row["primera_vez_visto"] = fecha
                row["ultima_vez_visto"] = fecha
                row["estado"] = "Nuevo"
                row["historial_precio"] = [{
                    "fecha": fecha,
                    "precio_valor": row.get("precio_valor", ""),
                    "precio_moneda": row.get("precio_moneda", ""),
                }]
            else:
                old_row = old_listado[url]
                row["primera_vez_visto"] = old_row.get("primera_vez_visto", fecha)
                row["ultima_vez_visto"] = fecha
                row["estado"] = "Mantenido"
                hist = list(old_row.get("historial_precio", []))
                if not hist:
                    # aviso de antes de esta funcionalidad, sin historial guardado:
                    # arrancamos la serie con el ultimo precio que se le conocia
                    hist = [{
                        "fecha": row["primera_vez_visto"],
                        "precio_valor": old_row.get("precio_valor", ""),
                        "precio_moneda": old_row.get("precio_moneda", ""),
                    }]
                if precio_cambio(hist[-1]) != precio_cambio(row):
                    hist.append({
                        "fecha": fecha,
                        "precio_valor": row.get("precio_valor", ""),
                        "precio_moneda": row.get("precio_moneda", ""),
                    })
                row["historial_precio"] = hist
            listado.append(row)

        nuevos_count = len(nuevos_urls)
        mantenidos_count = len(mantenidos_urls)
        bajas_count = len(bajas_urls)

        historico = existing.get("historico", [])

        # registro detallado y acumulativo de bajas (posible venta/alquiler)
        for url in bajas_urls:
            old_row = old_listado[url]
            primera = old_row.get("primera_vez_visto", fecha)
            bajas_historico.append({
                "url": url,
                "portal": old_row.get("portal", ""),
                "operacion": old_row.get("operacion", ""),
                "titulo": old_row.get("titulo", ""),
                "tipo_inmueble": old_row.get("tipo_inmueble", ""),
                "barrio": old_row.get("barrio", ""),
                "precio_moneda": old_row.get("precio_moneda", ""),
                "precio_valor": old_row.get("precio_valor", ""),
                "primera_vez_visto": primera,
                "ultima_vez_visto": old_row.get("ultima_vez_visto", fecha),
                "fecha_baja": fecha,
                "dias_publicado": dias_entre(primera, fecha),
                "historial_precio": old_row.get("historial_precio", []),
            })

    # contar por portal+operacion para el historico de esta corrida
    from collections import defaultdict
    counts = defaultdict(lambda: {"nuevos": 0, "mantenidos": 0, "bajas": 0})
    for row in listado:
        key = (row["portal"], row["operacion"])
        counts[key]["nuevos" if row["estado"] == "Nuevo" else "mantenidos"] += 1

    if existing is not None:
        for url in (old_urls - new_urls):
            r = old_listado[url]
            key = (r["portal"], r["operacion"])
            counts[key]["bajas"] += 1

    for (portal, operacion), c in counts.items():
        historico.append({
            "fecha": fecha, "portal": portal, "operacion": operacion,
            "nuevos": c["nuevos"], "mantenidos": c["mantenidos"], "bajas": c["bajas"],
            "total_activos": c["nuevos"] + c["mantenidos"],
        })

    print("Normalizando barrios (match directo + geocoding para direcciones)...", file=sys.stderr)
    listado = normalizar_barrios(listado)

    out = {
        "actualizado": fecha,
        "total_activos": len(listado),
        "resumen_ultima_corrida": {
            "nuevos": nuevos_count, "mantenidos": mantenidos_count, "bajas": bajas_count,
        },
        "listado": listado,
        "historico": historico,
        "bajas_historico": bajas_historico,
    }

    with open(args.data, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(f"OK: {args.data} actualizado. Activos={len(listado)} "
          f"Nuevos={nuevos_count} Mantenidos={mantenidos_count} Bajas={bajas_count} "
          f"BajasHistoricoTotal={len(bajas_historico)}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
