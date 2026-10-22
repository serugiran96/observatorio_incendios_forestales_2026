"""Configuración central del observatorio: rutas, fechas de corte y sistemas de referencia."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# --- Rutas del proyecto -------------------------------------------------------
RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
DIR_DATOS = RAIZ_PROYECTO / "data"
DIR_RAW = DIR_DATOS / "raw"
DIR_REGISTRO = DIR_RAW / "registro"          # registro curado de fuentes y evidencias (versionado)
DIR_DOCUMENTOS = DIR_RAW / "documentos"      # PDFs y páginas descargadas (no versionado)
DIR_GEODATOS = DIR_RAW / "geodatos"          # límites, ecosistemas, etc. descargados por script
DIR_PROCESSED = DIR_DATOS / "processed"      # salidas reproducibles que lee el dashboard
DIR_DOCS = RAIZ_PROYECTO / "docs"
DIR_REPORTES = RAIZ_PROYECTO / "reports"

RUTA_FUENTES = DIR_REGISTRO / "fuentes.csv"
RUTA_EVIDENCIAS = DIR_REGISTRO / "evidencias.csv"
RUTA_VACIOS = DIR_REGISTRO / "vacios_informacion.csv"

# --- Alcance temporal ---------------------------------------------------------
FECHA_CORTE = date(2026, 10, 21)
PERIODO_PRIORITARIO = (date(2026, 9, 1), FECHA_CORTE)
# Horizontes de intervención (en días desde el evento)
HORIZONTE_INMEDIATO_DIAS = 90
HORIZONTE_RESTAURACION_ANIOS = 5

# --- Alcance territorial ------------------------------------------------------
CODIGO_DEPARTAMENTO_CUSCO = "08"  # prefijo UBIGEO INEI del departamento de Cusco
# Caja envolvente aproximada (con margen) para validar coordenadas; no reemplaza al límite oficial.
CAJA_CUSCO = {"lat_min": -15.6, "lat_max": -11.0, "lon_min": -74.2, "lon_max": -70.2}

# --- Sistemas de referencia ---------------------------------------------------
CRS_GEOGRAFICO = "EPSG:4326"
# Cusco cruza las zonas UTM 18S y 19S; para áreas usamos una proyección de igual área continental.
CRS_AREA = "ESRI:102033"  # South America Albers Equal Area Conic


def leer_variable_entorno(nombre: str) -> str | None:
    """Lee una variable desde el entorno o desde `.env` (nunca versionado)."""
    load_dotenv(RAIZ_PROYECTO / ".env")
    valor = os.getenv(nombre)
    return valor or None
