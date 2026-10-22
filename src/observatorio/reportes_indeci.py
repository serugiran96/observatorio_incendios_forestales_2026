"""Extracción de los reportes del COEN-INDECI (preliminares, complementarios e informes de
emergencia) sobre incendios forestales.

Cada PDF contiene: 1. Hechos (fecha de ocurrencia y descripción), 2. Ubicación (con código
SINPAD), 3. Evaluación de daños (tabla), 4. Acciones de respuesta y rehabilitación (entregas de
Bienes de Ayuda Humanitaria, atención médica, etc.) y 5. Fuentes.

Se extrae solo información institucional: la sección "Detalle de daños a la salud de las
personas" (edad, sexo, tipo de lesión) NO se procesa para no registrar datos personales.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pdfplumber

URL_PORTAL = "https://portal.indeci.gob.pe"
INSTITUCION = "INDECI – Centro de Operaciones de Emergencia Nacional (COEN)"
PREFIJO_FUENTE = "F-INDECI-"
PREFIJO_EVIDENCIA = "E-INDECI-"

_TIPOS = {"REPORTE COMPLEMENTARIO": "RC", "REPORTE PRELIMINAR": "RP", "INFORME DE EMERGENCIA": "IE"}
_ENCABEZADO = re.compile(
    r"(?P<tipo>REPORTE\s+COMPLEMENTARIO|REPORTE\s+PRELIMINAR|INFORME\s+DE\s+EMERGENCIA)\s+N\.?\s*[°º]?\s*(?P<numero>\d+)"
    r"\s*[-–]\s*(?P<fecha>\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)
_ACTUALIZACION = re.compile(r"\((?:Reporte|Informe)\s+N\.?\s*[°º]?\s*(\d+)\)", re.IGNORECASE)
_PIE = re.compile(r"Distribución: A los tres niveles.*?P\s?á\s?g\s?i\s?n\s?a\s+\d+\s*\|\s*\d+", re.DOTALL)
_FECHA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
# Muchos PDF marcan como rotados caracteres que se ven horizontales; se leen como texto horizontal
_LECTURA = {"line_dir_rotated": "ttb", "char_dir_rotated": "ltr"}


# --- Utilidades -----------------------------------------------------------------
def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


def _fecha(texto: str) -> date | None:
    coincidencia = _FECHA.search(texto)
    if not coincidencia:
        return None
    dia, mes, anio = (int(g) for g in coincidencia.groups())
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def _limpiar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip(" .;,-•")


# --- Estructuras ----------------------------------------------------------------
@dataclass
class DanoTabla:
    """Una celda de la tabla de daños: encabezado reconstruido, cifra y variable interpretada."""

    distrito: str
    encabezado: str
    valor: float
    categoria: str | None
    variable: str | None
    unidad: str


@dataclass
class Accion:
    """Una acción de respuesta reportada (sección 4.2 "Desarrollo de acciones")."""

    fecha: date | None
    nivel: str  # LOCAL, REGIONAL, NACIONAL
    entidad: str  # quien ejecuta la acción (si el reporte lo precisa) o quien la informa
    texto: str
    tipo: str | None  # entrega_bah, atencion_medica, insumos_pecuarios, coordinacion_bah, solicitud_ayuda, extincion, cierre, cierre_temporal


@dataclass
class ReporteIndeci:
    archivo: str
    tipo: str  # RC, RP, IE
    numero: int
    fecha_reporte: date
    actualizacion: int | None
    fecha_ocurrencia: date | None
    hora_ocurrencia: str
    descripcion: str
    provincia: str
    distritos: list[str]
    sector: str
    sinpad: str
    contexto: str = ""  # sección 3.2 "Información contextual" (estado del incendio, daños a la vida, etc.)
    danos: list[DanoTabla] = field(default_factory=list)
    danos_sin_interpretar: bool = False
    acciones: list[Accion] = field(default_factory=list)
    fuentes_citadas: list[str] = field(default_factory=list)
    rubros_bah: list[str] = field(default_factory=list)  # rubros del anexo "Bienes de ayuda humanitaria"

    @property
    def id_fuente(self) -> str:
        return f"{PREFIJO_FUENTE}{self.tipo}{self.numero}"

    @property
    def clave_evento(self) -> str:
        """Agrupa los reportes de un mismo incendio: lugar y fecha de ocurrencia."""
        base = "|".join([_sin_tildes(self.provincia), _sin_tildes("|".join(self.distritos)), str(self.fecha_ocurrencia)])
        return hashlib.sha1(base.encode()).hexdigest()[:8]

    @property
    def cerrado(self) -> bool:
        return any(a.tipo == "cierre" for a in self.acciones) and not any(a.tipo == "cierre_temporal" for a in self.acciones)


# --- Interpretación de la tabla de daños ----------------------------------------
def clasificar_encabezado(encabezado: str) -> tuple[str | None, str | None, str]:
    """Asigna (categoría, variable, unidad) a un encabezado reconstruido de la tabla de daños."""
    e = _sin_tildes(encabezado)
    unidad = "ha" if "(HA)" in e else "m" if "(M)" in e else "km" if "(KM)" in e else ""
    if "FALLECID" in e:
        return "dano_humano", "personas_fallecidas", "personas"
    if "DESAPARECID" in e:
        return "dano_humano", "personas_desaparecidas", "personas"
    if "LESIONAD" in e or "HERID" in e:
        return "dano_humano", "personas_lesionadas", "personas"
    if "COBERTURA" in e or "NATURAL" in e:
        variable = "cobertura_natural_destruida" if "DESTRUID" in e else "cobertura_natural_afectada"
        return "dano_ambiental", variable, unidad or "ha"
    if "CULTIVO" in e or "AGRICOLA" in e:
        variable = "cultivos_perdidos" if "PERDID" in e else "cultivos_afectados"
        return "dano_productivo", variable, unidad or "ha"
    if "GANAD" in e or "PECUARI" in e or "ANIMAL" in e or "ALPACA" in e or "OVINO" in e:
        variable = "ganado_perdido" if "PERDID" in e else "ganado_afectado"
        return "dano_productivo", variable, "unidades"
    infraestructura = ("RIEGO", "CANAL", "MANGUERA", "INFRAESTRUCTURA", "VIA ", "PUENTE", "EDUCATIVA",
                       "ESTABLECIMIENTO", "LOCAL COMUNAL", "ELECTRIC")
    if any(k in e for k in infraestructura):
        return "dano_vivienda_infraestructura", "infraestructura_afectada", unidad or "unidades"
    if "VIVIENDA" in e or "INHABITABLE" in e or "COLAPSAD" in e:
        if "INHABITABLE" in e:
            return "dano_vivienda_infraestructura", "viviendas_inhabitables", "viviendas"
        if "DESTRUID" in e or "COLAPSAD" in e:
            return "dano_vivienda_infraestructura", "viviendas_destruidas", "viviendas"
        return "dano_vivienda_infraestructura", "viviendas_afectadas", "viviendas"
    if "DAMNIFICAD" in e:
        return "dano_humano", "personas_damnificadas", "personas"
    if "AFECTAD" in e and ("PERSONA" in e or "VIDA" in e or "SALUD" in e):
        return "dano_humano", "personas_afectadas", "personas"
    return None, None, unidad


def _extraer_tabla_danos(pagina) -> tuple[list[DanoTabla], bool]:
    """Lee la tabla "Reporte de daños" de una página.

    Las cifras se ubican en las filas "DIST. <nombre>"; el encabezado de cada cifra se reconstruye
    con las palabras situadas encima cuya extensión horizontal la contiene. Devuelve también si
    había cifras que no pudieron asociarse a un encabezado conocido.
    """
    palabras = pagina.extract_words(**_LECTURA)
    inicio = next((w for w in palabras if w["text"].lower().startswith("reporte") and any(
        v["text"].lower() == "daños" and abs(v["top"] - w["top"]) < 3 for v in palabras)), None)
    if inicio is None:
        return [], False
    filas_distrito = [w for w in palabras if w["text"] == "DIST." and w["top"] > inicio["top"]]
    if not filas_distrito:
        # Hay tabla pero sin filas legibles (p. ej., encabezados y cifras rotados)
        return [], True
    lineas_actualizado = [w["top"] for w in palabras if w["text"] == "Actualizado" and w["top"] > inicio["top"]]
    primera_fila = min(w["top"] for w in filas_distrito)
    encabezados = [
        w for w in palabras
        if inicio["top"] + 6 < w["top"] < primera_fila - 12
        and not any(abs(w["top"] - y) < 3 for y in lineas_actualizado)
    ]
    danos, sin_interpretar = [], False
    for fila in filas_distrito:
        nombre = _limpiar(" ".join(
            w["text"] for w in palabras
            if abs(w["top"] - fila["top"]) < 3 and w["x0"] > fila["x1"] and not re.fullmatch(r"[\d.,]+", w["text"])
        ))
        cifras = [
            w for w in palabras
            if abs(w["top"] - fila["top"]) < 3 and re.fullmatch(r"\d+(?:[.,]\d+)?", w["text"]) and w["x0"] > fila["x1"]
        ]
        for cifra in cifras:
            centro = (cifra["x0"] + cifra["x1"]) / 2
            base = [w for w in encabezados if w["x0"] - 4 <= centro <= w["x1"] + 4]
            if base:
                # La extensión de la columna se toma de su encabezado más bajo; los encabezados de grupo
                # (p. ej. "VIVIENDA" sobre "DESTRUIDA" y "AFECTADA") se incluyen si se solapan con ella
                inferior = max(base, key=lambda w: w["top"])
                x0, x1 = inferior["x0"], inferior["x1"]
                base = [w for w in encabezados if w["x0"] < x1 + 2 and w["x1"] > x0 - 2] + base
            columna = sorted({id(w): w for w in base}.values(), key=lambda w: (round(w["top"]), w["x0"]))
            encabezado = _limpiar(" ".join(w["text"] for w in columna))
            categoria, variable, unidad = clasificar_encabezado(encabezado)
            if variable is None:
                sin_interpretar = True
            danos.append(DanoTabla(nombre.title(), encabezado, float(cifra["text"].replace(",", ".")), categoria, variable, unidad))
    return danos, sin_interpretar


# --- Interpretación de acciones -------------------------------------------------
_TIPOS_ACCION = [
    ("cierre_temporal", re.compile(r"cierre temporal", re.I)),
    ("cierre", re.compile(r"cierr[ea] (del?|el) (presente )?(reporte|informe|emergencia)|emergencia (ha sido|fue|fe) atendida|"
                          r"se cierra el presente", re.I)),
    ("entrega_bah", re.compile(
        r"(entreg[óo]|culmin[óo] (con )?la entrega|realiz[óo] la entrega|inici[óo] la entrega|distribuy[óo]|hizo entrega)[^.]{0,120}"
        r"(bienes de ayuda humanitaria|\bBAH\b|ayuda humanitaria|kits?\b|alimentos|v[íi]veres)", re.I)),
    ("insumos_pecuarios", re.compile(
        r"(entreg[óo]|brind[óo]|realiz[óo]|distribuy[óo])[^.]{0,80}(insumos veterinarios|veterinari|forraje|heno|"
        r"alimento[^.]{0,20}(animal|ganado)|sanidad animal|semillas)|atenci[óo]n (y evaluaci[óo]n )?de (los )?animales", re.I)),
    ("atencion_medica", re.compile(r"(brind[óo]|realiz[óo]|recibi[óo])[^.]{0,60}atenci[óo]n m[ée]dica|fue(ron)? atendid[oa]s? en", re.I)),
    ("solicitud_ayuda", re.compile(r"(solicit[óo]|solicita|requiere|requerimiento|gestion[óo] ante)[^.]{0,120}"
                                   r"(bienes de ayuda humanitaria|\bBAH\b|ayuda|apoyo|maquinaria|forraje|semillas)", re.I)),
    ("coordinacion_bah", re.compile(r"(coordina|coordin[óo]|programa|program[óo]|gestiona)[^.]{0,80}"
                                    r"(entrega de )?(bienes de ayuda humanitaria|\bBAH\b|ayuda humanitaria)", re.I)),
    ("extincion", re.compile(r"(fue|ha sido|qued[óo]|se encuentra)\s+(extinguido|sofocado|controlado|liquidado)|"
                             r"(culmin[óo]|logr[óo]) (la )?(extinci[óo]n|sofocar|controlar)|se extingui[óo]", re.I)),
]


def clasificar_accion(texto: str) -> str | None:
    for tipo, patron in _TIPOS_ACCION:
        if patron.search(texto):
            return tipo
    return None


_ENTIDAD = re.compile(
    r"^(Municipalidad|Puesto de Salud|Centro de Salud|Hospital|Red de Salud|Gerencia|Direcci[óo]n|Oficina|Compañ[íi]a|"
    r"Cuerpo|Ej[ée]rcito|Polic[íi]a|Agro Rural|AGRO RURAL|SERFOR|INIA|SENASA|Gobierno|Subprefectura|Instituto|Fuerza)",
)
_FIN_ACCIONES = re.compile(r"\n\s*(?:5\.\s*FUENTES?|FUENTES?:|\d\.\s*ANEXOS?|ANEXOS?\b|CONTROL DE CAMBIOS)", re.I)
# Firmas del control de cambios: nombres del personal que elabora el reporte (no se registran)
_FIRMA = re.compile(r"(Elaborado|Revisado|Actualizado|aprobado)\s+por|CONTROL DE CAMBIOS|Analista del Módulo", re.I)
_REFERENCIA_REPORTE = re.compile(r"^(COMPLEMENTARIO|PRELIMINAR|REPORTE|INFORME)\b.*(COER|COEN|HORAS)", re.I)


def _extraer_acciones(texto: str) -> list[Accion]:
    """Lee "4.2 Desarrollo de acciones" y el anexo "Cronología de acciones": bloques por
    nivel/entidad con viñetas fechadas. Puede devolver la misma acción dos veces (en 4.2 y en la
    cronología); la deduplicación se hace al generar evidencias."""
    acciones: list[Accion] = []
    inicio = re.search(r"4\.2\.?\s*Desarrollo de acciones", texto, re.I)
    if inicio:
        fin = _FIN_ACCIONES.search(texto[inicio.end():])
        acciones += _acciones_de_bloque(texto[inicio.end(): inicio.end() + fin.start()] if fin else texto[inicio.end():])
    # Encabezado real del anexo (no la lista de anexos de la sección 6)
    cronologia = re.search(r"ANEXO\s*2\s*\n\s*CRONOLOG[ÍI]A DE ACCIONES(.*?)(?:ANEXO\s*3|VISTAS? FOTOGR|CONTROL DE CAMBIOS|\Z)", texto, re.S)
    if cronologia:
        acciones += _acciones_de_bloque(cronologia.group(1))
    return acciones


def _acciones_de_bloque(bloque: str) -> list[Accion]:
    acciones: list[Accion] = []
    nivel, entidad, fecha_actual, buffer = "", "", None, []

    def volcar():
        if not buffer:
            return
        ejecutor = entidad
        # Una viñeta puede comenzar con la entidad ejecutora: "Municipalidad Distrital de X - Entregó..."
        if _ENTIDAD.match(buffer[0]) and len(buffer[0]) < 90 and not clasificar_accion(buffer[0]):
            ejecutor = _limpiar(buffer.pop(0))
        contenido = _limpiar(" ".join(buffer))
        contenido = re.sub(r"^.*?inform[óo] que:?\s*", "", contenido) if re.search(r"inform[óo] que", contenido) else contenido
        for frase in re.split(r"\s+-\s+|\s*✓\s*|(?<=\.)\s+(?=[A-ZÁÉÍÓÚ])", contenido):
            frase = _limpiar(frase)
            if len(frase) > 8 and not _REFERENCIA_REPORTE.match(frase) and not _FIRMA.search(frase):
                acciones.append(Accion(fecha_actual, nivel, ejecutor, frase, clasificar_accion(frase)))
        buffer.clear()

    bloque = _PIE.sub("", bloque)
    lineas = [
        l.strip() for l in bloque.splitlines()
        if l.strip() and not l.startswith("Actualizado al")
        and not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}|\d{1,2}:\d{2}\s*[Hh]oras", l.strip())  # cabeceras de la cronología
    ]
    k = 0
    while k < len(lineas):
        linea = lineas[k]
        if linea in ("LOCAL", "REGIONAL", "NACIONAL", "SECTORIAL"):
            volcar()
            fecha_actual = None
            nivel = linea
            entidad = lineas[k + 1] if k + 1 < len(lineas) else ""
            k += 2
            continue
        viñeta = re.match(r"^•\s*(\d{1,2}/\d{1,2}/\d{4})(.*)$", linea)
        if viñeta:
            volcar()
            fecha_actual = _fecha(viñeta.group(1))
            if viñeta.group(2).strip():
                buffer.append(viñeta.group(2))
        elif not re.search(r"mediante su|en su REPORTE", linea, re.I) and not _REFERENCIA_REPORTE.match(linea):
            buffer.append(linea)
        k += 1
    volcar()
    return acciones


# --- Anexo de Bienes de Ayuda Humanitaria ---------------------------------------
_RUBROS_BAH = ("TECHO", "ABRIGO", "ENSERES", "HERRAMIENTAS", "ALIMENTOS", "HIGIENE", "AGUA")


def _extraer_rubros_bah(texto: str) -> list[str]:
    """Rubros listados en el anexo "1. BIENES DE AYUDA HUMANITARIA" (bienes entregados y recibidos).

    Solo se registra qué rubros aparecen; las cantidades del anexo no se leen de forma fiable.
    """
    anexo = re.search(r"1\.\s*BIENES DE AYUDA HUMANITARIA(.*?)(?:ANEXO\s*2|CRONOLOG[ÍI]A|\Z)", texto, re.S | re.I)
    if not anexo or "ENTREGADO" not in _sin_tildes(anexo.group(1)).replace(" ", ""):
        return []
    contenido = _sin_tildes(anexo.group(1)).replace(" ", "")
    return [r for r in _RUBROS_BAH if r in contenido]


# --- Ubicación desde la descripción de los hechos -------------------------------
_PALABRAS_LUGAR = re.compile(
    r"\b(sector(?:es)?(?!\s+diversos)|comunidad(?:es)?|centros? poblados?|C\.\s?P\.|anexos?|cerros?|localidad|quebrada|paraje|"
    r"zona|caser[íi]o|urbanizaci[óo]n|asociaci[óo]n)\b", re.I)
def _ubicacion(descripcion: str) -> tuple[str, list[str], str]:
    """Obtiene (sector, distritos, provincia) de frases como "en el sector X, distrito de Y,
    provincia de Z", "distrito Y, provincia Z" o "distrito y provincia de Z"."""
    misma = re.search(r"distrito y provincia de\s+(?P<nombre>[^.,]+)", descripcion, re.I)
    if misma:
        nombre = misma.group("nombre").strip().title()
        previo = descripcion[: misma.start()]
    else:
        lugar = re.search(
            r"distritos?\s+(?:de\s+)?(?P<distritos>.+?),?\s+(?:y\s+)?(?:de\s+la\s+)?provincias?\s+(?:de\s+)?(?P<provincia>[^.,]+)",
            descripcion, re.I,
        )
        if not lugar:
            return "", [], ""
        previo = descripcion[: lugar.start()]
    # El sector empieza en la primera palabra de lugar (sector, comunidad, centro poblado...)
    sector = (_PALABRAS_LUGAR.search(previo)
              or re.search(r"\ben\s+(?:el|la|los|las)\s+(.+)$", previo, re.I)
              or re.search(r"\ben\s+([A-ZÁÉÍÓÚÑ][^,()]+?)[,\s]*$", previo))
    sector_txt = previo[sector.start():] if sector and sector.re is _PALABRAS_LUGAR else (sector.group(1) if sector else "")
    # Quitar conectores colgantes al final: "..., en el", "... del", "... de"
    sector_txt = _limpiar(re.sub(r"(?:[,\s]+(?:del?|en(?:\s+(?:el|la|los|las))?))+\s*$", "", sector_txt))
    if misma:
        return sector_txt, [nombre], nombre
    distritos = [d.strip().title() for d in re.split(r"\s+y\s+|,\s*", lugar.group("distritos")) if d.strip()]
    return sector_txt, distritos, lugar.group("provincia").strip().title()


# --- Lectura de un PDF ----------------------------------------------------------
def leer_reporte(ruta: Path) -> ReporteIndeci | None:
    """Interpreta un PDF del COEN-INDECI; devuelve None si no tiene la estructura esperada."""
    with pdfplumber.open(ruta) as pdf:
        paginas = list(pdf.pages)
        texto = "\n".join(p.extract_text(**_LECTURA) or "" for p in paginas)
        texto = _PIE.sub("", texto)
        danos, sin_interpretar = [], False
        for pagina in paginas[:4]:
            danos, sin_interpretar = _extraer_tabla_danos(pagina)
            if danos or sin_interpretar:  # se encontró la tabla de daños (legible o no)
                break

    encabezado = _ENCABEZADO.search(re.sub(r"\s+", " ", texto[:600]))
    if not encabezado:
        return None
    actualizacion = _ACTUALIZACION.search(texto[:800])

    hechos = re.search(r"1\.\s*HECHOS:?(.*?)2\.\s*UBICACI", texto, re.S)
    bloque_hechos = hechos.group(1) if hechos else ""
    fecha_ocurrencia = _fecha(bloque_hechos)
    hora = re.search(r"(\d{1,2}:\d{2})\s*horas", bloque_hechos)
    descripcion = re.sub(r"\d{1,2}/\d{1,2}/\d{4}|\d{1,2}:\d{2}\s*horas|Fecha y hora de|Descripción|la ocurrencia", " ", bloque_hechos)
    descripcion = _limpiar(descripcion)

    descripcion = _limpiar(re.sub(r"\d{1,2}:\d{2}\s*horas", " ", descripcion, flags=re.I))
    sector, distritos, provincia = _ubicacion(descripcion)
    sinpad = re.search(r"SINPAD\s*\n.*?\b(\d{5,7})\s*$", texto, re.M)
    fuentes = re.search(r"\n5\.\s*FUENTES:?(.*?)\n6\.\s*ANEXOS", texto, re.S)
    contexto = re.search(r"3\.2\.?\s*Información contextual(.*?)\n4\.\s*ACCIONES", texto, re.S | re.I)

    return ReporteIndeci(
        archivo=ruta.name,
        tipo=_TIPOS[_sin_tildes(re.sub(r"\s+", " ", encabezado.group("tipo")))],
        numero=int(encabezado.group("numero")),
        fecha_reporte=_fecha(encabezado.group("fecha")),
        actualizacion=int(actualizacion.group(1)) if actualizacion else None,
        fecha_ocurrencia=fecha_ocurrencia,
        hora_ocurrencia=hora.group(1) if hora else "",
        descripcion=descripcion,
        provincia=provincia,
        distritos=distritos,
        sector=sector,
        contexto=_limpiar(contexto.group(1)) if contexto else "",
        sinpad=sinpad.group(1) if sinpad else "",
        danos=danos,
        danos_sin_interpretar=sin_interpretar,
        acciones=_extraer_acciones(texto),
        rubros_bah=_extraer_rubros_bah(texto),
        fuentes_citadas=[_limpiar(l) for l in (fuentes.group(1).split("\n- ") if fuentes else []) if _limpiar(l)],
    )
