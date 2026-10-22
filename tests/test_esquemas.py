"""Pruebas de coherencia interna de los vocabularios controlados."""

from observatorio import esquemas


def test_seis_estados_de_verificacion():
    assert len(esquemas.ESTADOS_VERIFICACION) == 6


def test_cada_categoria_tiene_estados_permitidos_validos():
    assert set(esquemas.ESTADOS_PERMITIDOS_POR_CATEGORIA) == set(esquemas.CATEGORIAS_EVIDENCIA)
    for estados in esquemas.ESTADOS_PERMITIDOS_POR_CATEGORIA.values():
        assert estados <= set(esquemas.ESTADOS_VERIFICACION)


def test_informacion_insuficiente_siempre_permitida():
    # Toda afirmación ambigua debe poder marcarse como información insuficiente
    for estados in esquemas.ESTADOS_PERMITIDOS_POR_CATEGORIA.values():
        assert "informacion_insuficiente" in estados


def test_ayuda_anunciada_nunca_cuenta_como_atencion_documentada():
    assert "atencion_documentada" not in esquemas.ESTADOS_PERMITIDOS_POR_CATEGORIA["ayuda_anunciada"]


def test_variables_apuntan_a_categorias_existentes():
    assert set(esquemas.VARIABLES.values()) <= set(esquemas.CATEGORIAS_EVIDENCIA)


def test_trece_provincias_de_cusco():
    assert len(esquemas.PROVINCIAS_CUSCO) == 13
    assert len(set(esquemas.PROVINCIAS_CUSCO)) == 13


def test_obligatorias_son_columnas_existentes():
    assert set(esquemas.OBLIGATORIAS_FUENTES) <= set(esquemas.COLUMNAS_FUENTES)
    assert set(esquemas.OBLIGATORIAS_EVIDENCIAS) <= set(esquemas.COLUMNAS_EVIDENCIAS)


def test_todas_las_variables_tienen_etiqueta():
    assert set(esquemas.VARIABLES) | {esquemas.VARIABLE_CUALITATIVA} <= set(esquemas.ETIQUETAS_VARIABLES)
