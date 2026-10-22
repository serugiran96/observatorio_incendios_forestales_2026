"""Pruebas de validación del registro de evidencias con casos sintéticos.

Los datos de estas pruebas son ficticios y existen solo para ejercitar las reglas;
no se escriben en data/ ni se muestran en el dashboard.
"""

import pandas as pd
import pytest

from observatorio import config, esquemas
from observatorio import evidencias as ev


def _fuentes(**cambios) -> pd.DataFrame:
    fila = {
        "id_fuente": "F-TEST",
        "institucion": "Institución de prueba",
        "titulo": "Documento de prueba",
        "url": "https://ejemplo.org/doc",
        "tipo_fuente": "oficial_nacional",
        "fecha_publicacion": "2026-10-10",
        "fecha_consulta": "2026-10-21",
        "accesible": "si",
        "archivo_local": "",
        "notas": "",
    }
    fila.update(cambios)
    return pd.DataFrame([fila], columns=esquemas.COLUMNAS_FUENTES)


def _evidencia(**cambios) -> pd.DataFrame:
    fila = {
        "id_evidencia": "E-TEST",
        "id_fuente": "F-TEST",
        "fecha_evento": "2026-10-05",
        "provincia": "Canchis",
        "distrito": "Sicuani",
        "localidad": "",
        "ubigeo": "",
        "latitud": "",
        "longitud": "",
        "precision_geografica": "distrito",
        "categoria": "dano_ambiental",
        "variable": "superficie_afectada",
        "valor": "100",
        "unidad": "ha",
        "descripcion": "Texto de prueba",
        "estado_verificacion": "dano_reportado_pendiente",
        "nivel_confianza": "media",
        "fuente_oficial_citada": "",
        "observaciones": "",
    }
    fila.update(cambios)
    return pd.DataFrame([fila], columns=esquemas.COLUMNAS_EVIDENCIAS)


def _errores(**cambios) -> list[str]:
    return ev.validar_evidencias(_evidencia(**cambios), _fuentes()).errores


def test_registro_valido_no_tiene_errores():
    assert _errores() == []


def test_fuente_inexistente():
    assert any("no existe en fuentes" in e for e in _errores(id_fuente="F-OTRA"))


@pytest.mark.parametrize(
    "categoria, estado",
    [
        ("ayuda_anunciada", "atencion_documentada"),  # anuncio no es entrega
        ("dano_humano", "atencion_documentada"),
        ("necesidad", "dano_confirmado"),
    ],
)
def test_estado_incoherente_con_categoria(categoria, estado):
    errores = _errores(categoria=categoria, estado_verificacion=estado, variable="descripcion_cualitativa", valor="", unidad="")
    assert any("no corresponde a la categoría" in e for e in errores)


def test_variable_de_otra_categoria():
    assert any("pertenece a" in e for e in _errores(variable="personas_fallecidas"))


def test_provincia_fuera_de_cusco():
    assert any("no pertenece a Cusco" in e for e in _errores(provincia="Arequipa"))


def test_dato_regional_no_exige_provincia():
    assert _errores(precision_geografica="region", provincia="", distrito="") == []


def test_centro_poblado_exige_localidad():
    assert any("exige localidad" in e for e in _errores(precision_geografica="centro_poblado"))


def test_coordenadas_fuera_de_cusco():
    errores = _errores(precision_geografica="punto", localidad="X", latitud="-12.05", longitud="-77.04")  # Lima
    assert any("fuera de la región Cusco" in e for e in errores)


def test_ubigeo_de_otro_departamento():
    assert any("ubigeo" in e for e in _errores(ubigeo="150101"))


def test_valor_sin_unidad_y_valor_no_numerico():
    assert any("sin unidad" in e for e in _errores(unidad=""))
    assert any("no es numérico" in e for e in _errores(valor="cien"))


def test_evento_posterior_a_publicacion():
    assert any("posterior a la publicación" in e for e in _errores(fecha_evento="2026-10-15"))


@pytest.mark.parametrize("texto", ["DNI 12345678 del afectado", "llamar al 987 654 321"])
def test_detecta_datos_personales(texto):
    assert any("dato personal" in e for e in _errores(descripcion=texto))


@pytest.mark.parametrize("texto", ["1 500 ha afectadas", "S/ 12,500,000 asignados", "2026-10-05"])
def test_no_confunde_cifras_con_datos_personales(texto):
    assert not ev.contiene_dato_personal(texto)


def test_fuente_publicada_despues_de_consultada():
    resultado = ev.validar_fuentes(_fuentes(fecha_publicacion="2026-10-25"))
    assert any("posterior a fecha_consulta" in e for e in resultado.errores)


def test_union_con_fuentes_agrega_enlace():
    unidas = ev.unir_con_fuentes(_evidencia(), _fuentes())
    assert unidas.loc[0, "url"] == "https://ejemplo.org/doc"


def test_registro_real_del_repositorio_es_valido():
    """El registro versionado en data/raw/registro debe pasar siempre la validación."""
    fuentes = ev.cargar_fuentes(config.RUTA_FUENTES)
    assert ev.validar_fuentes(fuentes).es_valido
    assert ev.validar_evidencias(ev.cargar_evidencias(config.RUTA_EVIDENCIAS), fuentes).es_valido
    assert ev.validar_vacios(ev.cargar_vacios(config.RUTA_VACIOS)).es_valido
