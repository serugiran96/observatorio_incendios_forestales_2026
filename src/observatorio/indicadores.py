"""Reglas de agregación del inventario de incendios, compartidas por los scripts y el dashboard.

- Los posibles duplicados no se eliminan del inventario; al sumar se conserva, de cada grupo, el
  registro con mayor cobertura destruida.
- Un incendio que abarca varios distritos cuenta en cada uno, pero sus cifras no se reparten: se
  suman aparte ("compartidas").
"""

from __future__ import annotations

import pandas as pd

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
        cobertura = pd.to_numeric(miembros["cobertura_natural_destruida_ha"], errors="coerce")
        conservar = miembros.loc[cobertura.fillna(-1).idxmax(), "id_evento"]
        excluidos |= grupo - {conservar}
    return excluidos


def sumar_sin_duplicados(inventario: pd.DataFrame) -> pd.Series:
    """Suma de cada cifra en eventos de un solo distrito, sin posibles duplicados."""
    excluidos = excluir_duplicados(inventario)
    unicos = inventario[~inventario["varios_distritos"].astype(str).eq("True") & ~inventario["id_evento"].isin(excluidos)]
    return unicos[CIFRAS].apply(pd.to_numeric, errors="coerce").sum()


def agregar_por_ubigeo(inventario: pd.DataFrame) -> pd.DataFrame:
    """Número de incendios y cifras sin duplicados por UBIGEO (los de varios distritos cuentan en cada uno)."""
    if inventario.empty:
        return pd.DataFrame(columns=["ubigeo", "n_incendios", *CIFRAS])
    excluidos = excluir_duplicados(inventario)
    largo = inventario.assign(ubigeo=inventario["ubigeo"].astype(str).str.split("|")).explode("ubigeo")
    conteo = largo.groupby("ubigeo").size().rename("n_incendios")
    unicos = largo[~largo["varios_distritos"].astype(str).eq("True") & ~largo["id_evento"].isin(excluidos)]
    sumas = unicos[CIFRAS].apply(pd.to_numeric, errors="coerce").groupby(unicos["ubigeo"]).sum()
    return conteo.to_frame().join(sumas, how="left").fillna(0).reset_index()
