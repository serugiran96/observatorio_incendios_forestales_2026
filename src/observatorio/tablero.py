"""Funciones compartidas por las páginas del dashboard: carga de datos, filtros, formato y gráficos.

El dashboard solo lee archivos de data/processed y del registro curado; nunca genera cifras propias
ni datos de demostración. Si falta una salida opcional (satélite), las páginas lo indican.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from observatorio import config, esquemas
from observatorio import evidencias as registro

PROCESADOS = config.DIR_PROCESSED

# --- Paleta (referencia validada: categórica en orden fijo, secuencial azul) ------------------
PALETA = {
    "light": {
        "categorica": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"],
        "neutro": "#898781", "tinta_secundaria": "#52514e", "superficie": "#ffffff",
        "secuencial": ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
    },
    "dark": {
        "categorica": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"],
        "neutro": "#898781", "tinta_secundaria": "#c3c2b7", "superficie": "#0e1117",
        "secuencial": ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
    },
}

ETIQUETAS_ATENCION = {
    **esquemas.ESTADOS_VERIFICACION,
    "sin daños a personas reportados": "Sin daños a personas reportados",
}


def paleta() -> dict:
    """Paleta del modo (claro u oscuro) que usa quien consulta."""
    try:
        modo = st.context.theme.type or "light"
    except AttributeError:
        modo = "light"
    return PALETA.get(modo, PALETA["light"])


# --- Formato ------------------------------------------------------------------------
def fmt(valor, decimales: int = 0) -> str:
    """Número con espacio de miles y coma decimal (convención SI usada en el Perú)."""
    if valor is None or pd.isna(valor):
        return "—"
    texto = f"{float(valor):,.{decimales}f}"
    return texto.replace(",", " ").replace(".", ",")


def fecha_larga(valor) -> str:
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
             "octubre", "noviembre", "diciembre"]
    d = pd.Timestamp(valor)
    return f"{d.day} de {meses[d.month - 1]} de {d.year}"


# --- Carga (con caché que se invalida cuando cambia el archivo) -----------------------------
def _marca(ruta: Path) -> float:
    return ruta.stat().st_mtime if ruta.exists() else 0.0


@st.cache_data(show_spinner=False)
def _leer_csv(ruta: str, marca: float, **kwargs) -> pd.DataFrame:
    return pd.read_csv(ruta, **kwargs)


def leer_procesado(nombre: str, **kwargs) -> pd.DataFrame | None:
    ruta = PROCESADOS / nombre
    if not ruta.exists():
        return None
    return _leer_csv(str(ruta), _marca(ruta), **kwargs)


@st.cache_data(show_spinner=False)
def _leer_geo(ruta: str, marca: float) -> gpd.GeoDataFrame:
    return gpd.read_file(ruta)


def leer_geo(nombre: str) -> gpd.GeoDataFrame | None:
    ruta = PROCESADOS / nombre
    return _leer_geo(str(ruta), _marca(ruta)) if ruta.exists() else None


def inventario() -> pd.DataFrame:
    inv = leer_procesado("incendios_cusco_georreferenciado.csv", dtype={"ubigeo": str, "sinpad": str}).copy()
    inv["fecha_ocurrencia"] = pd.to_datetime(inv["fecha_ocurrencia"])
    inv["fecha_ultimo_reporte"] = pd.to_datetime(inv["fecha_ultimo_reporte"], errors="coerce")
    return inv


def matriz_atencion() -> pd.DataFrame:
    m = leer_procesado("matriz_atencion_inmediata.csv", dtype={"ubigeo": str}).copy()
    m["fecha_ocurrencia"] = pd.to_datetime(m["fecha_ocurrencia"])
    return m


@st.cache_data(show_spinner=False)
def _registro(marcas: tuple) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fuentes = registro.cargar_fuentes()
    evidencias = registro.unir_con_fuentes(registro.cargar_evidencias(), fuentes)
    return fuentes, evidencias, registro.cargar_vacios()


def registro_curado() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(fuentes, evidencias con metadatos de su fuente, vacíos de información)."""
    marcas = tuple(_marca(r) for r in (config.RUTA_FUENTES, config.RUTA_EVIDENCIAS, config.RUTA_VACIOS))
    return _registro(marcas)


@st.cache_data(show_spinner=False)
def _ecosistemas_agrupados(ruta: str, marca: float) -> gpd.GeoDataFrame:
    """Ecosistemas MINAM en tres grupos relevantes para la restauración; el resto queda fuera del mapa."""
    eco = gpd.read_file(ruta)
    grupos = {"Bofedal": "Bofedal", "Pajonal": "Pajonal", "Bosque": "Bosque nativo"}
    eco["grupo"] = eco["ecosistema"].map(
        lambda e: next((g for prefijo, g in grupos.items() if e.startswith(prefijo)), None))
    eco = eco.dropna(subset=["grupo"]).dissolve(by="grupo", as_index=False)[["grupo", "geometry"]]
    eco["geometry"] = eco.geometry.simplify(0.003, preserve_topology=True)
    return eco


def ecosistemas_agrupados() -> gpd.GeoDataFrame | None:
    ruta = PROCESADOS / "ecosistemas_cusco.geojson"
    return _ecosistemas_agrupados(str(ruta), _marca(ruta)) if ruta.exists() else None


def estado_satelital() -> dict:
    """Qué productos satelitales existen (el análisis requiere credenciales de la usuaria)."""
    meta_ruta = PROCESADOS / "gee_metadatos.json"
    return {
        "focos": (PROCESADOS / "focos_calor_cusco.csv").exists(),
        "corroboracion": (PROCESADOS / "corroboracion_satelital.csv").exists(),
        "gee": (PROCESADOS / "gee_estadisticas_distrito.csv").exists(),
        "gee_metadatos": json.loads(meta_ruta.read_text()) if meta_ruta.exists() else None,
    }


# --- Filtros globales (barra lateral) ----------------------------------------------------
@dataclass
class Filtros:
    inicio: date = config.PERIODO_PRIORITARIO[0]
    fin: date = config.FECHA_CORTE
    provincias: list[str] = field(default_factory=list)
    distritos: list[str] = field(default_factory=list)  # UBIGEO
    estados: list[str] = field(default_factory=list)

    def describir(self) -> str:
        partes = [f"{self.inicio:%d-%m-%Y} a {self.fin:%d-%m-%Y}"]
        if self.provincias:
            partes.append(", ".join(self.provincias))
        if self.distritos:
            partes.append(f"{len(self.distritos)} distrito(s)")
        if self.estados:
            partes.append(", ".join(self.estados))
        return " · ".join(partes)


def filtros() -> Filtros:
    return st.session_state.get("filtros", Filtros())


def aplicar(datos: pd.DataFrame, f: Filtros, columna_fecha: str = "fecha_ocurrencia",
            columna_estado: str | None = "estado") -> pd.DataFrame:
    """Aplica periodo, provincias, distritos (UBIGEO, admite "a|b") y estados del evento."""
    fechas = pd.to_datetime(datos[columna_fecha])
    mascara = (fechas >= pd.Timestamp(f.inicio)) & (fechas <= pd.Timestamp(f.fin))
    if f.provincias:
        mascara &= datos["provincia"].isin(f.provincias)
    if f.distritos:
        mascara &= datos["ubigeo"].astype(str).str.split("|").apply(lambda us: bool(set(us) & set(f.distritos)))
    if f.estados and columna_estado:
        mascara &= datos[columna_estado].isin(f.estados)
    return datos[mascara]


# --- Gráficos ------------------------------------------------------------------------
def barras(datos: pd.DataFrame, x: str, y: str, horizontal: bool = False, titulo_x: str = "",
           titulo_y: str = "", texto_hover: str | None = None, alto: int = 360) -> go.Figure:
    """Barras de una sola serie (un color), marcas delgadas y esquinas redondeadas."""
    color = paleta()["categorica"][0]
    figura = go.Figure(go.Bar(
        x=datos[y] if horizontal else datos[x],
        y=datos[x] if horizontal else datos[y],
        orientation="h" if horizontal else "v",
        marker={"color": color, "line": {"width": 0}},
        hovertext=datos[texto_hover] if texto_hover else None,
        hoverinfo="text" if texto_hover else None,
    ))
    figura.update_layout(
        height=alto, margin={"l": 8, "r": 8, "t": 8, "b": 8}, bargap=0.35, barcornerradius=4,
        xaxis_title=titulo_y if horizontal else titulo_x, yaxis_title=titulo_x if horizontal else titulo_y,
        showlegend=False,
    )
    if horizontal:
        figura.update_yaxes(autorange="reversed")
    return figura


def ver_tabla(datos: pd.DataFrame, etiqueta: str = "Ver los datos del gráfico") -> None:
    """Toda figura tiene su tabla equivalente."""
    with st.expander(etiqueta):
        st.dataframe(datos, hide_index=True)


def aviso_fuente(texto: str) -> None:
    st.caption(f"Fuente: {texto}")
