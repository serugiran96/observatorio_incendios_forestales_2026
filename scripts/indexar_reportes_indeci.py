"""Construye un índice de los reportes del COEN-INDECI sobre incendios forestales en Cusco,
recorriendo el feed RSS del portal de emergencias de INDECI (ordenado por fecha).

Uso:
    uv run python scripts/indexar_reportes_indeci.py [--descargar]

Con --descargar, además baja el PDF de cada reporte a data/raw/documentos/indeci_coen_2026/
(no versionado) y registra su nombre en el índice.

Salida:
    data/processed/indice_reportes_indeci_cusco.csv
        una fila por reporte (preliminar o complementario), con número, fecha, distrito,
        número de actualización y enlace a la página del reporte.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import pandas as pd
import requests

from observatorio import config

CARPETA_PDF = config.DIR_DOCUMENTOS / "indeci_coen_2026"
_ENLACE_PDF = re.compile(r'href="(https://portal\.indeci\.gob\.pe/wp-content/uploads/[^"]+\.pdf)"', re.IGNORECASE)
_CABECERAS = {"User-Agent": "observatorio-incendios-cusco (proyecto universitario)"}

URL_FEED = "https://portal.indeci.gob.pe/emergencias/feed/"
BUSQUEDA = "incendio forestal cusco"
INICIO = datetime(2026, 8, 31)
PAUSA_SEGUNDOS = 1.0
MAX_PAGINAS = 200

# Tipos: reporte preliminar, reporte complementario (actualizaciones) e informe de emergencia
# (eventos graves, p. ej. con víctimas). Ejemplo de título:
# "REPORTE COMPLEMENTARIO N.º 14658 – 21/10/2026 / COEN – INDECI / 08:10 HORAS (Reporte N.º 9)
#  INCENDIO FORESTAL EN EL DISTRITO DE OMACHA – CUSCO"
_TITULO = re.compile(
    r"(?P<tipo>REPORTE\s+COMPLEMENTARIO|REPORTE\s+PRELIMINAR|INFORME\s+DE\s+EMERGENCIA)\s+N\.?\s*[°º]?\s*(?P<numero>\d+)"
    r".*?(?P<fecha>\d{1,2}/\d{1,2}/\d{4})"
    r"(?:.*?(?P<hora>\d{1,2}:\d{2})\s*HORAS)?"
    r"(?:.*?\((?:Reporte|Informe)\s+N\.?\s*[°º]?\s*(?P<actualizacion>\d+)\))?"
    r".*?INCENDIO\s+FORESTAL\s+EN\s+(?:EL\s+DISTRITO|LOS\s+DISTRITOS|LA\s+PROVINCIA)\s+DE\s+(?P<lugar>.+?)\s*[–-]\s*CUSCO",
    re.IGNORECASE | re.DOTALL,
)


_TIPOS = {
    "REPORTE COMPLEMENTARIO": "complementario",
    "REPORTE PRELIMINAR": "preliminar",
    "INFORME DE EMERGENCIA": "informe_emergencia",
}


def leer_pagina(numero: int) -> list[dict]:
    respuesta = requests.get(
        URL_FEED,
        params={"s": BUSQUEDA, "paged": numero},
        headers=_CABECERAS,
        timeout=90,
    )
    if respuesta.status_code == 404:
        return []
    respuesta.raise_for_status()
    raiz = ET.fromstring(respuesta.content)
    items = []
    for item in raiz.iter("item"):
        items.append(
            {
                "titulo": html.unescape(item.findtext("title", "")).strip(),
                "url": item.findtext("link", "").strip(),
                "publicado": parsedate_to_datetime(item.findtext("pubDate", "")),
            }
        )
    return items


def descargar_pdf(url_reporte: str, numero: int) -> str:
    """Descarga el PDF del reporte; devuelve el nombre del archivo.

    La página de cada reporte también enlaza PDF de otros reportes recientes (de cualquier región),
    así que se exige que el nombre del archivo contenga el número del reporte.
    """
    pagina = requests.get(url_reporte, headers=_CABECERAS, timeout=90)
    pagina.raise_for_status()
    enlaces = [
        e for e in _ENLACE_PDF.findall(pagina.text)
        if re.search(rf"N\.?\D{{0,3}}0*{numero}\D", requests.utils.unquote(e), re.IGNORECASE)
    ]
    if not enlaces:
        print(f"AVISO: no se encontró el PDF del reporte {numero} en {url_reporte}")
        return ""
    url_pdf = enlaces[0]
    nombre = requests.utils.unquote(url_pdf.rsplit("/", 1)[-1])
    destino = CARPETA_PDF / nombre
    if not destino.exists():
        respuesta = requests.get(url_pdf, headers=_CABECERAS, timeout=120)
        respuesta.raise_for_status()
        destino.write_bytes(respuesta.content)
        time.sleep(PAUSA_SEGUNDOS)
    return nombre


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--descargar", action="store_true", help="descargar el PDF de cada reporte")
    args = parser.parse_args()

    registros, no_reconocidos, pagina = [], [], 1
    while pagina <= MAX_PAGINAS:
        items = leer_pagina(pagina)
        if not items:
            break
        for item in items:
            coincidencia = _TITULO.search(re.sub(r"\s+", " ", item["titulo"]))
            if not coincidencia:
                if "CUSCO" in item["titulo"].upper() and "INCENDIO" in item["titulo"].upper():
                    no_reconocidos.append(item["titulo"])
                continue
            datos = coincidencia.groupdict()
            registros.append(
                {
                    "tipo_reporte": _TIPOS[re.sub(r"\s+", " ", datos["tipo"]).upper()],
                    "numero": int(datos["numero"]),
                    "fecha_reporte": datetime.strptime(datos["fecha"], "%d/%m/%Y").date().isoformat(),
                    "hora_reporte": datos["hora"] or "",
                    "actualizacion": int(datos["actualizacion"]) if datos["actualizacion"] else None,
                    "lugar": datos["lugar"].strip().title(),
                    "titulo": item["titulo"],
                    "url": item["url"],
                    "publicado_portal": item["publicado"].isoformat(),
                }
            )
        mas_antiguo = min(i["publicado"] for i in items).replace(tzinfo=None)
        print(f"página {pagina}: {len(items)} entradas, la más antigua {mas_antiguo:%Y-%m-%d}")
        if mas_antiguo < INICIO:
            break
        pagina += 1
        time.sleep(PAUSA_SEGUNDOS)

    indice = pd.DataFrame(registros).drop_duplicates("url")
    indice = indice[indice["fecha_reporte"] >= INICIO.date().isoformat()].sort_values(["fecha_reporte", "numero"])
    if args.descargar:
        CARPETA_PDF.mkdir(parents=True, exist_ok=True)
        archivos = []
        for k, (url, numero) in enumerate(zip(indice["url"], indice["numero"]), start=1):
            try:
                archivos.append(descargar_pdf(url, numero))
            except requests.RequestException as error:
                print(f"AVISO: no se pudo descargar {url}: {error}")
                archivos.append("")
            if k % 20 == 0:
                print(f"PDF {k}/{len(indice)}")
            time.sleep(PAUSA_SEGUNDOS)
        indice["archivo_pdf"] = archivos
        print(f"PDF disponibles: {sum(1 for a in archivos if a)}/{len(indice)}")

    destino = config.DIR_PROCESSED / "indice_reportes_indeci_cusco.csv"
    indice.to_csv(destino, index=False, encoding="utf-8")
    print(f"\nReportes de incendio forestal en Cusco desde {INICIO:%Y-%m-%d}: {len(indice)}")
    print(f"Lugares distintos: {indice['lugar'].nunique()} | guardado en {destino.relative_to(config.RAIZ_PROYECTO)}")
    for titulo in no_reconocidos:
        print(f"AVISO: título no reconocido: {titulo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
