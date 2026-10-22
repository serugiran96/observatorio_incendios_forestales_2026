"""Carga y validación del registro de fuentes, evidencias y vacíos de información.

Los CSV se leen siempre como texto para no perder ceros iniciales (UBIGEO) ni convertir
celdas vacías en NaN; la conversión de tipos se hace después de validar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from observatorio import config, esquemas

# Heurística conservadora para detectar datos personales que no deben registrarse
# Los dígitos que forman parte de un identificador (p. ej. "E-OGRD-93816452-00") no cuentan.
_PATRON_DNI = re.compile(r"(?<![\w.,-])\d{8}(?![\w.,-])")
_PATRON_CELULAR = re.compile(r"(?<![\w-])9\d{2}[\s-]?\d{3}[\s-]?\d{3}(?![\w-])")
_PATRON_UBIGEO = re.compile(rf"^{config.CODIGO_DEPARTAMENTO_CUSCO}\d{{4}}$")


@dataclass
class ResultadoValidacion:
    """Errores bloqueantes y advertencias de una validación."""

    errores: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    @property
    def es_valido(self) -> bool:
        return not self.errores

    def resumen(self) -> str:
        lineas = [f"{len(self.errores)} errores, {len(self.advertencias)} advertencias"]
        lineas += [f"  ERROR: {e}" for e in self.errores]
        lineas += [f"  AVISO: {a}" for a in self.advertencias]
        return "\n".join(lineas)


# --- Lectura --------------------------------------------------------------------
def leer_registro(ruta: Path) -> pd.DataFrame:
    """Lee un CSV del registro como texto, con celdas vacías como cadenas vacías."""
    return pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8")


def cargar_fuentes(ruta: Path = config.RUTA_FUENTES) -> pd.DataFrame:
    return leer_registro(ruta)


def cargar_evidencias(ruta: Path = config.RUTA_EVIDENCIAS) -> pd.DataFrame:
    return leer_registro(ruta)


def cargar_vacios(ruta: Path = config.RUTA_VACIOS) -> pd.DataFrame:
    return leer_registro(ruta)


# --- Utilidades de validación ---------------------------------------------------
def _fecha_iso(texto: str) -> date | None:
    """Convierte 'AAAA-MM-DD' en fecha; devuelve None si el texto no es una fecha válida."""
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def _es_numero(texto: str) -> bool:
    try:
        float(texto)
    except ValueError:
        return False
    return True


def _verificar_columnas(df: pd.DataFrame, esperadas: tuple[str, ...], nombre: str, res: ResultadoValidacion) -> bool:
    faltantes = [c for c in esperadas if c not in df.columns]
    if faltantes:
        res.errores.append(f"{nombre}: faltan columnas {faltantes}")
        return False
    extra = [c for c in df.columns if c not in esperadas]
    if extra:
        res.advertencias.append(f"{nombre}: columnas no documentadas {extra}")
    return True


def _verificar_obligatorias(df: pd.DataFrame, columnas: tuple[str, ...], id_col: str, res: ResultadoValidacion) -> None:
    for col in columnas:
        vacias = df.loc[df[col].str.strip() == "", id_col].tolist()
        if vacias:
            res.errores.append(f"'{col}' vacío en: {vacias}")


def _verificar_ids_unicos(df: pd.DataFrame, id_col: str, res: ResultadoValidacion) -> None:
    duplicados = df.loc[df[id_col].duplicated(), id_col].unique().tolist()
    if duplicados:
        res.errores.append(f"'{id_col}' duplicado: {duplicados}")


def contiene_dato_personal(texto: str) -> bool:
    """Detecta patrones de DNI o celular peruano en un texto libre."""
    return bool(_PATRON_DNI.search(texto) or _PATRON_CELULAR.search(texto))


# --- Validación de fuentes ------------------------------------------------------
def validar_fuentes(fuentes: pd.DataFrame) -> ResultadoValidacion:
    res = ResultadoValidacion()
    if not _verificar_columnas(fuentes, esquemas.COLUMNAS_FUENTES, "fuentes", res):
        return res
    _verificar_obligatorias(fuentes, esquemas.OBLIGATORIAS_FUENTES, "id_fuente", res)
    _verificar_ids_unicos(fuentes, "id_fuente", res)

    for fila in fuentes.itertuples(index=False):
        ident = fila.id_fuente
        if fila.tipo_fuente and fila.tipo_fuente not in esquemas.TIPOS_FUENTE:
            res.errores.append(f"{ident}: tipo_fuente desconocido '{fila.tipo_fuente}'")
        if fila.accesible and fila.accesible not in esquemas.ACCESIBILIDAD_FUENTE:
            res.errores.append(f"{ident}: accesible debe ser {esquemas.ACCESIBILIDAD_FUENTE}")
        if fila.url and not fila.url.startswith(("http://", "https://")):
            res.errores.append(f"{ident}: url no válida '{fila.url}'")
        if not fila.url:
            res.advertencias.append(f"{ident}: fuente sin url")

        consulta = _fecha_iso(fila.fecha_consulta) if fila.fecha_consulta else None
        if fila.fecha_consulta and consulta is None:
            res.errores.append(f"{ident}: fecha_consulta no es AAAA-MM-DD")
        if fila.fecha_publicacion:
            publicacion = _fecha_iso(fila.fecha_publicacion)
            if publicacion is None:
                res.errores.append(f"{ident}: fecha_publicacion no es AAAA-MM-DD")
            elif consulta and publicacion > consulta:
                res.errores.append(f"{ident}: fecha_publicacion posterior a fecha_consulta")
        elif fila.accesible != "no":
            res.advertencias.append(f"{ident}: sin fecha_publicacion")
    return res


# --- Validación de evidencias ---------------------------------------------------
def _validar_territorio(fila, res: ResultadoValidacion) -> None:
    ident = fila.id_evidencia
    precision = fila.precision_geografica
    if precision not in esquemas.PRECISIONES_GEOGRAFICAS:
        res.errores.append(f"{ident}: precision_geografica desconocida '{precision}'")
        return
    if precision != "region":
        if fila.provincia not in esquemas.PROVINCIAS_CUSCO:
            res.errores.append(f"{ident}: provincia '{fila.provincia}' no pertenece a Cusco")
    if precision in ("distrito", "centro_poblado", "punto") and not fila.distrito:
        res.errores.append(f"{ident}: precisión '{precision}' exige distrito")
    if precision in ("centro_poblado", "punto") and not fila.localidad:
        res.errores.append(f"{ident}: precisión '{precision}' exige localidad")

    if fila.ubigeo and not _PATRON_UBIGEO.match(fila.ubigeo):
        res.errores.append(f"{ident}: ubigeo '{fila.ubigeo}' no es un código de Cusco (08XXXX)")

    tiene_lat, tiene_lon = bool(fila.latitud), bool(fila.longitud)
    if precision == "punto" and not (tiene_lat and tiene_lon):
        res.errores.append(f"{ident}: precisión 'punto' exige latitud y longitud")
    if tiene_lat != tiene_lon:
        res.errores.append(f"{ident}: latitud y longitud deben registrarse juntas")
    elif tiene_lat:
        if not (_es_numero(fila.latitud) and _es_numero(fila.longitud)):
            res.errores.append(f"{ident}: coordenadas no numéricas")
        else:
            lat, lon = float(fila.latitud), float(fila.longitud)
            caja = config.CAJA_CUSCO
            if not (caja["lat_min"] <= lat <= caja["lat_max"] and caja["lon_min"] <= lon <= caja["lon_max"]):
                res.errores.append(f"{ident}: coordenadas ({lat}, {lon}) fuera de la región Cusco")


def _validar_contenido(fila, res: ResultadoValidacion) -> None:
    ident = fila.id_evidencia
    categoria, estado, variable = fila.categoria, fila.estado_verificacion, fila.variable

    if categoria not in esquemas.CATEGORIAS_EVIDENCIA:
        res.errores.append(f"{ident}: categoria desconocida '{categoria}'")
    elif estado not in esquemas.ESTADOS_VERIFICACION:
        res.errores.append(f"{ident}: estado_verificacion desconocido '{estado}'")
    elif estado not in esquemas.ESTADOS_PERMITIDOS_POR_CATEGORIA[categoria]:
        res.errores.append(f"{ident}: estado '{estado}' no corresponde a la categoría '{categoria}'")

    if variable != esquemas.VARIABLE_CUALITATIVA:
        if variable not in esquemas.VARIABLES:
            res.errores.append(f"{ident}: variable desconocida '{variable}'")
        elif esquemas.VARIABLES[variable] != categoria:
            res.errores.append(f"{ident}: variable '{variable}' pertenece a '{esquemas.VARIABLES[variable]}'")

    if fila.nivel_confianza not in esquemas.NIVELES_CONFIANZA:
        res.errores.append(f"{ident}: nivel_confianza debe ser {tuple(esquemas.NIVELES_CONFIANZA)}")

    if fila.valor:
        if not _es_numero(fila.valor):
            res.errores.append(f"{ident}: valor '{fila.valor}' no es numérico")
        elif float(fila.valor) < 0:
            res.errores.append(f"{ident}: valor negativo")
        if not fila.unidad:
            res.errores.append(f"{ident}: valor sin unidad")
        if variable == esquemas.VARIABLE_CUALITATIVA:
            res.errores.append(f"{ident}: una descripción cualitativa no lleva valor numérico")

    texto_libre = f"{fila.descripcion} {fila.observaciones}"
    if contiene_dato_personal(texto_libre):
        res.errores.append(f"{ident}: posible dato personal (DNI o celular) en texto libre")


def validar_evidencias(evidencias: pd.DataFrame, fuentes: pd.DataFrame) -> ResultadoValidacion:
    """Valida estructura, vocabularios, coherencia y trazabilidad del registro de evidencias."""
    res = ResultadoValidacion()
    if not _verificar_columnas(evidencias, esquemas.COLUMNAS_EVIDENCIAS, "evidencias", res):
        return res
    _verificar_obligatorias(evidencias, esquemas.OBLIGATORIAS_EVIDENCIAS, "id_evidencia", res)
    _verificar_ids_unicos(evidencias, "id_evidencia", res)

    fechas_publicacion = dict(zip(fuentes["id_fuente"], fuentes["fecha_publicacion"]))
    for fila in evidencias.itertuples(index=False):
        ident = fila.id_evidencia
        if fila.id_fuente not in fechas_publicacion:
            res.errores.append(f"{ident}: id_fuente '{fila.id_fuente}' no existe en fuentes.csv")

        if fila.fecha_evento:
            evento = _fecha_iso(fila.fecha_evento)
            publicacion = _fecha_iso(fechas_publicacion.get(fila.id_fuente, "") or "")
            if evento is None:
                res.errores.append(f"{ident}: fecha_evento no es AAAA-MM-DD")
            elif publicacion and evento > publicacion:
                res.errores.append(f"{ident}: fecha_evento posterior a la publicación de su fuente")
        else:
            res.advertencias.append(f"{ident}: sin fecha_evento")

        _validar_territorio(fila, res)
        _validar_contenido(fila, res)

    # Posibles duplicados: misma fuente, lugar, variable, fecha y valor; en afirmaciones sin cifra
    # (acciones, descripciones) también debe coincidir el texto
    claves = ["id_fuente", "provincia", "distrito", "localidad", "categoria", "variable", "fecha_evento", "valor"]
    con_cifra, sin_cifra = evidencias[evidencias["valor"] != ""], evidencias[evidencias["valor"] == ""]
    repetidas = (
        con_cifra.loc[con_cifra.duplicated(claves, keep=False), "id_evidencia"].tolist()
        + sin_cifra.loc[sin_cifra.duplicated(claves + ["descripcion"], keep=False), "id_evidencia"].tolist()
    )
    if repetidas:
        res.advertencias.append(f"posibles evidencias duplicadas: {repetidas}")
    return res


def validar_vacios(vacios: pd.DataFrame) -> ResultadoValidacion:
    res = ResultadoValidacion()
    if not _verificar_columnas(vacios, esquemas.COLUMNAS_VACIOS, "vacios", res):
        return res
    _verificar_obligatorias(vacios, ("id_vacio", "tema", "descripcion", "fecha_registro"), "id_vacio", res)
    _verificar_ids_unicos(vacios, "id_vacio", res)
    for fila in vacios.itertuples(index=False):
        if fila.provincia and fila.provincia not in esquemas.PROVINCIAS_CUSCO:
            res.errores.append(f"{fila.id_vacio}: provincia '{fila.provincia}' no pertenece a Cusco")
        if fila.fecha_registro and _fecha_iso(fila.fecha_registro) is None:
            res.errores.append(f"{fila.id_vacio}: fecha_registro no es AAAA-MM-DD")
    return res


# --- Preparación para análisis --------------------------------------------------
def tipar_evidencias(evidencias: pd.DataFrame) -> pd.DataFrame:
    """Convierte columnas numéricas y de fecha (usar solo después de validar)."""
    tipadas = evidencias.copy()
    for col in ("valor", "latitud", "longitud"):
        tipadas[col] = pd.to_numeric(tipadas[col].replace("", None), errors="coerce")
    tipadas["fecha_evento"] = pd.to_datetime(tipadas["fecha_evento"].replace("", None), errors="coerce")
    return tipadas


def unir_con_fuentes(evidencias: pd.DataFrame, fuentes: pd.DataFrame) -> pd.DataFrame:
    """Añade a cada evidencia los metadatos de su fuente (institución, enlace, fechas, tipo)."""
    metadatos = fuentes[["id_fuente", "institucion", "titulo", "url", "tipo_fuente", "fecha_publicacion", "fecha_consulta"]]
    return evidencias.merge(metadatos, on="id_fuente", how="left", validate="many_to_one")


# --- Escritura del registro -----------------------------------------------------
def reemplazar_por_prefijo(registro: pd.DataFrame, nuevas: pd.DataFrame, columna_id: str, prefijo: str) -> pd.DataFrame:
    """Sustituye las filas generadas por un proceso automático (identificadas por prefijo).

    Las filas curadas manualmente (otros prefijos) se conservan intactas, de modo que los
    scripts de extracción pueden ejecutarse de nuevo sin borrar el trabajo manual.
    """
    conservadas = registro[~registro[columna_id].str.startswith(prefijo)]
    combinado = pd.concat([conservadas, nuevas.astype(str)], ignore_index=True)
    return combinado.sort_values(columna_id, kind="stable").reset_index(drop=True)


def guardar_registro(registro: pd.DataFrame, ruta: Path, columnas: tuple[str, ...]) -> None:
    registro.loc[:, list(columnas)].to_csv(ruta, index=False, encoding="utf-8")
