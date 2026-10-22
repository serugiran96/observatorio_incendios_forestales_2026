"""Matriz de atención inmediata: criterios explícitos, estados de atención y no atribución de ayuda provincial.

Los incendios sintéticos de este archivo son ficticios: sirven para ejercitar las reglas y no se guardan en data/.
"""

from datetime import date

import pandas as pd
import pytest

from observatorio import atencion, config, esquemas

COLUMNAS_INVENTARIO = [
    "id_evento", "fuente_principal", "provincia", "distrito", "localidad", "fecha_ocurrencia", "estado",
    "ultimo_reporte", "fecha_ultimo_reporte", "cobertura_natural_destruida_ha", "personas_fallecidas",
    "personas_lesionadas", "personas_damnificadas", "personas_afectadas", "viviendas_afectadas",
    "viviendas_inhabitables", "viviendas_destruidas", "ganado_perdido", "ganado_afectado", "cultivos_ha",
    "tabla_danos_no_legible", "entrega_bah_documentada", "rubros_bah", "atencion_medica_documentada",
    "insumos_pecuarios_documentados", "ayuda_solicitada", "posibles_duplicados", "ubigeo", "alias_por_verificar",
    "varios_distritos",
]


def _evento(id_evento, **cambios):
    base = dict.fromkeys(COLUMNAS_INVENTARIO, "")
    base.update({
        "id_evento": id_evento, "fuente_principal": "COEN-INDECI", "provincia": "Canas", "distrito": "Quehue",
        "fecha_ocurrencia": "2026-10-01", "estado": "cerrado (emergencia atendida)",
        "ultimo_reporte": f"F-INDECI-RC{id_evento[-2:]}", "fecha_ultimo_reporte": "2026-10-05",
        "tabla_danos_no_legible": "False", "entrega_bah_documentada": "False",
        "atencion_medica_documentada": "False", "insumos_pecuarios_documentados": "False",
        "ayuda_solicitada": "False", "ubigeo": "080406", "alias_por_verificar": "False", "varios_distritos": "False",
    })
    base.update(cambios)
    return base


def _matriz(eventos, evidencias=None, acciones=None):
    inventario = pd.DataFrame(eventos, columns=COLUMNAS_INVENTARIO)
    acciones = acciones if acciones is not None else pd.DataFrame(
        columns=["id_evento", "id_fuente", "fecha", "nivel", "entidad", "tipo", "texto"])
    evidencias = evidencias if evidencias is not None else pd.DataFrame(
        columns=["id_evidencia", "id_fuente", "provincia", "distrito", "categoria", "descripcion"])
    fuentes = pd.DataFrame({"id_fuente": ["F-0001"], "archivo_local": [""]})
    return atencion.construir_matriz(inventario, acciones, evidencias, fuentes,
                                     periodo=(date(2026, 9, 1), date(2026, 10, 21)), fecha_corte=date(2026, 10, 21))


def test_damnificados_sin_entrega_documentada_es_atencion_no_verificada():
    m = _matriz([_evento("INDECI-01", personas_damnificadas="6", estado="abierto al último reporte")])
    fila = m.iloc[0]
    assert fila["estado_atencion"] == "atencion_no_verificada"
    assert fila["c_sin_bah_documentada"] and fila["seguimiento_humanitario"] and fila["verificar_atencion"]
    assert "No implica que no se haya entregado" in fila["necesidades_pendientes"]


def test_entrega_documentada_cambia_el_estado():
    m = _matriz([_evento("INDECI-02", personas_damnificadas="24", entrega_bah_documentada="True",
                         rubros_bah="abrigo, alimentos")])
    assert m.iloc[0]["estado_atencion"] == "atencion_documentada"
    assert not m.iloc[0]["c_sin_bah_documentada"]
    assert "abrigo, alimentos" in m.iloc[0]["ayuda_entregada_con_evidencia"]


def test_solo_cobertura_no_requiere_seguimiento_humanitario():
    m = _matriz([_evento("INDECI-03", cobertura_natural_destruida_ha="15")])
    assert m.iloc[0]["estado_atencion"] == "sin daños a personas reportados"
    assert not m.iloc[0]["seguimiento_humanitario"]


def test_sin_actualizacion_usa_el_umbral_desde_la_fecha_de_corte():
    viejo = _evento("INDECI-04", estado="abierto al último reporte", fecha_ultimo_reporte="2026-09-20")
    reciente = _evento("INDECI-05", estado="abierto al último reporte", fecha_ultimo_reporte="2026-10-15")
    m = _matriz([viejo, reciente]).set_index("id_evento")
    assert m.loc["INDECI-04", "c_sin_actualizacion"] and m.loc["INDECI-04", "dias_sin_actualizacion"] == 31
    assert not m.loc["INDECI-05", "c_sin_actualizacion"]


def test_ayuda_provincial_no_se_atribuye_a_un_incendio():
    evidencias = pd.DataFrame([
        {"id_evidencia": "E-9001", "id_fuente": "F-0001", "provincia": "Canas", "distrito": "",
         "categoria": "ayuda_entregada", "descripcion": "Entrega de semillas en la provincia"},
        {"id_evidencia": "E-9002", "id_fuente": "F-0001", "provincia": "Canas", "distrito": "Quehue",
         "categoria": "ayuda_anunciada", "descripcion": "Anuncio para Quehue"},
    ])
    m = _matriz([_evento("INDECI-06", personas_damnificadas="3")], evidencias=evidencias)
    fila = m.iloc[0]
    # La entrega provincial se muestra rotulada y no convierte la atención en documentada
    assert "(nivel provincial, no atribuible a este incendio)" in fila["ayuda_entregada_con_evidencia"]
    assert fila["estado_atencion"] == "atencion_no_verificada"
    assert "Anuncio para Quehue" in fila["ayuda_anunciada"]


def test_fuera_del_periodo_no_entra_en_la_matriz():
    m = _matriz([_evento("INDECI-07", fecha_ocurrencia="2026-08-15"), _evento("INDECI-08")])
    assert list(m["id_evento"]) == ["INDECI-08"]


def test_no_hay_puntaje_ni_ranking():
    m = _matriz([_evento("INDECI-09", personas_damnificadas="2")])
    assert not any(c in m.columns for c in ("puntaje", "ranking", "prioridad", "score"))
    for codigo in atencion.CRITERIOS:
        assert m[codigo].dtype == bool


RUTA = config.DIR_PROCESSED / "matriz_atencion_inmediata.csv"


@pytest.mark.skipif(not RUTA.exists(), reason="ejecute scripts/construir_matrices.py")
def test_matriz_procesada_es_coherente():
    m = pd.read_csv(RUTA, dtype={"ubigeo": str})
    validos = set(esquemas.ESTADOS_VERIFICACION) | {"sin daños a personas reportados"}
    assert set(m["estado_atencion"]) <= validos
    assert set(m["estado_danos"]) <= set(esquemas.ESTADOS_VERIFICACION)
    # Toda atención no verificada tiene un daño humano o productivo que la motive
    assert m.loc[m["estado_atencion"] == "atencion_no_verificada", "seguimiento_humanitario"].all()
    assert m["id_evento"].is_unique
