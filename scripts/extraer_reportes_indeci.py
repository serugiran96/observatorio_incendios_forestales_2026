"""Convierte los PDF del COEN-INDECI (incendios forestales en Cusco) en evidencias del registro y
en un inventario consolidado de incendios.

Requiere haber ejecutado antes:
    uv run python scripts/indexar_reportes_indeci.py --descargar
    uv run python scripts/extraer_reportes_emergencia.py   (para la referencia cruzada OGRD)

Uso:
    uv run python scripts/extraer_reportes_indeci.py

Salidas:
    data/raw/registro/fuentes.csv, evidencias.csv     filas F-INDECI-* / E-INDECI-*
    data/processed/incendios_cusco_consolidado.csv    una fila por incendio (INDECI + OGRD)
    data/processed/acciones_respuesta_indeci.csv      acciones de respuesta reportadas
"""

from __future__ import annotations

import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date

import pandas as pd

from observatorio import config, esquemas
from observatorio import evidencias as ev
from observatorio import reportes_indeci as ri

CARPETA_PDF = config.DIR_DOCUMENTOS / "indeci_coen_2026"
RUTA_INDICE = config.DIR_PROCESSED / "indice_reportes_indeci_cusco.csv"
RUTA_OGRD = config.DIR_PROCESSED / "emergencias_cusco_ogrd.csv"

# Tipo de acción -> (categoría, variable, estado de verificación)
ACCIONES_A_EVIDENCIA = {
    "entrega_bah": ("ayuda_entregada", "entrega_bah", "atencion_documentada"),
    "atencion_medica": ("ayuda_entregada", "atencion_medica", "atencion_documentada"),
    "insumos_pecuarios": ("ayuda_entregada", "insumos_pecuarios", "atencion_documentada"),
    "coordinacion_bah": ("ayuda_anunciada", "ayuda_anunciada", "atencion_no_verificada"),
    "solicitud_ayuda": ("necesidad", "necesidad_reportada", "necesidad_pendiente_documentada"),
    "extincion": ("evento_incendio", "incendio_extinguido", "dano_confirmado"),
}


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sin_tildes.lower())


def provincia_oficial(nombre: str) -> str:
    """Devuelve el nombre de provincia tal como figura en esquemas.PROVINCIAS_CUSCO."""
    clave = normalizar(nombre).removesuffix("s")  # "Quispicanchis" -> "quispicanchi"
    for oficial in esquemas.PROVINCIAS_CUSCO:
        if normalizar(oficial) == clave:
            return oficial
    return nombre


def marcar_posibles_duplicados(filas: list[dict], dias: int = 2) -> None:
    """Señala incendios del mismo distrito, con fechas cercanas, que comparten un nombre de lugar.

    No elimina filas: la decisión de fusionarlas requiere verificación (ver docs/criterios_verificacion.md).
    """
    genericas = {"sector", "sectores", "comunidad", "comunidades", "centro", "poblado", "anexo", "cerro", "localidad", "campesina"}
    tokens = lambda texto: {p for p in re.findall(r"[a-záéíóúñ]{5,}", str(texto).lower()) if p not in genericas}
    for fila in filas:
        fila.setdefault("posibles_duplicados", "")
    for i, a in enumerate(filas):
        for b in filas[i + 1:]:
            if a["provincia"] != b["provincia"] or not (set(a["distrito"].split("|")) & set(b["distrito"].split("|"))):
                continue
            if abs((date.fromisoformat(a["fecha_ocurrencia"]) - date.fromisoformat(b["fecha_ocurrencia"])).days) > dias:
                continue
            if tokens(a["localidad"]) & tokens(b["localidad"]):
                a["posibles_duplicados"] = "; ".join(filter(None, [a["posibles_duplicados"], b["id_evento"]]))
                b["posibles_duplicados"] = "; ".join(filter(None, [b["posibles_duplicados"], a["id_evento"]]))


def fuente_de(reporte: ri.ReporteIndeci, url: str) -> dict:
    tipos = {"RC": "Reporte complementario", "RP": "Reporte preliminar", "IE": "Informe de emergencia"}
    actualizacion = f" (actualización n.º {reporte.actualizacion})" if reporte.actualizacion else ""
    return {
        "id_fuente": reporte.id_fuente,
        "institucion": ri.INSTITUCION,
        "titulo": f"{tipos[reporte.tipo]} N.º {reporte.numero}{actualizacion} – incendio forestal en "
                  f"{', '.join(reporte.distritos) or 'Cusco'} ({reporte.provincia or 'Cusco'})",
        "url": url,
        "tipo_fuente": "oficial_nacional",
        "fecha_publicacion": reporte.fecha_reporte.isoformat(),
        "fecha_consulta": config.FECHA_CORTE.isoformat(),
        "accesible": "si",
        "archivo_local": f"{CARPETA_PDF.relative_to(config.RAIZ_PROYECTO).as_posix()}/{reporte.archivo}",
        "notas": "Fuente primaria COEN-INDECI (datos SINPAD/COER). " + (
            "Tabla de daños no legible automáticamente; ver PDF." if reporte.danos_sin_interpretar else ""),
    }


def main() -> int:
    indice = pd.read_csv(RUTA_INDICE, dtype=str, keep_default_na=False)
    if "archivo_pdf" not in indice.columns:
        print("El índice no tiene PDF descargados. Ejecute indexar_reportes_indeci.py --descargar.")
        return 1

    reportes, url_por_fuente, fallidos, erratas = [], {}, [], {}
    for fila in indice.itertuples(index=False):
        if not fila.archivo_pdf or not (CARPETA_PDF / fila.archivo_pdf).exists():
            fallidos.append(f"{fila.url} (sin PDF)")
            continue
        reporte = ri.leer_reporte(CARPETA_PDF / fila.archivo_pdf)
        if reporte is None or reporte.fecha_ocurrencia is None:
            fallidos.append(f"{fila.archivo_pdf} (estructura no reconocida)")
            continue
        if str(reporte.numero) != str(int(fila.numero)) and str(int(fila.numero)) not in fila.archivo_pdf:
            fallidos.append(f"{fila.archivo_pdf} (no corresponde al reporte {fila.numero} del índice)")
            continue
        reporte.provincia = provincia_oficial(reporte.provincia)
        if reporte.provincia not in esquemas.PROVINCIAS_CUSCO:
            fallidos.append(f"{fila.archivo_pdf} (provincia '{reporte.provincia}' fuera de Cusco)")
            continue
        if not reporte.distritos:
            reporte.distritos = [fila.lugar]
        reportes.append(reporte)
        url_por_fuente[reporte.id_fuente] = fila.url
        if str(reporte.numero) != str(int(fila.numero)):
            erratas[reporte.id_fuente] = f"El portal publica este reporte como N.º {fila.numero}; el PDF dice N.º {reporte.numero}."

    # Agrupar reportes del mismo incendio y ordenar cada cadena por fecha y actualización
    eventos: dict[str, list[ri.ReporteIndeci]] = defaultdict(list)
    for reporte in reportes:
        eventos[reporte.clave_evento].append(reporte)
    for cadena in eventos.values():
        cadena.sort(key=lambda r: (r.fecha_reporte, r.actualizacion or 0, r.numero))

    ogrd = pd.read_csv(RUTA_OGRD, dtype=str, keep_default_na=False) if RUTA_OGRD.exists() else pd.DataFrame()
    filas_fuentes = {r.id_fuente: fuente_de(r, url_por_fuente[r.id_fuente]) for r in reportes}
    for id_fuente, nota in erratas.items():
        filas_fuentes[id_fuente]["notas"] = f"{filas_fuentes[id_fuente]['notas']} {nota}".strip()
    filas_evidencias, filas_consolidado, filas_acciones, claves_ogrd_usadas = [], [], [], set()

    for clave, cadena in sorted(eventos.items(), key=lambda kv: kv[1][0].fecha_ocurrencia):
        ultimo = cadena[-1]
        distrito = "|".join(ultimo.distritos)
        provincia = ultimo.provincia if ultimo.provincia in esquemas.PROVINCIAS_CUSCO else ""
        precision = "centro_poblado" if ultimo.sector else "distrito"
        base = {
            "provincia": provincia,
            "distrito": distrito,
            "localidad": ultimo.sector,
            "ubigeo": "",
            "latitud": "",
            "longitud": "",
            "precision_geografica": precision if provincia else "region",
            "nivel_confianza": "alta",
            "fuente_oficial_citada": "COEN-INDECI",
        }

        # Referencia cruzada con las tarjetas OGRD-Congreso (mismo distrito, ±1 día)
        coincidencias = []
        if not ogrd.empty:
            for f in ogrd.itertuples(index=False):
                mismo_distrito = bool({normalizar(d) for d in f.distrito.split("|")} & {normalizar(d) for d in ultimo.distritos})
                if mismo_distrito and f.fecha_hora and abs((date.fromisoformat(f.fecha_hora[:10]) - ultimo.fecha_ocurrencia).days) <= 1:
                    coincidencias.append(f.clave)
        claves_ogrd_usadas.update(coincidencias)

        cadena_txt = ", ".join(r.id_fuente for r in cadena)
        observaciones = [f"SINPAD {next((r.sinpad for r in reversed(cadena) if r.sinpad), 'no indicado')}",
                         f"reportes: {cadena_txt}"]
        if coincidencias:
            observaciones.append("también en tarjetas OGRD: " + ", ".join(f"E-OGRD-{c}-00" for c in coincidencias))
        if ultimo.danos_sin_interpretar:
            observaciones.append("tabla de daños con cifras no interpretadas automáticamente; revisar PDF")

        if ultimo.cerrado or (any(r.cerrado for r in cadena) and not any(a.tipo == "cierre_temporal" for a in ultimo.acciones)):
            estado = "cerrado (emergencia atendida)"
        elif any(a.tipo == "cierre_temporal" for r in cadena for a in r.acciones):
            estado = "cierre temporal (atención en curso)"
        else:
            estado = "abierto al último reporte"
        filas_evidencias.append({
            **base,
            "id_evidencia": f"{ri.PREFIJO_EVIDENCIA}{clave}-00",
            "id_fuente": ultimo.id_fuente,
            "fecha_evento": ultimo.fecha_ocurrencia.isoformat(),
            "categoria": "evento_incendio",
            "variable": "incendio_reportado",
            "valor": "1",
            "unidad": "evento",
            "descripcion": f"{ultimo.descripcion}. Estado: {estado} ({ultimo.fecha_reporte:%d/%m/%Y}).",
            "estado_verificacion": "dano_confirmado",
            "observaciones": "; ".join(observaciones),
        })

        # Daños del último reporte de la cadena (cifras acumuladas actualizadas)
        cifras = defaultdict(float)
        varios_distritos = len({d.distrito for d in ultimo.danos}) > 1  # la tabla tiene una fila por distrito
        for k, dano in enumerate((d for d in ultimo.danos if d.variable), start=1):
            cifras[dano.variable] += dano.valor
            filas_evidencias.append({
                **base,
                "distrito": dano.distrito if varios_distritos and dano.distrito else distrito,
                "id_evidencia": f"{ri.PREFIJO_EVIDENCIA}{clave}-D{k:02d}",
                "id_fuente": ultimo.id_fuente,
                "fecha_evento": ultimo.fecha_ocurrencia.isoformat(),
                "categoria": dano.categoria,
                "variable": dano.variable,
                "valor": f"{dano.valor:g}",
                "unidad": dano.unidad,
                "descripcion": f"{esquemas.ETIQUETAS_VARIABLES[dano.variable]}: {dano.valor:g} {dano.unidad}, según la "
                               f"evaluación de daños (EDAN) reportada al COEN, actualizada al {ultimo.fecha_reporte:%d/%m/%Y}.",
                "estado_verificacion": "dano_confirmado",
                "observaciones": f"columna reconstruida: '{dano.encabezado}'",
            })

        # Acciones de toda la cadena, sin repetir la misma acción reportada en varias actualizaciones
        vistas, contador = set(), 0
        for reporte in cadena:
            for accion in reporte.acciones:
                fecha = accion.fecha or reporte.fecha_reporte
                filas_acciones.append({
                    "id_evento": clave, "id_fuente": reporte.id_fuente, "fecha": fecha.isoformat(), "nivel": accion.nivel,
                    "entidad": accion.entidad, "tipo": accion.tipo or "", "texto": accion.texto,
                })
                if accion.tipo not in ACCIONES_A_EVIDENCIA:
                    continue
                firma = (fecha, accion.tipo, normalizar(accion.texto)[:60])
                if firma in vistas:
                    continue
                vistas.add(firma)
                contador += 1
                categoria, variable, estado_v = ACCIONES_A_EVIDENCIA[accion.tipo]
                if accion.tipo == "extincion" and not re.search(r"extingui|liquidad|sofocad", accion.texto, re.I):
                    variable = "incendio_controlado"
                filas_evidencias.append({
                    **base,
                    "id_evidencia": f"{ri.PREFIJO_EVIDENCIA}{clave}-A{contador:02d}",
                    "id_fuente": reporte.id_fuente,
                    "fecha_evento": min(fecha, reporte.fecha_reporte).isoformat(),
                    "categoria": categoria,
                    "variable": variable,
                    "valor": "",
                    "unidad": "",
                    "descripcion": f"{accion.entidad}: {accion.texto}.",
                    "estado_verificacion": estado_v,
                    "observaciones": f"nivel {accion.nivel.lower() or 'no indicado'}; acción reportada al COEN",
                })

        # Anexo de Bienes de Ayuda Humanitaria: evidencia de entrega aunque el texto no la describa
        rubros = sorted({rubro for r in cadena for rubro in r.rubros_bah})
        if rubros:
            con_anexo = next(r for r in reversed(cadena) if r.rubros_bah)
            filas_evidencias.append({
                **base,
                "id_evidencia": f"{ri.PREFIJO_EVIDENCIA}{clave}-B01",
                "id_fuente": con_anexo.id_fuente,
                "fecha_evento": con_anexo.fecha_reporte.isoformat(),
                "categoria": "ayuda_entregada",
                "variable": "entrega_bah",
                "valor": "",
                "unidad": "",
                "descripcion": f"Anexo 'Bienes de ayuda humanitaria' del reporte con bienes entregados y recibidos; rubros: {', '.join(r.lower() for r in rubros)}.",
                "estado_verificacion": "atencion_documentada",
                "observaciones": "Cantidades del anexo no extraídas automáticamente; ver PDF.",
            })

        tipos_accion = {a.tipo for r in cadena for a in r.acciones}
        if rubros:
            tipos_accion.add("entrega_bah")
        fechas_bah = sorted((a.fecha or r.fecha_reporte) for r in cadena for a in r.acciones if a.tipo == "entrega_bah")
        filas_consolidado.append({
            "id_evento": f"INDECI-{clave}",
            "fuente_principal": "COEN-INDECI",
            "provincia": provincia,
            "distrito": distrito,
            "localidad": ultimo.sector,
            "fecha_ocurrencia": ultimo.fecha_ocurrencia.isoformat(),
            "sinpad": next((r.sinpad for r in reversed(cadena) if r.sinpad), ""),
            "estado": estado,
            "ultimo_reporte": ultimo.id_fuente,
            "fecha_ultimo_reporte": ultimo.fecha_reporte.isoformat(),
            "n_reportes": len(cadena),
            "cobertura_natural_destruida_ha": cifras.get("cobertura_natural_destruida"),
            "personas_fallecidas": cifras.get("personas_fallecidas"),
            "personas_lesionadas": cifras.get("personas_lesionadas"),
            "personas_damnificadas": cifras.get("personas_damnificadas"),
            "personas_afectadas": cifras.get("personas_afectadas"),
            "viviendas_afectadas": cifras.get("viviendas_afectadas"),
            "viviendas_inhabitables": cifras.get("viviendas_inhabitables"),
            "viviendas_destruidas": cifras.get("viviendas_destruidas"),
            "ganado_perdido": cifras.get("ganado_perdido"),
            "ganado_afectado": cifras.get("ganado_afectado"),
            "cultivos_ha": (cifras.get("cultivos_afectados") or 0) + (cifras.get("cultivos_perdidos") or 0) or None,
            "tabla_danos_no_legible": ultimo.danos_sin_interpretar,
            "entrega_bah_documentada": "entrega_bah" in tipos_accion,
            "fecha_primera_entrega_bah": fechas_bah[0].isoformat() if fechas_bah else "",
            "rubros_bah": ", ".join(r.lower() for r in rubros),
            "atencion_medica_documentada": "atencion_medica" in tipos_accion,
            "insumos_pecuarios_documentados": "insumos_pecuarios" in tipos_accion,
            "ayuda_solicitada": "solicitud_ayuda" in tipos_accion,
            "tarjetas_ogrd": "; ".join(coincidencias),
            "descripcion": ultimo.descripcion,
        })

    marcar_posibles_duplicados(filas_consolidado)

    # Incendios que solo aparecen en las tarjetas OGRD (sin reporte COEN-INDECI emparejado)
    for f in ogrd.itertuples(index=False):
        if f.clave in claves_ogrd_usadas:
            continue
        filas_consolidado.append({
            "id_evento": f"OGRD-{f.clave}",
            "fuente_principal": "OGRD-Congreso (compila COEN-INDECI)",
            "provincia": f.provincia, "distrito": f.distrito, "localidad": f.localidad,
            "fecha_ocurrencia": f.fecha_hora[:10], "estado": "sin seguimiento en reportes COEN indexados",
            "ultimo_reporte": f.reporte_ultimo, "n_reportes": len(f.reportes.split("; ")),
            "cobertura_natural_destruida_ha": f.cobertura_natural_destruida_ha or None,
            "personas_fallecidas": f.personas_fallecidas or None, "personas_lesionadas": f.personas_lesionadas or None,
            "personas_afectadas": f.personas_afectadas or None, "viviendas_afectadas": f.viviendas_afectadas or None,
            "ganado_afectado": f.ganado_afectado or None, "entrega_bah_documentada": False,
            "tarjetas_ogrd": f.clave, "descripcion": f.texto_danos,
        })

    # Escritura del registro
    nuevas_fuentes = pd.DataFrame(list(filas_fuentes.values()), columns=esquemas.COLUMNAS_FUENTES)
    nuevas_evidencias = pd.DataFrame(filas_evidencias, columns=esquemas.COLUMNAS_EVIDENCIAS).fillna("")
    fuentes = ev.reemplazar_por_prefijo(ev.cargar_fuentes(), nuevas_fuentes, "id_fuente", ri.PREFIJO_FUENTE)
    evidencias = ev.reemplazar_por_prefijo(ev.cargar_evidencias(), nuevas_evidencias, "id_evidencia", ri.PREFIJO_EVIDENCIA)
    resultado_f, resultado_e = ev.validar_fuentes(fuentes), ev.validar_evidencias(evidencias, fuentes)
    if not (resultado_f.es_valido and resultado_e.es_valido):
        print(resultado_f.resumen())
        print(resultado_e.resumen())
        print("No se escribió el registro: corrija los errores.")
        return 1
    ev.guardar_registro(fuentes, config.RUTA_FUENTES, esquemas.COLUMNAS_FUENTES)
    ev.guardar_registro(evidencias, config.RUTA_EVIDENCIAS, esquemas.COLUMNAS_EVIDENCIAS)

    consolidado = pd.DataFrame(filas_consolidado).sort_values(["fecha_ocurrencia", "provincia", "distrito"])
    consolidado.to_csv(config.DIR_PROCESSED / "incendios_cusco_consolidado.csv", index=False, encoding="utf-8")
    pd.DataFrame(filas_acciones).to_csv(config.DIR_PROCESSED / "acciones_respuesta_indeci.csv", index=False, encoding="utf-8")

    print(f"Reportes COEN-INDECI leídos: {len(reportes)} | no procesados: {len(fallidos)}")
    for f in fallidos:
        print(f"  AVISO: {f}")
    print(f"Incendios COEN-INDECI: {len(eventos)} | solo en OGRD: {len(consolidado) - len(eventos)} | total: {len(consolidado)}")
    print(f"Evidencias E-INDECI: {len(nuevas_evidencias)} | advertencias de validación: {len(resultado_e.advertencias)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
