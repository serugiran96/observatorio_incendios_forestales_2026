"""Extrae los incendios forestales de Cusco desde los reportes diarios de emergencias de la
Oficina de Gestión del Riesgo de Desastres del Congreso (compilan información de INDECI-COEN).

Uso:
    uv run python scripts/extraer_reportes_emergencia.py [--descargar]

Con --descargar, baja primero los PDF del índice 2026 que aún no estén en la carpeta local.

Salidas:
    data/processed/emergencias_cusco_ogrd.csv   una fila por incendio consolidado (auditoría)
    data/raw/registro/fuentes.csv               filas F-OGRD-* (una por reporte consultado)
    data/raw/registro/evidencias.csv            filas E-OGRD-* (evento y daños por incendio)
Las filas curadas manualmente del registro no se modifican.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date

import pandas as pd
import requests

from observatorio import config, esquemas
from observatorio import evidencias as ev
from observatorio import reportes_emergencia as rem

CARPETA = config.DIR_DOCUMENTOS / "congreso_ogrd_2026"
URL_INDICE = "https://www3.congreso.gob.pe/riesgodesastres/reportes/2026/"
PERIODO = (date(2026, 9, 1), config.FECHA_CORTE)


def descargar_reportes() -> None:
    """Descarga los reportes del periodo prioritario listados en el índice oficial."""
    CARPETA.mkdir(parents=True, exist_ok=True)
    html = requests.get(URL_INDICE, timeout=60).text
    for ruta in sorted(set(re.findall(r'href="([^"]+\.pdf)"', html))):
        nombre = ruta.rsplit("/", 1)[-1]
        try:
            fecha = rem.metadatos_archivo(nombre)["fecha_reporte"]
        except ValueError:
            continue
        destino = CARPETA / nombre
        if PERIODO[0] <= fecha <= PERIODO[1] and not destino.exists():
            respuesta = requests.get(rem.URL_BASE + nombre, timeout=120)
            respuesta.raise_for_status()
            destino.write_bytes(respuesta.content)
            print(f"descargado {nombre}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--descargar", action="store_true", help="descargar reportes faltantes del índice")
    args = parser.parse_args()
    if args.descargar:
        descargar_reportes()

    archivos = sorted(CARPETA.glob("*.pdf"), key=lambda r: rem.metadatos_archivo(r.name)["fecha_reporte"])
    if not archivos:
        print(f"No hay reportes en {CARPETA}. Ejecute con --descargar.")
        return 1

    tarjetas, notas_por_archivo = [], {}
    for ruta in archivos:
        fecha = rem.metadatos_archivo(ruta.name)["fecha_reporte"]
        del_archivo = [t for t in rem.extraer_tarjetas_pdf(ruta) if t.departamento.lower() == "cusco"]
        incendios = [t for t in del_archivo if t.es_incendio_forestal]
        tarjetas += [(ruta.name, fecha, t) for t in incendios]
        notas_por_archivo[ruta.name] = (
            f"Tarjetas de Cusco: {len(del_archivo)} (incendios forestales: {len(incendios)}). "
            "Compila reportes de INDECI-COEN; no es un inventario exhaustivo."
        )

    emergencias = rem.consolidar(tarjetas)

    # Tabla de auditoría en data/processed
    filas_auditoria = []
    for e in emergencias:
        t = e.tarjeta
        cifras = {d.variable: d.valor for d in rem.interpretar_danos(t.texto_danos) if d.valor is not None}
        filas_auditoria.append(
            {
                "clave": t.clave,
                "fecha_hora": t.fecha_hora.isoformat(sep=" ") if t.fecha_hora else "",
                "provincia": t.provincia,
                "distrito": t.distrito,
                "distrito_reportado": t.distrito_reportado,
                "localidad": t.localidad,
                "texto_danos": t.texto_danos,
                "cobertura_natural_destruida_ha": cifras.get("cobertura_natural_destruida"),
                "personas_fallecidas": cifras.get("personas_fallecidas"),
                "personas_lesionadas": cifras.get("personas_lesionadas"),
                "personas_afectadas": cifras.get("personas_afectadas"),
                "viviendas_afectadas": cifras.get("viviendas_afectadas"),
                "ganado_afectado": cifras.get("ganado_afectado"),
                "reporte_ultimo": e.archivo_ultimo,
                "reportes": "; ".join(e.reportes),
                "posibles_duplicados": "; ".join(e.posibles_duplicados),
            }
        )
    config.DIR_PROCESSED.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(filas_auditoria).to_csv(config.DIR_PROCESSED / "emergencias_cusco_ogrd.csv", index=False, encoding="utf-8")

    # Registro de fuentes y evidencias
    carpeta_local = CARPETA.relative_to(config.RAIZ_PROYECTO).as_posix()
    nuevas_fuentes = pd.DataFrame(
        [rem.fila_fuente(r.name, config.FECHA_CORTE, notas_por_archivo[r.name], carpeta_local) for r in archivos],
        columns=esquemas.COLUMNAS_FUENTES,
    )
    nuevas_evidencias = pd.DataFrame(
        [fila for e in emergencias for fila in rem.filas_evidencia(e)], columns=esquemas.COLUMNAS_EVIDENCIAS
    )
    fuentes = ev.reemplazar_por_prefijo(ev.cargar_fuentes(), nuevas_fuentes, "id_fuente", rem.PREFIJO_FUENTE)
    evidencias = ev.reemplazar_por_prefijo(ev.cargar_evidencias(), nuevas_evidencias, "id_evidencia", rem.PREFIJO_EVIDENCIA)

    resultado = ev.validar_evidencias(evidencias, fuentes)
    resultado_fuentes = ev.validar_fuentes(fuentes)
    if not (resultado.es_valido and resultado_fuentes.es_valido):
        print(resultado_fuentes.resumen())
        print(resultado.resumen())
        print("No se escribió el registro: corrija los errores.")
        return 1

    ev.guardar_registro(fuentes, config.RUTA_FUENTES, esquemas.COLUMNAS_FUENTES)
    ev.guardar_registro(evidencias, config.RUTA_EVIDENCIAS, esquemas.COLUMNAS_EVIDENCIAS)

    con_duplicado = sum(1 for e in emergencias if e.posibles_duplicados)
    print(f"Reportes procesados: {len(archivos)}")
    print(f"Incendios forestales en Cusco (tarjetas únicas): {len(emergencias)}; con posible duplicado: {con_duplicado}")
    print(f"Evidencias generadas: {len(nuevas_evidencias)} | Fuentes: {len(nuevas_fuentes)}")
    print(f"Advertencias de validación: {len(resultado.advertencias)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
