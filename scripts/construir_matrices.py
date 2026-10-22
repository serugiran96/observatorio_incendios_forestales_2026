"""Construye las matrices de atención inmediata, restauración y presupuesto que lee el dashboard.

Requiere (ver README, flujo completo):
    data/processed/incendios_cusco_georreferenciado.csv  (scripts/agregar_por_distrito.py)
    data/processed/indicadores_distrito.csv              (scripts/agregar_por_distrito.py)
    data/processed/acciones_respuesta_indeci.csv         (scripts/extraer_reportes_indeci.py)
    data/raw/registro/medidas_restauracion.csv y costos_unitarios.csv (curados, versionados)
Opcional: corroboracion_satelital.csv (FIRMS) y gee_estadisticas_distrito.csv (Earth Engine).

Uso:
    uv run python scripts/construir_matrices.py

Salidas (data/processed/):
    matriz_atencion_inmediata.csv        una fila por incendio del periodo, con criterios explícitos
    restauracion_medidas_distrito.csv    distrito × medida aplicable, con nivel de sustento
    matriz_presupuesto.csv               intervenciones por territorio, cantidades y costos (o pendientes)
    recursos_documentados_contexto.csv   presupuestos documentados no asignables a una línea
"""

from __future__ import annotations

import sys

import pandas as pd

from observatorio import atencion, config, presupuesto, restauracion, territorio
from observatorio import evidencias as registro


def _opcional(nombre: str, **kwargs) -> pd.DataFrame | None:
    ruta = config.DIR_PROCESSED / nombre
    return pd.read_csv(ruta, **kwargs) if ruta.exists() else None


def main() -> int:
    fuentes = registro.cargar_fuentes()
    evidencias = registro.cargar_evidencias()
    medidas = restauracion.cargar_medidas()
    costos = presupuesto.cargar_costos()
    errores = restauracion.validar_medidas(medidas, fuentes) + presupuesto.validar_costos(costos, fuentes)
    if errores:
        print("Errores en los catálogos curados:\n  " + "\n  ".join(errores))
        return 1

    inventario = pd.read_csv(config.DIR_PROCESSED / "incendios_cusco_georreferenciado.csv", dtype=str)
    acciones = pd.read_csv(config.DIR_PROCESSED / "acciones_respuesta_indeci.csv", dtype=str)
    indicadores = pd.read_csv(config.DIR_PROCESSED / "indicadores_distrito.csv", dtype={"ubigeo": str})
    corroboracion = _opcional("corroboracion_satelital.csv")
    gee = _opcional("gee_estadisticas_distrito.csv", dtype={"ubigeo": str})
    distritos = territorio.cargar_distritos()
    nombres = dict(zip(distritos["ubigeo"], distritos["distrito"]))

    matriz = atencion.construir_matriz(inventario, acciones, evidencias, fuentes, corroboracion, nombres)
    matriz.to_csv(config.DIR_PROCESSED / "matriz_atencion_inmediata.csv", index=False, encoding="utf-8")

    por_distrito = restauracion.medidas_por_distrito(indicadores, medidas, gee)
    por_distrito.to_csv(config.DIR_PROCESSED / "restauracion_medidas_distrito.csv", index=False, encoding="utf-8")

    lineas = presupuesto.construir_matriz(matriz, por_distrito, costos, evidencias, gee)
    lineas.to_csv(config.DIR_PROCESSED / "matriz_presupuesto.csv", index=False, encoding="utf-8")
    presupuesto.recursos_de_contexto(evidencias).to_csv(
        config.DIR_PROCESSED / "recursos_documentados_contexto.csv", index=False, encoding="utf-8")

    print(f"Matriz de atención: {len(matriz)} incendios | seguimiento humanitario: "
          f"{matriz['seguimiento_humanitario'].sum()} | verificar atención: {matriz['verificar_atencion'].sum()}")
    print(f"Estados de atención: {matriz['estado_atencion'].value_counts().to_dict()}")
    print(f"Restauración: {por_distrito['ubigeo'].nunique()} distritos, {len(por_distrito)} medidas aplicables "
          f"({por_distrito['estado_aplicacion'].value_counts().to_dict()})")
    print(f"Presupuesto: {len(lineas)} líneas | con costo total: {lineas['costo_total_soles'].notna().sum()} | "
          f"pendientes de cotización: {(lineas['estado_costo'] == 'pendiente de cotización').sum()}")
    if gee is None:
        print("AVISO: sin gee_estadisticas_distrito.csv; control de erosión sin cantidades (análisis satelital pendiente).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
