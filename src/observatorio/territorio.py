"""Límites distritales oficiales y asignación de UBIGEO a los nombres de las fuentes.

Los nombres de distrito llegan con variantes ortográficas desde los reportes. Se comparan sin
tildes ni mayúsculas contra la lista oficial (OSINERGMIN/INEI); las variantes que no coinciden se
resuelven solo con alias explícitos y documentados, nunca por similitud automática.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import geopandas as gpd

from observatorio import config

RUTA_DISTRITOS = config.DIR_PROCESSED / "limites_cusco_distritos.geojson"
RUTA_PROVINCIAS = config.DIR_PROCESSED / "limites_cusco_provincias.geojson"

# (provincia, nombre en la fuente) -> nombre oficial
ALIAS_OFICIALES = {
    ("Anta", "Huarucondo"): "Huarocondo",
    ("La Convención", "Echarati"): "Echarate",
    ("La Convención", "Inkahuasi"): "Inkawasi",
    ("Quispicanchi", "Ccatcca"): "Ccatca",
    ("Chumbivilcas", "Ccapacmarca"): "Capacmarca",
    ("Calca", "La Mar"): "Lamay",
}
# Alias inferidos (no evidentes en la fuente) que deben verificarse
ALIAS_POR_VERIFICAR = {("Calca", "La Mar")}


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sin_tildes.lower())


@lru_cache(maxsize=2)
def cargar_distritos(ruta: Path = RUTA_DISTRITOS) -> gpd.GeoDataFrame:
    return gpd.read_file(ruta)


@lru_cache(maxsize=2)
def _indice_ubigeo(ruta: Path = RUTA_DISTRITOS) -> dict[tuple[str, str], str]:
    distritos = cargar_distritos(ruta)
    return {(normalizar(f.provincia), normalizar(f.distrito)): f.ubigeo for f in distritos.itertuples()}


def ubigeo_de(provincia: str, distrito: str, ruta: Path = RUTA_DISTRITOS) -> str | None:
    """UBIGEO de un distrito; None si el nombre no se reconoce (no se adivina)."""
    oficial = ALIAS_OFICIALES.get((provincia, distrito), distrito)
    return _indice_ubigeo(ruta).get((normalizar(provincia), normalizar(oficial)))


def ubigeos_de(provincia: str, distritos: str, ruta: Path = RUTA_DISTRITOS) -> list[str | None]:
    """UBIGEO de cada distrito de un campo que puede listar varios separados por "|"."""
    return [ubigeo_de(provincia, d, ruta) for d in distritos.split("|") if d]


def requiere_verificacion(provincia: str, distrito: str) -> bool:
    return (provincia, distrito) in ALIAS_POR_VERIFICAR
