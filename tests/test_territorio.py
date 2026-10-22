"""Pruebas de los límites oficiales y de la asignación de UBIGEO."""

from observatorio import esquemas, territorio


def test_limites_oficiales_de_cusco():
    distritos = territorio.cargar_distritos()
    assert len(distritos) == 112
    assert set(distritos["provincia"]) == set(esquemas.PROVINCIAS_CUSCO)
    assert distritos["ubigeo"].str.match(r"^08\d{4}$").all()
    assert distritos["ubigeo"].is_unique
    assert distritos.is_valid.all()


def test_ubigeo_sin_tildes_ni_mayusculas():
    assert territorio.ubigeo_de("Chumbivilcas", "SANTO TOMAS") == territorio.ubigeo_de("Chumbivilcas", "Santo Tomás")
    assert territorio.ubigeo_de("Chumbivilcas", "Santo Tomás") is not None


def test_alias_apuntan_a_distritos_existentes():
    for (provincia, _), oficial in territorio.ALIAS_OFICIALES.items():
        assert territorio.ubigeo_de(provincia, oficial) is not None, oficial


def test_nombre_desconocido_no_se_adivina():
    assert territorio.ubigeo_de("Calca", "Distrito Inexistente") is None
    # Un distrito real en otra provincia no debe asignarse
    assert territorio.ubigeo_de("Calca", "Omacha") is None


def test_varios_distritos():
    ubigeos = territorio.ubigeos_de("Paruro", "Yaurisque|Paccaritambo")
    assert len(ubigeos) == 2 and all(ubigeos)
