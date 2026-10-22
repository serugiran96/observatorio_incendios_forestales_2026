"""Georreferencia el inventario de incendios por distrito (UBIGEO) y calcula indicadores distritales.

Requiere:
    data/processed/incendios_cusco_consolidado.csv   (scripts/extraer_reportes_indeci.py)
    data/processed/limites_cusco_distritos.geojson   (scripts/descargar_limites.py)

Uso:
    uv run python scripts/agregar_por_distrito.py

Salidas:
    data/processed/incendios_cusco_georreferenciado.csv   inventario + UBIGEO + punto aproximado
    data/processed/indicadores_distrito.csv               indicadores del periodo prioritario por distrito
    data/processed/indicadores_distrito.geojson           los mismos indicadores con geometría (mapas)

Reglas:
- La ubicación de cada incendio es, como máximo, el distrito: el punto del mapa es un punto interior del
  distrito (no la ubicación del incendio) y se marca como aproximado.
- Un incendio que abarca varios distritos cuenta en cada uno, pero sus cifras no se reparten: se suman
  aparte en las columnas "*_compartidas".
- Los posibles duplicados no se eliminan; las hectáreas se informan con y sin ellos.
"""

from __future__ import annotations

import sys

import geopandas as gpd
import pandas as pd

from observatorio import config, territorio

CIFRAS = [
    "cobertura_natural_destruida_ha",
    "personas_fallecidas",
    "personas_lesionadas",
    "personas_damnificadas",
    "personas_afectadas",
    "viviendas_afectadas",
    "viviendas_inhabitables",
    "viviendas_destruidas",
    "ganado_perdido",
    "ganado_afectado",
    "cultivos_ha",
]


def excluir_duplicados(inventario: pd.DataFrame) -> set[str]:
    """IDs de eventos que se omiten al sumar sin duplicados: de cada grupo se conserva el de mayor cobertura."""
    excluidos = set()
    vistos = set()
    for fila in inventario.itertuples(index=False):
        if not isinstance(fila.posibles_duplicados, str) or not fila.posibles_duplicados or fila.id_evento in vistos:
            continue
        grupo = {fila.id_evento, *fila.posibles_duplicados.split("; ")}
        vistos |= grupo
        miembros = inventario[inventario["id_evento"].isin(grupo)]
        conservar = miembros.sort_values("cobertura_natural_destruida_ha", ascending=False, na_position="last").iloc[0]["id_evento"]
        excluidos |= grupo - {conservar}
    return excluidos


# Grupos de ecosistemas (Mapa Nacional de Ecosistemas, MINAM) usados por el módulo de restauración
GRUPOS_ECOSISTEMA = {
    "ha_pajonal": ("Pajonal",),
    "ha_bofedal": ("Bofedal",),
    "ha_bosque": ("Bosque",),
    "ha_matorral": ("Matorral",),
    "ha_zona_agricola": ("Zona agrícola",),
}


def resumen_ecosistemas() -> pd.DataFrame:
    """Ecosistemas principales y hectáreas por grupo en cada distrito (si se ejecutó descargar_ecosistemas.py)."""
    ruta = config.DIR_PROCESSED / "ecosistemas_por_distrito.csv"
    if not ruta.exists():
        return pd.DataFrame(columns=["ubigeo"])
    ecos = pd.read_csv(ruta, dtype={"ubigeo": str})
    filas = []
    for ubigeo, grupo in ecos.groupby("ubigeo"):
        grupo = grupo.sort_values("ha", ascending=False)
        fila = {
            "ubigeo": ubigeo,
            "ecosistemas_principales": "; ".join(f"{e} ({p:.0f} %)" for e, p in zip(grupo["ecosistema"][:3], grupo["pct_distrito"][:3])),
        }
        for columna, prefijos in GRUPOS_ECOSISTEMA.items():
            fila[columna] = round(grupo.loc[grupo["ecosistema"].str.startswith(prefijos), "ha"].sum(), 1)
        filas.append(fila)
    return pd.DataFrame(filas)


def main() -> int:
    inventario = pd.read_csv(config.DIR_PROCESSED / "incendios_cusco_consolidado.csv", dtype={"sinpad": str})
    distritos = territorio.cargar_distritos()
    puntos = distritos.set_index("ubigeo").geometry.representative_point()

    # 1) UBIGEO y punto aproximado por incendio
    ubigeos, no_reconocidos = [], []
    for fila in inventario.itertuples(index=False):
        codigos = territorio.ubigeos_de(str(fila.provincia), str(fila.distrito))
        if not codigos or None in codigos:
            no_reconocidos.append(f"{fila.id_evento}: {fila.provincia} / {fila.distrito}")
        ubigeos.append("|".join(c for c in codigos if c))
    inventario["ubigeo"] = ubigeos
    inventario["alias_por_verificar"] = [
        territorio.requiere_verificacion(str(p), str(d)) for p, d in zip(inventario["provincia"], inventario["distrito"])
    ]
    primer_ubigeo = inventario["ubigeo"].str.split("|").str[0]
    inventario["latitud_aprox"] = primer_ubigeo.map(lambda u: round(puntos[u].y, 5) if u in puntos.index else None)
    inventario["longitud_aprox"] = primer_ubigeo.map(lambda u: round(puntos[u].x, 5) if u in puntos.index else None)
    inventario["precision_punto"] = "punto interior del distrito (aproximado)"
    inventario["varios_distritos"] = inventario["ubigeo"].str.contains(r"\|")
    inventario.to_csv(config.DIR_PROCESSED / "incendios_cusco_georreferenciado.csv", index=False, encoding="utf-8")

    # 2) Indicadores del periodo prioritario
    fechas = pd.to_datetime(inventario["fecha_ocurrencia"])
    inicio, fin = (pd.Timestamp(f) for f in config.PERIODO_PRIORITARIO)
    periodo = inventario[(fechas >= inicio) & (fechas <= fin)].copy()
    excluidos = excluir_duplicados(periodo)
    for col in CIFRAS:
        periodo[col] = pd.to_numeric(periodo[col], errors="coerce")
    for col in ("entrega_bah_documentada", "atencion_medica_documentada"):
        periodo[col] = periodo[col].fillna(False).astype(bool)
    periodo["con_damnificados_o_inhabitables"] = (periodo["personas_damnificadas"].fillna(0) > 0) | (
        periodo["viviendas_inhabitables"].fillna(0) > 0
    )

    filas = []
    for distrito in distritos.itertuples(index=False):
        en_distrito = periodo[periodo["ubigeo"].str.split("|").apply(lambda us: distrito.ubigeo in us)]
        unicos = en_distrito[~en_distrito["varios_distritos"]]
        compartidos = en_distrito[en_distrito["varios_distritos"]]
        fila = {
            "ubigeo": distrito.ubigeo,
            "provincia": distrito.provincia,
            "distrito": distrito.distrito,
            "poblacion_2018": distrito.poblacion_2018,
            "area_km2": distrito.area_km2,
            "n_incendios": len(en_distrito),
            "n_incendios_varios_distritos": len(compartidos),
            "n_posibles_duplicados": int(en_distrito["id_evento"].isin(excluidos).sum()),
            "fecha_ultimo_incendio": en_distrito["fecha_ocurrencia"].max() if len(en_distrito) else "",
            "n_con_cifra_cobertura": int(unicos["cobertura_natural_destruida_ha"].notna().sum()),
            "cobertura_destruida_ha_sin_duplicados": unicos.loc[
                ~unicos["id_evento"].isin(excluidos), "cobertura_natural_destruida_ha"].sum(),
            "cobertura_destruida_ha_compartidas": compartidos["cobertura_natural_destruida_ha"].sum(),
            "n_entrega_bah_documentada": int(en_distrito["entrega_bah_documentada"].sum()),
            "n_atencion_medica_documentada": int(en_distrito["atencion_medica_documentada"].sum()),
            "n_damnificados_sin_bah_documentada": int(
                (en_distrito["con_damnificados_o_inhabitables"] & ~en_distrito["entrega_bah_documentada"]).sum()),
            "n_abiertos_al_ultimo_reporte": int(en_distrito["estado"].eq("abierto al último reporte").sum()),
            "alias_por_verificar": bool(en_distrito["alias_por_verificar"].any()),
        }
        for col in CIFRAS[1:]:
            fila[col] = unicos.loc[~unicos["id_evento"].isin(excluidos), col].sum()
        filas.append(fila)
    indicadores = pd.DataFrame(filas)
    indicadores["cobertura_destruida_pct_area"] = (
        indicadores["cobertura_destruida_ha_sin_duplicados"] / (indicadores["area_km2"] * 100) * 100
    ).round(3)
    indicadores = indicadores.merge(resumen_ecosistemas(), on="ubigeo", how="left")
    indicadores.to_csv(config.DIR_PROCESSED / "indicadores_distrito.csv", index=False, encoding="utf-8")
    geo = distritos[["ubigeo", "geometry"]].merge(indicadores, on="ubigeo")
    gpd.GeoDataFrame(geo, geometry="geometry", crs=distritos.crs).to_file(
        config.DIR_PROCESSED / "indicadores_distrito.geojson", driver="GeoJSON"
    )

    con_incendios = indicadores[indicadores["n_incendios"] > 0]
    print(f"Incendios en el periodo: {len(periodo)} | distritos con incendios: {len(con_incendios)} de {len(indicadores)}")
    print(f"Cobertura destruida (EDAN, sin duplicados, solo eventos de un distrito): "
          f"{indicadores['cobertura_destruida_ha_sin_duplicados'].sum():,.1f} ha "
          f"+ {periodo.loc[periodo['varios_distritos'], 'cobertura_natural_destruida_ha'].sum():,.1f} ha en eventos de varios distritos")
    print(f"Distritos con damnificados sin entrega de BAH documentada: "
          f"{(indicadores['n_damnificados_sin_bah_documentada'] > 0).sum()}")
    for texto in no_reconocidos:
        print(f"AVISO: distrito no reconocido -> {texto}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
