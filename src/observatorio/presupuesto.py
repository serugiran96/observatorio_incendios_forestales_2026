"""Matriz de presupuesto y brechas: intervenciones por territorio con cantidades documentadas.

Reglas:
- No se inventan costos. Un costo unitario solo se usa si `costos_unitarios.csv` lo trae con su
  fuente; si no, la línea queda "pendiente de cotización" y se explica cómo estimarlo.
- Las cantidades salen de la EDAN (reportes COEN-INDECI) o del análisis satelital; si no existen,
  la cantidad queda pendiente y no se calcula un total.
- La brecha monetaria solo se calcula cuando hay costo total y recursos documentados en soles.
- Los escenarios del dashboard usan costos ingresados por quien consulta y se rotulan como supuestos.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from observatorio import config

RUTA_COSTOS = config.DIR_REGISTRO / "costos_unitarios.csv"
ESTADOS_COSTO = ("pendiente de cotización", "referencial", "cotizado")
COLUMNAS_COSTOS = (
    "id_intervencion", "intervencion", "componente", "unidad", "costo_unitario_soles", "fuente_costo",
    "estado_costo", "como_estimar", "entidades_referenciales", "fuentes_competencia",
)
SIN_COSTO = "no calculable: costo pendiente de cotización"
SIN_CANTIDAD = "no calculable: cantidad pendiente"

# Medida de restauración -> intervención presupuestal distrital (cantidad por defecto)
INTERVENCION_POR_MEDIDA = {"R03": "E01", "R01": "E02", "R04": "E03", "R06": "E04", "R10": "M01"}


def cargar_costos(ruta: Path = RUTA_COSTOS) -> pd.DataFrame:
    costos = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    costos["costo_unitario_soles"] = pd.to_numeric(costos["costo_unitario_soles"], errors="coerce")
    return costos


def validar_costos(costos: pd.DataFrame, fuentes: pd.DataFrame) -> list[str]:
    """Un costo unitario sin fuente es un error: el proyecto no inventa presupuestos."""
    errores = [f"falta la columna {c}" for c in COLUMNAS_COSTOS if c not in costos.columns]
    if errores:
        return errores
    ids_fuentes = set(fuentes["id_fuente"])
    for c in costos.itertuples(index=False):
        if c.estado_costo not in ESTADOS_COSTO:
            errores.append(f"{c.id_intervencion}: estado_costo desconocido ({c.estado_costo})")
        tiene_costo = pd.notna(c.costo_unitario_soles)
        if tiene_costo and not c.fuente_costo:
            errores.append(f"{c.id_intervencion}: costo unitario sin fuente_costo")
        if tiene_costo and c.estado_costo == "pendiente de cotización":
            errores.append(f"{c.id_intervencion}: tiene costo pero figura como pendiente de cotización")
        if not tiene_costo and c.estado_costo != "pendiente de cotización":
            errores.append(f"{c.id_intervencion}: sin costo unitario pero estado {c.estado_costo}")
        if c.fuente_costo and c.fuente_costo not in ids_fuentes:
            errores.append(f"{c.id_intervencion}: fuente_costo inexistente {c.fuente_costo}")
        if not c.como_estimar:
            errores.append(f"{c.id_intervencion}: falta explicar cómo estimar el costo")
    return errores


def _recursos_productivos(evidencias: pd.DataFrame, provincia: str, distrito: str) -> list[str]:
    """Entregas en especie documentadas (p. ej., semillas del INIA) del mismo distrito o provincia."""
    entregas = evidencias[(evidencias["categoria"] == "ayuda_entregada") & (evidencias["provincia"] == provincia)]
    textos = []
    for e in entregas.itertuples(index=False):
        if str(e.distrito) == distrito:
            textos.append(f"{e.descripcion} [{e.id_evidencia}]")
        elif str(e.distrito) in ("", "nan"):
            textos.append(f"(nivel provincial) {e.descripcion} [{e.id_evidencia}]")
    return textos


def _anuncios(evidencias: pd.DataFrame, provincia: str, distrito: str) -> list[str]:
    anuncios = evidencias[evidencias["categoria"] == "ayuda_anunciada"]
    textos = []
    for e in anuncios.itertuples(index=False):
        distritos = [d for d in str(e.distrito).split("|") if d and d != "nan"]
        if e.provincia == provincia and distrito in distritos:
            textos.append(f"{e.descripcion} [{e.id_evidencia}; entrega no verificada]")
        elif str(e.provincia) in ("", "nan"):
            textos.append(f"(regional) {e.descripcion} [{e.id_evidencia}; entrega no verificada]")
    return textos


def _linea(costo: pd.Series, territorio: dict, problema: str, beneficiarios: str, cantidad, fuente_cantidad: str,
           recursos: list[str], anuncios: list[str], estado_atencion: str = "") -> dict:
    unitario = costo["costo_unitario_soles"]
    total = cantidad * unitario if pd.notna(cantidad) and pd.notna(unitario) else float("nan")
    brecha_soles = float("nan")
    if pd.isna(cantidad):
        brecha = SIN_CANTIDAD
    elif pd.isna(unitario):
        brecha = SIN_COSTO
    elif recursos:
        brecha = "no calculable: hay recursos documentados sin valor en soles"
    else:
        brecha_soles, brecha = total, "costo total sin recursos documentados"
    return {
        "componente": costo["componente"],
        "id_intervencion": costo["id_intervencion"],
        "intervencion": costo["intervencion"],
        **territorio,
        "problema": problema,
        "beneficiarios": beneficiarios,
        "cantidad": cantidad,
        "unidad": costo["unidad"],
        "fuente_cantidad": fuente_cantidad,
        "costo_unitario_soles": unitario,
        "estado_costo": costo["estado_costo"],
        "fuente_costo": costo["fuente_costo"],
        "costo_total_soles": total,
        "estado_atencion": estado_atencion,
        "recursos_documentados": " | ".join(recursos),
        "donaciones_o_anuncios": " | ".join(anuncios),
        "brecha": brecha,
        "brecha_soles": brecha_soles,
        "entidades_competentes": costo["entidades_referenciales"],
        "fuentes_competencia": costo["fuentes_competencia"],
        "como_estimar": costo["como_estimar"],
    }


def construir_matriz(
    matriz_atencion: pd.DataFrame,
    medidas_distrito: pd.DataFrame,
    costos: pd.DataFrame,
    evidencias: pd.DataFrame,
    gee: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Líneas de intervención: humanitarias y productivas por incendio; ecológicas por distrito."""
    costo = costos.set_index("id_intervencion", drop=False)
    manuales = evidencias[~evidencias["id_evidencia"].str.match(r"E-(OGRD|INDECI)-")]
    filas = []

    # 1) Por incendio: atención humanitaria y rehabilitación productiva (cantidades de la EDAN)
    for f in matriz_atencion.to_dict("records"):
        territorio = {
            "provincia": f["provincia"], "distrito": f.get("distrito_oficial") or f["distrito"],
            "ubigeo": f["ubigeo"], "localidad": f["localidad"], "id_evento": f["id_evento"],
        }
        fuente = f"EDAN en {f['fuentes']}"
        entregado = [f["ayuda_entregada_con_evidencia"]] if f["ayuda_entregada_con_evidencia"] else []
        anuncios = _anuncios(manuales, f["provincia"], f["distrito"])
        valor = lambda col: 0 if pd.isna(f[col]) else f[col]  # noqa: E731
        if valor("personas_damnificadas") > 0:
            n = valor("personas_damnificadas")
            filas.append(_linea(costo.loc["H01"], territorio, "Personas damnificadas", f"{n:.0f} personas", n,
                                fuente, entregado, anuncios, f["estado_atencion"]))
        viviendas = valor("viviendas_inhabitables") + valor("viviendas_destruidas")
        if viviendas > 0:
            filas.append(_linea(costo.loc["H02"], territorio, "Viviendas inhabitables o destruidas",
                                f"{viviendas:.0f} viviendas", viviendas, fuente, entregado, anuncios, f["estado_atencion"]))
        if valor("personas_lesionadas") > 0:
            n = valor("personas_lesionadas")
            filas.append(_linea(costo.loc["H03"], territorio, "Personas lesionadas", f"{n:.0f} personas", n,
                                fuente, entregado, [], f["estado_atencion"]))
        productivos = entregado + _recursos_productivos(manuales, f["provincia"], f["distrito"])
        if valor("cultivos_ha") > 0:
            filas.append(_linea(costo.loc["P01"], territorio, "Cultivos perdidos o afectados",
                                "familias productoras (número no publicado)", valor("cultivos_ha"), fuente,
                                productivos, anuncios, f["estado_atencion"]))
        ganado = valor("ganado_perdido") + valor("ganado_afectado")
        if ganado > 0:
            filas.append(_linea(costo.loc["P02"], territorio, "Ganado perdido o afectado",
                                "familias criadoras (número no publicado)", ganado, fuente, productivos, anuncios,
                                f["estado_atencion"]))

    # 2) Por distrito: restauración ecológica y monitoreo
    gee_por_ubigeo = {} if gee is None else gee.set_index(gee["ubigeo"].astype(str)).to_dict("index")
    for m in medidas_distrito.to_dict("records"):
        id_intervencion = INTERVENCION_POR_MEDIDA.get(m["id_medida"])
        if id_intervencion is None:
            continue
        territorio = {"provincia": m["provincia"], "distrito": m["distrito"], "ubigeo": m["ubigeo"],
                      "localidad": "", "id_evento": ""}
        cantidad, fuente_cantidad = float("nan"), "pendiente"
        if id_intervencion == "E01" and m["ubigeo"] in gee_por_ubigeo:
            cantidad = gee_por_ubigeo[m["ubigeo"]].get("ha_quemado_pendiente_30", float("nan"))
            fuente_cantidad = "análisis satelital (área quemada probable con pendiente ≥ 30°)"
        elif id_intervencion == "E01":
            fuente_cantidad = "pendiente: requiere análisis satelital"
        elif id_intervencion == "E02" and m["cobertura_destruida_ha_edan"] > 0:
            cantidad = m["cobertura_destruida_ha_edan"]
            fuente_cantidad = "EDAN: cobertura natural destruida (referencia; incluye ecosistemas distintos al pajonal)"
        elif id_intervencion == "E04":
            fuente_cantidad = "pendiente: superficie de bosque quemado no publicada"
        elif id_intervencion in ("E03", "M01"):
            cantidad, fuente_cantidad = 1.0, "un distrito"
        filas.append(_linea(costo.loc[id_intervencion], territorio, m["motivo"], "comunidades del distrito",
                            cantidad, fuente_cantidad, [], []))

    matriz = pd.DataFrame(filas)
    matriz.insert(0, "id_linea", [f"L-{i:04d}" for i in range(1, len(matriz) + 1)])
    return matriz


def recursos_de_contexto(evidencias: pd.DataFrame) -> pd.DataFrame:
    """Presupuestos documentados que no se pueden asignar a una línea (proyectos y programas regionales)."""
    filas = evidencias[evidencias["variable"] == "presupuesto_asignado"].copy()
    filas["monto_soles"] = pd.to_numeric(filas["valor"], errors="coerce")
    return filas[["id_evidencia", "id_fuente", "descripcion", "monto_soles", "estado_verificacion"]]


def escenario(matriz: pd.DataFrame, costos_supuestos: dict[str, float]) -> pd.DataFrame:
    """Totales por componente con costos unitarios SUPUESTOS (los ingresa quien consulta el tablero).

    Las líneas sin cantidad se cuentan aparte: no se suman.
    """
    base = matriz.copy()
    base["costo_supuesto"] = base["id_intervencion"].map(costos_supuestos)
    con_todo = base["cantidad"].notna() & base["costo_supuesto"].notna()
    base["total_escenario"] = (base["cantidad"] * base["costo_supuesto"]).where(con_todo)
    resumen = base.groupby(["componente", "id_intervencion", "intervencion"], as_index=False).agg(
        lineas=("id_linea", "count"),
        lineas_sin_cantidad=("cantidad", lambda s: int(s.isna().sum())),
        cantidad_total=("cantidad", "sum"),
        costo_unitario_supuesto=("costo_supuesto", "first"),
        total_escenario_soles=("total_escenario", lambda s: s.sum(min_count=1)),
    )
    return resumen
