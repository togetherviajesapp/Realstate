#!/usr/bin/env python3
"""
Combina los CSV crudos de los 3 portales, compara contra data.json existente
(nuevo / mantenido / baja) y escribe data.json actualizado para el sitio estatico.

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

COLS = ["portal", "operacion", "url", "titulo", "tipo_inmueble", "barrio",
        "precio_moneda", "precio_valor", "gastos_comunes", "dormitorios", "banos", "m2"]


def load_existing(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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

    if existing is None:
        listado = df_new.to_dict("records")
        for r in listado:
            r["primera_vez_visto"] = fecha
            r["ultima_vez_visto"] = fecha
            r["estado"] = "Nuevo"
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
            else:
                row["primera_vez_visto"] = old_listado[url].get("primera_vez_visto", fecha)
                row["ultima_vez_visto"] = fecha
                row["estado"] = "Mantenido"
            listado.append(row)

        nuevos_count = len(nuevos_urls)
        mantenidos_count = len(mantenidos_urls)
        bajas_count = len(bajas_urls)

        historico = existing.get("historico", [])

    # contar por portal+operacion para el historico de esta corrida
    from collections import defaultdict
    counts = defaultdict(lambda: {"nuevos": 0, "mantenidos": 0, "bajas": 0})
    for row in listado:
        key = (row["portal"], row["operacion"])
        counts[key]["nuevos" if row["estado"] == "Nuevo" else "mantenidos"] += 1

    if existing is not None:
        old_listado_map = {r["url"]: r for r in existing.get("listado", [])}
        for url in (old_urls - new_urls):
            r = old_listado_map[url]
            key = (r["portal"], r["operacion"])
            counts[key]["bajas"] += 1

    for (portal, operacion), c in counts.items():
        historico.append({
            "fecha": fecha, "portal": portal, "operacion": operacion,
            "nuevos": c["nuevos"], "mantenidos": c["mantenidos"], "bajas": c["bajas"],
            "total_activos": c["nuevos"] + c["mantenidos"],
        })

    out = {
        "actualizado": fecha,
        "total_activos": len(listado),
        "resumen_ultima_corrida": {
            "nuevos": nuevos_count, "mantenidos": mantenidos_count, "bajas": bajas_count,
        },
        "listado": listado,
        "historico": historico,
    }

    with open(args.data, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(f"OK: {args.data} actualizado. Activos={len(listado)} "
          f"Nuevos={nuevos_count} Mantenidos={mantenidos_count} Bajas={bajas_count}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
