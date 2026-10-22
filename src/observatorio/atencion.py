"""Matriz de atención inmediata (horizonte 0–90 días): una fila por incendio del periodo prioritario.

Reglas (ver docs/criterios_verificacion.md):
- No se calcula un puntaje ni un ranking. Cada incendio lleva criterios explícitos (verdadero/falso)
  y dos marcas derivadas: "seguimiento humanitario" (hay daños a personas, viviendas o medios de vida)
  y "verificar atención" (la información pública no permite confirmar la atención).
- Que no haya registro público de una entrega no prueba que no se entregó: en ese caso el estado
  es "atención no verificada", nunca "sin atención".
- La ayuda anunciada a nivel provincial se muestra aparte y no se atribuye a un incendio concreto.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from observatorio import config

UMBRAL_DIAS_SIN_ACTUALIZACION = 14

# código -> (etiqueta, grupo)
CRITERIOS = {
    "c_victimas": ("Personas fallecidas o lesionadas", "seguimiento humanitario"),
    "c_vivienda": ("Personas damnificadas o viviendas inhabitables o destruidas", "seguimiento humanitario"),
    "c_medios_vida": ("Cultivos o ganado perdidos o afectados", "seguimiento humanitario"),
    "c_sin_bah_documentada": ("Damnificados sin entrega de BAH documentada", "verificar atención"),
    "c_lesionados_sin_atencion_documentada": ("Lesionados sin atención médica documentada en el reporte", "verificar atención"),
    "c_sin_actualizacion": (f"Abierto y sin actualización pública en más de {UMBRAL_DIAS_SIN_ACTUALIZACION} días",
                            "verificar atención"),
    "c_informacion_incompleta": ("Tabla de daños ilegible, sin reporte COEN localizado o distrito por verificar",
                                 "verificar atención"),
    "c_abierto": ("Abierto al último reporte", "contexto"),
    "c_posible_duplicado": ("Posible duplicado de otro registro", "contexto"),
}

_NUMERICAS = [
    "cobertura_natural_destruida_ha", "personas_fallecidas", "personas_lesionadas", "personas_damnificadas",
    "personas_afectadas", "viviendas_afectadas", "viviendas_inhabitables", "viviendas_destruidas",
    "ganado_perdido", "ganado_afectado", "cultivos_ha",
]
_BOOLEANAS = [
    "entrega_bah_documentada", "atencion_medica_documentada", "insumos_pecuarios_documentados",
    "ayuda_solicitada", "tabla_danos_no_legible", "alias_por_verificar", "varios_distritos",
]
_TIPOS_ATENCION = ("entrega_bah", "atencion_medica", "insumos_pecuarios")
_ENTIDADES_EQUIVALENTES = {"COEN – INDECI": "COEN-INDECI", "COEN - INDECI": "COEN-INDECI"}


def _a_bool(serie: pd.Series) -> pd.Series:
    return serie.map(lambda v: str(v).strip().lower() == "true")


def preparar_inventario(inventario: pd.DataFrame) -> pd.DataFrame:
    """Tipa el inventario georreferenciado (números y booleanos)."""
    inv = inventario.copy()
    for col in _NUMERICAS:
        inv[col] = pd.to_numeric(inv[col], errors="coerce")
    for col in _BOOLEANAS:
        inv[col] = _a_bool(inv[col])
    inv["fecha_ocurrencia"] = pd.to_datetime(inv["fecha_ocurrencia"], errors="coerce")
    inv["fecha_ultimo_reporte"] = pd.to_datetime(inv["fecha_ultimo_reporte"], errors="coerce")
    return inv


def _numero(valor) -> str:
    return f"{valor:,.0f}".replace(",", " ") if float(valor).is_integer() else f"{valor:,.1f}".replace(",", " ")


def _resumen_cifras(fila, columnas: dict[str, str]) -> str:
    partes = [f"{etiqueta}: {_numero(fila[col])}" for col, etiqueta in columnas.items()
              if pd.notna(fila[col]) and fila[col] > 0]
    return "; ".join(partes)


def resumen_danos(fila) -> str:
    texto = _resumen_cifras(fila, {
        "cobertura_natural_destruida_ha": "cobertura natural destruida (ha)",
        "viviendas_afectadas": "viviendas afectadas",
        "viviendas_inhabitables": "viviendas inhabitables",
        "viviendas_destruidas": "viviendas destruidas",
    })
    if fila["tabla_danos_no_legible"]:
        texto = (texto + "; " if texto else "") + "tabla de daños del reporte ilegible"
    return texto or "sin cifras de daños en el reporte"


def resumen_personas_medios_vida(fila) -> str:
    return _resumen_cifras(fila, {
        "personas_fallecidas": "fallecidas",
        "personas_lesionadas": "lesionadas",
        "personas_damnificadas": "damnificadas",
        "personas_afectadas": "afectadas",
        "cultivos_ha": "cultivos (ha)",
        "ganado_perdido": "ganado perdido",
        "ganado_afectado": "ganado afectado",
    })


def _id_fuentes_ogrd(fuentes: pd.DataFrame) -> dict[str, str]:
    """Nombre de archivo PDF del reporte OGRD -> id_fuente."""
    locales = fuentes.dropna(subset=["archivo_local"])
    return {Path(r).name: i for i, r in zip(locales["id_fuente"], locales["archivo_local"]) if r}


def _evidencias_territoriales(evidencias: pd.DataFrame, categoria: str) -> pd.DataFrame:
    """Evidencias manuales (no extraídas de reportes) de una categoría, con provincia identificada."""
    manuales = evidencias[~evidencias["id_evidencia"].str.match(r"E-(OGRD|INDECI)-")]
    return manuales[(manuales["categoria"] == categoria) & manuales["provincia"].fillna("").ne("")]


def _textos_para(evidencias: pd.DataFrame, provincia: str, distrito: str) -> tuple[list[str], list[str]]:
    """Separa evidencias del mismo distrito y de nivel provincial (sin distrito)."""
    en_distrito, en_provincia = [], []
    for ev in evidencias[evidencias["provincia"] == provincia].itertuples(index=False):
        distritos = [d for d in str(ev.distrito or "").split("|") if d and d != "nan"]
        texto = f"{ev.descripcion} [{ev.id_evidencia}, {ev.id_fuente}]"
        if distrito in distritos:
            en_distrito.append(texto)
        elif not distritos:
            en_provincia.append(f"(nivel provincial, no atribuible a este incendio) {texto}")
    return en_distrito, en_provincia


def _acciones_por_evento(acciones: pd.DataFrame) -> dict[str, pd.DataFrame]:
    acc = acciones.copy()
    acc["entidad"] = acc["entidad"].replace(_ENTIDADES_EQUIVALENTES)
    return {f"INDECI-{k}": g.sort_values("fecha") for k, g in acc.groupby("id_evento")}


def construir_matriz(
    inventario: pd.DataFrame,
    acciones: pd.DataFrame,
    evidencias: pd.DataFrame,
    fuentes: pd.DataFrame,
    corroboracion: pd.DataFrame | None = None,
    nombres_oficiales: dict[str, str] | None = None,
    periodo: tuple[date, date] = config.PERIODO_PRIORITARIO,
    fecha_corte: date = config.FECHA_CORTE,
) -> pd.DataFrame:
    """Matriz de atención inmediata para los incendios con fecha de ocurrencia dentro del periodo.

    `nombres_oficiales`: UBIGEO -> nombre oficial del distrito (unifica variantes como "San Sebastian").
    """
    inv = preparar_inventario(inventario)
    inicio, fin = (pd.Timestamp(f) for f in periodo)
    inv = inv[(inv["fecha_ocurrencia"] >= inicio) & (inv["fecha_ocurrencia"] <= fin)].copy()

    por_evento = _acciones_por_evento(acciones)
    ogrd_a_fuente = _id_fuentes_ogrd(fuentes)
    anunciadas = _evidencias_territoriales(evidencias, "ayuda_anunciada")
    entregadas = _evidencias_territoriales(evidencias, "ayuda_entregada")
    necesidades = _evidencias_territoriales(evidencias, "necesidad")
    focos = None
    if corroboracion is not None and len(corroboracion):
        focos = corroboracion.set_index("id_evento")["focos_en_ventana"]

    filas = []
    for _, f in inv.iterrows():
        acc = por_evento.get(f["id_evento"], acciones.iloc[0:0])
        cero = lambda col: 0 if pd.isna(f[col]) else f[col]  # noqa: E731
        c = {
            "c_victimas": cero("personas_fallecidas") + cero("personas_lesionadas") > 0,
            "c_vivienda": cero("personas_damnificadas") + cero("viviendas_inhabitables") + cero("viviendas_destruidas") > 0,
            "c_medios_vida": cero("cultivos_ha") + cero("ganado_perdido") + cero("ganado_afectado") > 0,
            "c_abierto": f["estado"] == "abierto al último reporte",
            "c_posible_duplicado": isinstance(f["posibles_duplicados"], str) and bool(f["posibles_duplicados"]),
        }
        c["c_sin_bah_documentada"] = c["c_vivienda"] and not f["entrega_bah_documentada"]
        c["c_lesionados_sin_atencion_documentada"] = cero("personas_lesionadas") > 0 and not f["atencion_medica_documentada"]
        dias = (pd.Timestamp(fecha_corte) - f["fecha_ultimo_reporte"]).days if pd.notna(f["fecha_ultimo_reporte"]) else None
        c["c_sin_actualizacion"] = c["c_abierto"] and dias is not None and dias > UMBRAL_DIAS_SIN_ACTUALIZACION
        c["c_informacion_incompleta"] = bool(
            f["tabla_danos_no_legible"] or f["fuente_principal"].startswith("OGRD") or f["alias_por_verificar"])

        # Fuentes del evento
        ids = set(acc["id_fuente"]) if len(acc) else set()
        ultimo = str(f["ultimo_reporte"])
        ids.add(ultimo if ultimo.startswith("F-") else ogrd_a_fuente.get(ultimo, ultimo))

        # Atención documentada, anunciada y necesidades
        atenciones = [f"{a.fecha}: {a.texto} ({a.entidad})" for a in acc.itertuples() if a.tipo in _TIPOS_ATENCION]
        if f["entrega_bah_documentada"] and isinstance(f["rubros_bah"], str):
            atenciones.append(f"Rubros de BAH entregados según el anexo del reporte: {f['rubros_bah']}")
        ent_d, ent_p = _textos_para(entregadas, f["provincia"], f["distrito"])
        anu_d, anu_p = _textos_para(anunciadas, f["provincia"], f["distrito"])
        nec_d, nec_p = _textos_para(necesidades, f["provincia"], f["distrito"])
        solicitudes = [f"{a.fecha}: {a.texto} ({a.entidad})" for a in acc.itertuples() if a.tipo == "solicitud_ayuda"]

        documentada = bool(f["entrega_bah_documentada"] or f["atencion_medica_documentada"]
                           or f["insumos_pecuarios_documentados"] or ent_d)
        if documentada:
            estado_atencion = "atencion_documentada"
        elif c["c_victimas"] or c["c_vivienda"] or c["c_medios_vida"]:
            estado_atencion = "atencion_no_verificada"
        elif solicitudes or nec_d:
            estado_atencion = "necesidad_pendiente_documentada"
        else:
            estado_atencion = "sin daños a personas reportados"

        pendientes = []
        if c["c_sin_bah_documentada"]:
            pendientes.append(
                f"{resumen_personas_medios_vida(f)}: sin entrega de BAH documentada al último reporte "
                f"({f['fecha_ultimo_reporte']:%d-%m-%Y}). No implica que no se haya entregado.")
        if c["c_lesionados_sin_atencion_documentada"]:
            pendientes.append("Personas lesionadas sin atención médica descrita en el reporte.")
        if c["c_medios_vida"] and not f["insumos_pecuarios_documentados"]:
            pendientes.append("Pérdidas agropecuarias sin apoyo productivo documentado.")

        fila = {
            "id_evento": f["id_evento"],
            "provincia": f["provincia"],
            "distrito": f["distrito"],
            "distrito_oficial": " / ".join(
                (nombres_oficiales or {}).get(u, u) for u in str(f["ubigeo"]).split("|")),
            "ubigeo": f["ubigeo"],
            "localidad": f["localidad"] if isinstance(f["localidad"], str) else "",
            "fecha_ocurrencia": f["fecha_ocurrencia"].date().isoformat(),
            "estado_evento": f["estado"],
            "danos": resumen_danos(f),
            "personas_y_medios_de_vida": resumen_personas_medios_vida(f),
            "necesidades_documentadas": " | ".join(solicitudes + nec_d + nec_p),
            "ayuda_anunciada": " | ".join(anu_d + anu_p),
            "ayuda_entregada_con_evidencia": " | ".join(atenciones + ent_d + ent_p),
            "necesidades_pendientes": " | ".join(pendientes),
            "instituciones": "; ".join(sorted(set(acc["entidad"].dropna()))) if len(acc) else "",
            "ultima_actualizacion": f["fecha_ultimo_reporte"].date().isoformat() if pd.notna(f["fecha_ultimo_reporte"]) else "",
            "dias_sin_actualizacion": dias,
            "fuentes": "; ".join(sorted(ids)),
            "estado_danos": "informacion_insuficiente" if f["tabla_danos_no_legible"] else "dano_confirmado",
            "estado_atencion": estado_atencion,
            "fuente_principal": f["fuente_principal"],
        }
        for col in _NUMERICAS:
            fila[col] = f[col]
        fila.update(c)
        fila["seguimiento_humanitario"] = any(c[k] for k, (_, g) in CRITERIOS.items() if g == "seguimiento humanitario")
        fila["verificar_atencion"] = any(c[k] for k, (_, g) in CRITERIOS.items() if g == "verificar atención")
        fila["motivos"] = "; ".join(CRITERIOS[k][0] for k in CRITERIOS if c[k])
        if focos is not None:
            fila["focos_calor_en_ventana"] = focos.get(f["id_evento"])
        filas.append(fila)

    matriz = pd.DataFrame(filas)
    return matriz.sort_values(
        ["verificar_atencion", "seguimiento_humanitario", "fecha_ocurrencia"], ascending=[False, False, False]
    ).reset_index(drop=True)


def ayuda_regional(evidencias: pd.DataFrame) -> pd.DataFrame:
    """Ayuda anunciada o entregada sin provincia identificada (no atribuible a un territorio)."""
    manuales = evidencias[~evidencias["id_evidencia"].str.match(r"E-(OGRD|INDECI)-")]
    sin_territorio = manuales["provincia"].fillna("").eq("")
    return manuales[sin_territorio & manuales["categoria"].isin(["ayuda_anunciada", "ayuda_entregada"])]
