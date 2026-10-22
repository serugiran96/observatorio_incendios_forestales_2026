"""Módulo de restauración: catálogo de medidas con su sustento y aplicación a cada distrito afectado.

Reglas:
- Cada medida tiene un nivel de sustento explícito: "justificada" (evidencia aplicable al ecosistema
  o a la región), "condicionada" (técnica documentada cuya ubicación o diseño requiere evaluación de
  campo o análisis satelital), "hipótesis" (sin evidencia para este contexto) o "no recomendada".
- Los ecosistemas son los PRESENTES en el distrito (MINAM); no se sabe cuáles se quemaron mientras no
  exista el análisis satelital o la ficha de campo. Por eso la aplicación a un distrito se marca
  "aplica" o "verificar en campo", nunca como diagnóstico del área quemada.
- No se recomienda reforestar pajonales ni bofedales, ni plantar especies exóticas (medida R11).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from observatorio import config

RUTA_MEDIDAS = config.DIR_REGISTRO / "medidas_restauracion.csv"

NIVELES_SUSTENTO = {
    "justificada": "Justificada por evidencia aplicable",
    "condicionada": "Condicionada a evaluación de campo o análisis satelital",
    "hipotesis": "Hipótesis que requiere evaluación de campo",
    "no_recomendada": "No recomendada",
}
COMPONENTES = {
    "humanitaria": "Atención humanitaria",
    "rehabilitacion_productiva": "Rehabilitación productiva",
    "restauracion_ecologica": "Restauración ecológica",
    "prevencion": "Prevención",
    "monitoreo": "Monitoreo",
    "no_recomendada": "No recomendada",
}
# Columna de indicadores_distrito.csv con las hectáreas de cada ecosistema objetivo
COLUMNA_ECOSISTEMA = {
    "pajonal": "ha_pajonal",
    "bofedal": "ha_bofedal",
    "bosque": "ha_bosque",
    "zona_agricola": "ha_zona_agricola",
}
UMBRAL_HA_ECOSISTEMA = 10.0  # descarta astillas de la intersección de capas
COLUMNAS_MEDIDAS = (
    "id_medida", "medida", "componente", "ecosistema_objetivo", "horizonte", "descripcion",
    "condicion_aplicacion", "nivel_sustento", "sustento", "fuentes", "indicador_monitoreo",
    "entidades_referenciales",
)


def cargar_medidas(ruta: Path = RUTA_MEDIDAS) -> pd.DataFrame:
    return pd.read_csv(ruta, dtype=str, keep_default_na=False)


def validar_medidas(medidas: pd.DataFrame, fuentes: pd.DataFrame) -> list[str]:
    """Errores del catálogo: columnas, vocabularios y fuentes inexistentes."""
    errores = [f"falta la columna {c}" for c in COLUMNAS_MEDIDAS if c not in medidas.columns]
    if errores:
        return errores
    ids_fuentes = set(fuentes["id_fuente"])
    for m in medidas.itertuples(index=False):
        if m.nivel_sustento not in NIVELES_SUSTENTO:
            errores.append(f"{m.id_medida}: nivel_sustento desconocido ({m.nivel_sustento})")
        if m.componente not in COMPONENTES:
            errores.append(f"{m.id_medida}: componente desconocido ({m.componente})")
        citadas = [f.strip() for f in m.fuentes.split(";") if f.strip()]
        if not citadas:
            errores.append(f"{m.id_medida}: sin fuentes")
        errores += [f"{m.id_medida}: fuente inexistente {f}" for f in citadas if f not in ids_fuentes]
    return errores


def _ha(fila, columna: str) -> float:
    valor = fila.get(columna)
    return 0.0 if valor is None or pd.isna(valor) else float(valor)


def _pct(ha: float, area_km2: float) -> str:
    return f"{ha:,.0f} ha ({ha / (area_km2 * 100) * 100:.0f} % del distrito)".replace(",", " ")


def aplicar_a_distrito(medida, distrito: dict, gee: dict | None = None) -> tuple[str, str] | None:
    """(estado_aplicacion, motivo) de una medida en un distrito, o None si no corresponde.

    `distrito`: fila de indicadores_distrito.csv; `gee`: fila de gee_estadisticas_distrito.csv, si existe.
    """
    objetivo = medida.ecosistema_objetivo
    if medida.nivel_sustento == "no_recomendada":
        return None
    if objetivo in ("pajonal", "bofedal", "bosque"):
        ha = _ha(distrito, COLUMNA_ECOSISTEMA[objetivo])
        if ha < UMBRAL_HA_ECOSISTEMA:
            return None
        motivo = f"{objetivo} presente en el distrito: {_pct(ha, distrito['area_km2'])}"
        estado = "verificar en campo" if medida.nivel_sustento in ("condicionada", "hipotesis") else "aplica"
        return estado, motivo + "; no se sabe si fue el ecosistema quemado"
    if objetivo == "laderas":
        if gee is None:
            return "verificar en campo", "requiere el área quemada con pendiente ≥ 30° (análisis satelital pendiente)"
        ha = _ha(gee, "ha_quemado_pendiente_30")
        if ha <= 0:
            return None
        return "verificar en campo", f"{ha:,.0f} ha de área quemada probable con pendiente ≥ 30° (satélite)"
    if objetivo == "zona_agricola":
        perdidas = {k: _ha(distrito, k) for k in ("cultivos_ha", "ganado_perdido", "ganado_afectado")}
        if any(v > 0 for v in perdidas.values()):
            detalle = ", ".join(f"{k.replace('_', ' ')}: {v:,.0f}" for k, v in perdidas.items() if v > 0)
            return "aplica", f"pérdidas agropecuarias documentadas en la EDAN ({detalle})"
        ha = _ha(distrito, "ha_zona_agricola")
        if ha >= UMBRAL_HA_ECOSISTEMA:
            return "verificar en campo", f"zona agrícola en el distrito ({_pct(ha, distrito['area_km2'])}) sin pérdidas documentadas: empadronar"
        return None
    if objetivo == "todos":
        return "aplica", f"{int(distrito['n_incendios'])} incendios en el periodo"
    return None


def medidas_por_distrito(
    indicadores: pd.DataFrame, medidas: pd.DataFrame, gee: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Tabla larga distrito × medida para los distritos con incendios en el periodo prioritario."""
    gee_por_ubigeo = {} if gee is None else {str(f["ubigeo"]): f for f in gee.to_dict("records")}
    filas = []
    for distrito in indicadores[indicadores["n_incendios"] > 0].to_dict("records"):
        for medida in medidas.itertuples(index=False):
            resultado = aplicar_a_distrito(medida, distrito, gee_por_ubigeo.get(str(distrito["ubigeo"])) if gee is not None else None)
            if resultado is None:
                continue
            estado, motivo = resultado
            filas.append({
                "ubigeo": distrito["ubigeo"],
                "provincia": distrito["provincia"],
                "distrito": distrito["distrito"],
                "n_incendios": distrito["n_incendios"],
                "cobertura_destruida_ha_edan": distrito["cobertura_destruida_ha_sin_duplicados"],
                "id_medida": medida.id_medida,
                "medida": medida.medida,
                "componente": medida.componente,
                "horizonte": medida.horizonte,
                "nivel_sustento": medida.nivel_sustento,
                "estado_aplicacion": estado,
                "motivo": motivo,
                "fuentes": medida.fuentes,
            })
    return pd.DataFrame(filas)
