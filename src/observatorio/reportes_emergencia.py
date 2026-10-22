"""Extracción de emergencias desde los reportes diarios de la Oficina de Gestión del Riesgo de
Desastres (OGRD) del Congreso de la República, que compilan información de INDECI-COEN.

Cada página de un reporte presenta "tarjetas" (una por emergencia) con fecha, tipo de evento,
ubicación y evaluación de daños, dispuestas en columnas junto a un mapa. Como la extracción de
texto plano mezcla columnas, cada tarjeta se recorta por coordenadas a partir de la palabra
"EVENTO" y luego se interpreta su texto.

Las cifras de daños son evaluaciones preliminares reportadas por las autoridades locales a
INDECI; "cobertura natural destruida" NO equivale a área quemada medida por satélite.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pdfplumber

URL_BASE = "https://www3.congreso.gob.pe/Docs/riesgodesastres/files/"
INSTITUCION = "Congreso de la República – Oficina de Gestión del Riesgo de Desastres (compila INDECI-COEN)"

# Geometría de las tarjetas (puntos PDF). El encabezado con el departamento está ~35 pt sobre
# "EVENTO" y las tarjetas de una misma columna se superponen: la última línea de una tarjeta
# termina apenas 2–3 pt antes del encabezado de la siguiente.
_ANCHO_MAX_TARJETA = 178
_ENCABEZADO_MIN, _ENCABEZADO_MAX = 45, 28  # rango (pt sobre "EVENTO") donde se busca el encabezado
_ENCABEZADO_POR_DEFECTO = 37

# Líneas del pie de página o del mapa que pueden colarse en un recorte
_RUIDO = re.compile(
    r"^(OFICIAL[IÍ]A.*|OFICINA ?DE GESTI[OÓ]N.*|DEL RIESGO DE.*|DESASTRES|MAYOR|Fuente: ?INDECI\.?|[A-ZÁÉÍÓÚ]{1,4}|EVALU?|EV)$"
)

# Variantes ortográficas observadas en los reportes -> nombre de distrito usado por INEI.
# Deben confirmarse contra los límites oficiales en la Fase 3. "|" separa eventos que abarcan
# varios distritos (sus cifras no son divisibles entre ellos).
ALIAS_PROVINCIAS = {"Quispicanchis": "Quispicanchi", "La Convencion": "La Convención"}
ALIAS_DISTRITOS = {
    "Pichihua": "Pichigua",
    "Alto Pichihua": "Alto Pichigua",
    "Yaurisquey Paccaritambo": "Yaurisque|Paccaritambo",
    "Yaurisque y Paccaritambo": "Yaurisque|Paccaritambo",
    "Huyopata": "Huayopata",
    "Capi": "Ccapi",
    "Acha": "Accha",
    "Colca": "Colcha",
    "Paypata": "Pallpata",
}


@dataclass
class TarjetaEmergencia:
    """Una emergencia tal como aparece en una tarjeta del reporte."""

    departamento: str
    fecha_hora: datetime | None
    eventos: list[str]
    provincia: str
    distrito: str
    localidad: str
    texto_danos: str
    distrito_reportado: str = ""  # nombre tal como figura en el reporte, antes de aplicar alias
    texto_original: str = field(repr=False, default="")

    @property
    def es_incendio_forestal(self) -> bool:
        return any(_sin_espacios(e) == "incendioforestal" for e in self.eventos)

    @property
    def clave(self) -> str:
        """Identificador estable de la emergencia (fecha, hora y lugar)."""
        fecha = self.fecha_hora.isoformat() if self.fecha_hora else ""
        base = "|".join([fecha, _sin_espacios(self.provincia), _sin_espacios(self.distrito), _sin_espacios(self.localidad)])
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]


@dataclass
class Dano:
    """Una afirmación de daño interpretada desde el texto de una tarjeta."""

    categoria: str
    variable: str
    valor: float | None
    unidad: str
    descripcion: str


# --- Utilidades de texto --------------------------------------------------------
def _sin_espacios(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[\s.]", "", sin_tildes).lower()


def _limpiar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip(" .;,•")


def _numero(texto: str) -> float:
    return float(texto.replace(",", "."))


def normalizar_nombre(texto: str) -> str:
    """Separa palabras pegadas por la extracción ("SanPablo" -> "San Pablo") y limpia espacios."""
    separado = re.sub(r"([a-záéíóúñ])([A-ZÁÉÍÓÚÑ])", r"\1 \2", texto)
    return _limpiar(separado)


# --- Archivos -------------------------------------------------------------------
def metadatos_archivo(nombre: str) -> dict:
    """Obtiene número y fecha de un reporte a partir de su nombre (…NNN_DDMMAA.pdf)."""
    coincidencia = re.search(r"(\d{3})?_?(\d{2})(\d{2})(\d{2})\.pdf$", nombre)
    if not coincidencia:
        raise ValueError(f"Nombre de reporte no reconocido: {nombre}")
    numero, dia, mes, anio = coincidencia.groups()
    return {
        "numero_reporte": int(numero) if numero else None,
        "fecha_reporte": date(2000 + int(anio), int(mes), int(dia)),
        "url": URL_BASE + nombre,
    }


# --- Recorte de tarjetas --------------------------------------------------------
def _inicio_tarjeta(ancla: dict, palabras: list[dict]) -> float:
    """Ordenada superior de la tarjeta: el encabezado en mayúsculas sobre "EVENTO", si se detecta."""
    encabezados = [
        w["top"]
        for w in palabras
        if w["text"].isupper()
        and ancla["x0"] - 5 <= w["x0"] <= ancla["x0"] + 150
        and ancla["top"] - _ENCABEZADO_MIN <= w["top"] <= ancla["top"] - _ENCABEZADO_MAX
    ]
    return (min(encabezados) if encabezados else ancla["top"] - _ENCABEZADO_POR_DEFECTO) - 0.5


def recortar_tarjetas(pagina) -> list[str]:
    """Devuelve el texto de cada tarjeta de una página, recortada por coordenadas."""
    palabras = pagina.extract_words()
    anclas = [w for w in palabras if w["text"] == "EVENTO" and w["x0"] < pagina.width - 60]
    textos = []
    for ancla in anclas:
        debajo = [b for b in anclas if abs(b["x0"] - ancla["x0"]) < 30 and b["top"] > ancla["top"] + 20]
        # La siguiente columna (a cualquier altura) limita el ancho de la tarjeta
        columnas_derecha = [b["x0"] - 2 for b in anclas if b["x0"] > ancla["x0"] + 30]
        x_fin = min(columnas_derecha + [ancla["x0"] + _ANCHO_MAX_TARJETA, pagina.width])
        y_fin = min([_inicio_tarjeta(b, palabras) for b in debajo], default=pagina.height - 5)
        caja = (max(0, ancla["x0"] - 3), max(0, _inicio_tarjeta(ancla, palabras)), x_fin, y_fin)
        textos.append(pagina.crop(caja).extract_text() or "")
    return textos


def limpiar_texto_tarjeta(texto: str) -> str:
    """Quita ruido del pie de página y corta el texto si el recorte incluyó una segunda tarjeta."""
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    indices_fecha = [i for i, l in enumerate(lineas) if l.startswith("Fecha")]
    if len(indices_fecha) > 1:
        corte = indices_fecha[1]
        # La línea anterior a la segunda fecha es el encabezado de departamento de la otra tarjeta
        if corte > 0 and lineas[corte - 1].isupper():
            corte -= 1
        lineas = lineas[:corte]
    return "\n".join(l for l in lineas if not _RUIDO.match(l))


# --- Interpretación de una tarjeta ----------------------------------------------
def _seccion(lineas: list[str], inicio: str, fin: str | None) -> str:
    try:
        i = next(k for k, l in enumerate(lineas) if l.startswith(inicio))
    except StopIteration:
        return ""
    j = len(lineas)
    if fin:
        j = next((k for k, l in enumerate(lineas) if k > i and l.startswith(fin)), len(lineas))
    return " ".join(lineas[i + 1 : j])


def _campo(bloque: str, etiqueta: str) -> str:
    coincidencia = re.search(rf"{etiqueta}:\s*(.+?)(?=•|$)", bloque)
    return _limpiar(coincidencia.group(1)) if coincidencia else ""


def parsear_tarjeta(texto: str) -> TarjetaEmergencia | None:
    """Interpreta el texto limpio de una tarjeta; devuelve None si no tiene la estructura esperada."""
    lineas = texto.splitlines()
    if not lineas or not any(l.startswith("EVENTO") for l in lineas):
        return None

    fecha_hora = None
    coincidencia = re.search(r"Fecha:\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\s*(\d{1,2}):(\d{2})", texto)
    if coincidencia:
        dia, mes, anio, hora, minuto = (int(g) for g in coincidencia.groups())
        fecha_hora = datetime(anio + 2000 if anio < 100 else anio, mes, dia, hora, minuto)

    bloque_evento = _seccion(lineas, "EVENTO", "UBICACI")
    bloque_ubicacion = _seccion(lineas, "UBICACI", "EVALUACI")
    bloque_danos = _seccion(lineas, "EVALUACI", None)

    eventos = [_limpiar(e) for e in bloque_evento.split("•") if _limpiar(e)]
    provincia = normalizar_nombre(_campo(bloque_ubicacion, "Provincia"))
    provincia = ALIAS_PROVINCIAS.get(provincia, provincia)

    # "Distrito(s)" es el último campo de la ubicación; su texto puede continuar en líneas
    # siguientes, a veces con otra viñeta ("Urubamba/Sec. • Huascaray, CP Yanahuara").
    coincidencia = re.search(r"Distritos?:(.*)$", bloque_ubicacion)
    distrito_completo = _limpiar(coincidencia.group(1).replace("•", " ")) if coincidencia else ""
    distrito, _, localidad = distrito_completo.partition("/")
    distrito_reportado = normalizar_nombre(distrito)
    distrito = ALIAS_DISTRITOS.get(distrito_reportado, distrito_reportado)

    return TarjetaEmergencia(
        departamento=_campo(bloque_ubicacion, "Departamento"),
        fecha_hora=fecha_hora,
        eventos=eventos,
        provincia=provincia,
        distrito=distrito,
        localidad=normalizar_nombre(localidad),
        texto_danos=_limpiar(bloque_danos.replace("•", ";")).strip("; "),
        distrito_reportado=distrito_reportado,
        texto_original=texto,
    )


# --- Interpretación de daños ----------------------------------------------------
_PERSONAS = {
    "afectad": "personas_afectadas",
    "herid": "personas_lesionadas",
    "fallecid": "personas_fallecidas",
    "damnificad": "personas_damnificadas",
}
_VIVIENDAS = {"afectad": "viviendas_afectadas", "con daños": "viviendas_afectadas", "destruid": "viviendas_destruidas", "inhabitable": "viviendas_inhabitables"}


def interpretar_danos(texto: str) -> list[Dano]:
    """Convierte el texto de evaluación de daños en afirmaciones estructuradas.

    Si un daño se menciona sin cifra, se registra como descripción cualitativa para no
    inventar magnitudes.
    """
    danos: list[Dano] = []
    t = texto.lower()

    # Cobertura natural destruida / afectada (ha)
    cobertura = re.search(r"cobertura\s*nat(?:ural|\.)?\s*destruida\s*[:(]?\s*([\d]+(?:[.,]\d+)?)\s*\n?\s*ha", t)
    if cobertura:
        danos.append(Dano("dano_ambiental", "cobertura_natural_destruida", _numero(cobertura.group(1)), "ha", "Cobertura natural destruida"))
    elif re.search(r"cobertura\s*nat(?:ural|\.)?\s*destruida", t):
        danos.append(Dano("dano_ambiental", "descripcion_cualitativa", None, "", "Cobertura natural destruida (sin cifra)"))
    afectada = re.search(r"afectada\s*\(([\d]+(?:[.,]\d+)?)\s*ha\)", t)
    if afectada and "cobertura" in t:
        danos.append(Dano("dano_ambiental", "cobertura_natural_afectada", _numero(afectada.group(1)), "ha", "Cobertura natural afectada"))

    # Personas: "2 personas afectadas", "1 persona fallecida, 3 afectadas"
    personas_con_cifra = set()
    for cifra, estado in re.findall(r"(\d+)\s*(?:personas?\s*)?(afectad|herid|fallecid|damnificad)", t):
        variable = _PERSONAS[estado]
        personas_con_cifra.add(variable)
        danos.append(Dano("dano_humano", variable, float(cifra), "personas", variable.replace("_", " ").capitalize()))
    if re.search(r"(?<!\d\s)personas\s*afectadas", t) and "personas_afectadas" not in personas_con_cifra:
        danos.append(Dano("dano_humano", "descripcion_cualitativa", None, "", "Personas afectadas (sin cifra)"))

    # Viviendas
    viviendas_con_cifra = False
    for cifra, estado in re.findall(r"(\d+)\s*viviendas?\s*(afectad|con daños|destruid|inhabitable)", t):
        viviendas_con_cifra = True
        variable = _VIVIENDAS[estado]
        danos.append(Dano("dano_vivienda_infraestructura", variable, float(cifra), "viviendas", variable.replace("_", " ").capitalize()))
    if not viviendas_con_cifra and re.search(r"viviendas?\s*afectadas?", t):
        danos.append(Dano("dano_vivienda_infraestructura", "descripcion_cualitativa", None, "", "Viviendas afectadas (sin cifra)"))

    # Medios de vida
    ganado = re.search(r"ganader[ií]a\s*perdida(?:\s*\((\d+)\s*u\))?", t)
    if ganado:
        if ganado.group(1):
            danos.append(Dano("dano_productivo", "ganado_afectado", float(ganado.group(1)), "unidades", "Ganadería perdida"))
        else:
            danos.append(Dano("dano_productivo", "descripcion_cualitativa", None, "", "Ganadería perdida (sin cifra)"))
    cultivo = re.search(r"cultivos?\s*afectados?\s*\(([\d]+(?:[.,]\d+)?)\s*ha\)", t)
    if cultivo:
        danos.append(Dano("dano_productivo", "cultivos_afectados", _numero(cultivo.group(1)), "ha", "Cultivos afectados"))
    elif re.search(r"cultivos?\s*afectados?|agricultura\s*afectada", t):
        danos.append(Dano("dano_productivo", "descripcion_cualitativa", None, "", "Cultivos o agricultura afectados (sin cifra)"))

    # Infraestructura y servicios
    if re.search(r"energ[ií]a\s*el[eé]ctrica\s*afectada", t):
        danos.append(Dano("dano_vivienda_infraestructura", "descripcion_cualitativa", None, "", "Energía eléctrica afectada"))
    via = re.search(r"v[ií]a\s*(vecinal|nacional|departamental)?\s*afectada(?::\s*(\d+)\s*m)?", t)
    if via:
        tipo = via.group(1) or ""
        if via.group(2):
            danos.append(Dano("dano_vivienda_infraestructura", "infraestructura_afectada", float(via.group(2)), "m", f"Vía {tipo} afectada".replace("  ", " ")))
        else:
            danos.append(Dano("dano_vivienda_infraestructura", "descripcion_cualitativa", None, "", f"Vía {tipo} afectada".replace("  ", " ")))
    return danos


# --- Proceso de un archivo ------------------------------------------------------
def extraer_tarjetas_pdf(ruta: Path) -> list[TarjetaEmergencia]:
    """Extrae todas las tarjetas interpretables de un reporte (se omite la portada)."""
    tarjetas = []
    with pdfplumber.open(ruta) as pdf:
        for pagina in pdf.pages[1:]:
            for texto in recortar_tarjetas(pagina):
                tarjeta = parsear_tarjeta(limpiar_texto_tarjeta(texto))
                if tarjeta is not None:
                    tarjetas.append(tarjeta)
    return tarjetas


# --- Consolidación entre reportes -----------------------------------------------
@dataclass
class EmergenciaConsolidada:
    """Una emergencia única, con la versión más reciente de su tarjeta y los reportes que la citan."""

    tarjeta: TarjetaEmergencia
    archivo_ultimo: str
    reportes: list[str]
    posibles_duplicados: list[str] = field(default_factory=list)


_PALABRAS_GENERICAS = {"sector", "sectores", "comunidad", "localidad", "anexo", "cerro", "centro", "poblado"}


def _tokens_localidad(texto: str) -> set[str]:
    palabras = re.findall(r"[a-záéíóúñ]{5,}", texto.lower())
    return {p for p in palabras if p not in _PALABRAS_GENERICAS}


def consolidar(tarjetas_por_archivo: list[tuple[str, date, TarjetaEmergencia]]) -> list[EmergenciaConsolidada]:
    """Une las tarjetas repetidas (misma fecha, hora y lugar) conservando la del reporte más reciente.

    `tarjetas_por_archivo` contiene tuplas (nombre_archivo, fecha_reporte, tarjeta).
    """
    por_clave: dict[str, EmergenciaConsolidada] = {}
    for nombre, _, tarjeta in sorted(tarjetas_por_archivo, key=lambda x: x[1]):
        existente = por_clave.get(tarjeta.clave)
        if existente is None:
            por_clave[tarjeta.clave] = EmergenciaConsolidada(tarjeta, nombre, [nombre])
            continue
        if nombre not in existente.reportes:
            existente.reportes.append(nombre)
        # Se conserva la versión más reciente, salvo que pierda información de daños
        if tarjeta.texto_danos or not existente.tarjeta.texto_danos:
            existente.tarjeta, existente.archivo_ultimo = tarjeta, nombre
    emergencias = sorted(por_clave.values(), key=lambda e: e.tarjeta.fecha_hora or datetime.min)
    marcar_posibles_duplicados(emergencias)
    return emergencias


def _cobertura(tarjeta: TarjetaEmergencia) -> float | None:
    for dano in interpretar_danos(tarjeta.texto_danos):
        if dano.variable == "cobertura_natural_destruida":
            return dano.valor
    return None


def marcar_posibles_duplicados(emergencias: list[EmergenciaConsolidada], dias: int = 2) -> None:
    """Señala tarjetas que podrían describir el mismo incendio (no las elimina).

    Criterio: misma provincia, fechas separadas por `dias` o menos, y (a) comparten un nombre de
    localidad, o (b) mismo distrito con la misma cifra de cobertura destruida.
    """
    for i, a in enumerate(emergencias):
        for b in emergencias[i + 1 :]:
            ta, tb = a.tarjeta, b.tarjeta
            if ta.provincia != tb.provincia or not (ta.fecha_hora and tb.fecha_hora):
                continue
            if abs((tb.fecha_hora - ta.fecha_hora).days) > dias:
                continue
            distritos_a, distritos_b = set(ta.distrito.split("|")), set(tb.distrito.split("|"))
            comparte_lugar = bool(_tokens_localidad(ta.localidad) & _tokens_localidad(tb.localidad))
            misma_cifra = bool(distritos_a & distritos_b) and _cobertura(ta) is not None and _cobertura(ta) == _cobertura(tb)
            if comparte_lugar or misma_cifra:
                a.posibles_duplicados.append(tb.clave)
                b.posibles_duplicados.append(ta.clave)


# --- Conversión al registro de fuentes y evidencias -----------------------------
PREFIJO_FUENTE = "F-OGRD-"
PREFIJO_EVIDENCIA = "E-OGRD-"


def id_fuente(nombre_archivo: str) -> str:
    meta = metadatos_archivo(nombre_archivo)
    numero = meta["numero_reporte"] if meta["numero_reporte"] is not None else "S"
    return f"{PREFIJO_FUENTE}{meta['fecha_reporte']:%Y%m%d}-{numero}"


def fila_fuente(nombre_archivo: str, fecha_consulta: date, notas: str, carpeta_local: str) -> dict:
    meta = metadatos_archivo(nombre_archivo)
    numero = f"N.º {meta['numero_reporte']}" if meta["numero_reporte"] else "sin número"
    return {
        "id_fuente": id_fuente(nombre_archivo),
        "institucion": INSTITUCION,
        "titulo": f"Reporte de emergencias {numero} – {meta['fecha_reporte']:%d/%m/%Y}",
        "url": meta["url"],
        "tipo_fuente": "oficial_nacional",
        "fecha_publicacion": meta["fecha_reporte"].isoformat(),
        "fecha_consulta": fecha_consulta.isoformat(),
        "accesible": "si",
        "archivo_local": f"{carpeta_local}/{nombre_archivo}",
        "notas": notas,
    }


def filas_evidencia(emergencia: EmergenciaConsolidada) -> list[dict]:
    """Convierte una emergencia consolidada en filas del registro de evidencias."""
    t = emergencia.tarjeta
    lugar = ", ".join(x for x in [t.localidad, f"distrito {t.distrito.replace('|', ' y ')}", f"provincia {t.provincia}"] if x)
    observaciones = [f"Tarjeta citada en {len(emergencia.reportes)} reporte(s): {', '.join(emergencia.reportes)}"]
    if t.distrito_reportado != t.distrito:
        observaciones.append(f"distrito reportado como '{t.distrito_reportado}'")
    if "|" in t.distrito:
        observaciones.append("evento que abarca varios distritos; cifras no divisibles entre ellos")
    if emergencia.posibles_duplicados:
        ids = ", ".join(f"{PREFIJO_EVIDENCIA}{c}-00" for c in emergencia.posibles_duplicados)
        observaciones.append(f"posible mismo incendio que {ids}")

    base = {
        "id_fuente": id_fuente(emergencia.archivo_ultimo),
        "fecha_evento": t.fecha_hora.date().isoformat() if t.fecha_hora else "",
        "provincia": t.provincia,
        "distrito": t.distrito,
        "localidad": t.localidad,
        "ubigeo": "",
        "latitud": "",
        "longitud": "",
        "precision_geografica": "centro_poblado" if t.localidad else "distrito",
        "estado_verificacion": "dano_confirmado",
        "nivel_confianza": "alta",
        "fuente_oficial_citada": "INDECI-COEN",
        "observaciones": "; ".join(observaciones),
    }
    hora = f"{t.fecha_hora:%d/%m/%Y %H:%M}" if t.fecha_hora else "fecha no indicada"
    filas = [
        {
            **base,
            "id_evidencia": f"{PREFIJO_EVIDENCIA}{t.clave}-00",
            "categoria": "evento_incendio",
            "variable": "incendio_reportado",
            "valor": "1",
            "unidad": "evento",
            "descripcion": f"Incendio forestal registrado ({hora}) en {lugar}. Evaluación de daños: {t.texto_danos or 'sin detalle'}.",
        }
    ]
    for k, dano in enumerate(interpretar_danos(t.texto_danos), start=1):
        filas.append(
            {
                **base,
                "id_evidencia": f"{PREFIJO_EVIDENCIA}{t.clave}-{k:02d}",
                "categoria": dano.categoria,
                "variable": dano.variable,
                "valor": f"{dano.valor:g}" if dano.valor is not None else "",
                "unidad": dano.unidad,
                "descripcion": f"{dano.descripcion} – evaluación preliminar reportada a INDECI ({lugar}).",
            }
        )
    return filas
