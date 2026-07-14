#!/usr/bin/env python3
"""
Normalizacion de barrios de Montevideo.

Muchos avisos traen una direccion (calle + numero) en el campo "barrio" en vez
del nombre del barrio. Esta funcion:
  1. Si el valor ya es un barrio oficial conocido (o lo contiene), lo devuelve normalizado.
  2. Si no, geocodifica la direccion con Nominatim (OpenStreetMap, gratuito) y
     mapea el resultado al barrio oficial mas cercano.
  3. Cachea resultados en un JSON para no volver a consultar la misma direccion.
"""
import json
import os
import re
import time
import unicodedata

import requests

CACHE_FILE = os.path.join(os.path.dirname(__file__), "data", "geocode_cache.json")

# Lista de barrios oficiales de Montevideo (Municipios/CCZ), con variantes comunes
# que aparecen en los portales inmobiliarios.
BARRIOS_OFICIALES = [
    "Ciudad Vieja", "Centro", "Barrio Sur", "Cordón", "Cordón Sur", "Aguada",
    "Reducto", "Bella Vista", "Capurro", "Parque Rodó", "Palermo",
    "Punta Carretas", "Pocitos", "Pocitos Nuevo", "Buceo", "Puerto Buceo",
    "Malvín", "Malvín Norte", "Carrasco", "Carrasco Norte", "Punta Gorda",
    "Villa Dolores", "Parque Batlle", "Tres Cruces", "La Blanqueada",
    "Larrañaga", "Brazo Oriental", "La Comercial", "Jacinto Vera",
    "Atahualpa", "Prado", "Nueva Savona", "Sayago", "Colón", "Lezica",
    "Melilla", "Peñarol", "Cerro", "La Teja", "Belvedere", "Nuevo París",
    "Paso de la Arena", "Villa Española", "Flor de Maroñas", "Maroñas",
    "Ituzaingó", "Unión", "Villa Muñoz", "Goes", "Mercado Modelo",
    "Arroyo Seco", "Cerrito", "Casabó", "Pajas Blancas", "Santiago Vázquez",
    "Piedras Blancas", "Manga", "Casavalle", "Marconi", "Camino Carrasco",
    "Punta Rieles", "Bañados de Carrasco", "Golf", "Trouville",
]


def _strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _norm(s):
    return _strip_accents(s).lower().strip()


_BARRIOS_NORM = {_norm(b): b for b in BARRIOS_OFICIALES}


def _match_conocido(valor):
    """Si el valor ya es (o contiene) un barrio oficial, lo devuelve normalizado."""
    v = _norm(valor)
    if v in _BARRIOS_NORM:
        return _BARRIOS_NORM[v]
    # buscar como substring completo de palabra (evita falsos positivos parciales)
    for norm_b, real_b in sorted(_BARRIOS_NORM.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{re.escape(norm_b)}\b", v):
            return real_b
    return None


def _parece_direccion(valor):
    """Heuristica: si tiene numeros, probablemente es una direccion, no un barrio."""
    return bool(re.search(r"\d", valor))


def _load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)


def _geocodificar(direccion):
    """Consulta Nominatim (OpenStreetMap) y devuelve el barrio oficial mas cercano, o None."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": f"{direccion}, Montevideo, Uruguay",
                "format": "json",
                "addressdetails": 1,
                "limit": 1,
            },
            headers={"User-Agent": "reporte-inmuebles-montevideo/1.0 (uso personal)"},
            timeout=15,
        )
        data = r.json()
        if not data:
            return None
        addr = data[0].get("address", {})
        candidato = addr.get("suburb") or addr.get("neighbourhood") or addr.get("city_district") or addr.get("quarter")
        if not candidato:
            return None
        match = _match_conocido(candidato)
        return match or candidato
    except Exception:
        return None


def normalizar_barrios(rows, campo="barrio", sleep=1.1):
    """
    Recibe una lista de dicts con un campo de barrio/direccion y devuelve la
    misma lista con ese campo normalizado a un barrio oficial cuando sea posible.
    Usa cache persistente para no re-geocodificar direcciones ya resueltas.
    """
    cache = _load_cache()
    nuevas_consultas = 0

    for row in rows:
        valor = (row.get(campo) or "").strip()
        if not valor:
            continue

        conocido = _match_conocido(valor)
        if conocido:
            row[campo] = conocido
            continue

        if not _parece_direccion(valor):
            # no tiene numeros, probablemente ya es un nombre propio de zona;
            # se deja tal cual (ej. "Puerto del Buceo" con variantes no listadas)
            continue

        if valor in cache:
            if cache[valor]:
                row[campo] = cache[valor]
            continue

        resultado = _geocodificar(valor)
        cache[valor] = resultado
        nuevas_consultas += 1
        if resultado:
            row[campo] = resultado
        time.sleep(sleep)

    if nuevas_consultas:
        _save_cache(cache)

    return rows
