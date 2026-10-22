"""Dashboard del observatorio «Cusco — del incendio a la recuperación».

Uso:
    uv run streamlit run app.py

Lee solo data/processed y el registro curado (data/raw/registro). Las cifras provienen de fuentes
identificadas; el dashboard no contiene datos ficticios ni de demostración.
"""

from __future__ import annotations

import streamlit as st

from observatorio import config, tablero

st.set_page_config(
    page_title="Cusco — del incendio a la recuperación",
    page_icon="🔥",
    layout="wide",
)

paginas = {
    "Panorama": [
        st.Page("paginas/resumen.py", title="Resumen ejecutivo", icon=":material/summarize:", default=True),
        st.Page("paginas/mapa.py", title="Mapa", icon=":material/map:"),
        st.Page("paginas/ficha.py", title="Ficha territorial", icon=":material/location_on:"),
    ],
    "Respuesta y recuperación": [
        st.Page("paginas/atencion.py", title="Atención inmediata", icon=":material/medical_services:"),
        st.Page("paginas/restauracion.py", title="Restauración", icon=":material/eco:"),
        st.Page("paginas/presupuesto.py", title="Presupuesto y brechas", icon=":material/payments:"),
    ],
    "Transparencia": [
        st.Page("paginas/metodologia.py", title="Metodología y fuentes", icon=":material/menu_book:"),
    ],
}
navegacion = st.navigation(paginas)

# --- C. Filtros globales -----------------------------------------------------------------
inventario = tablero.inventario()
with st.sidebar:
    st.markdown("**Filtros** · se aplican a todas las páginas")
    fecha_min = inventario["fecha_ocurrencia"].min().date()
    rango = st.date_input(
        "Fecha de ocurrencia",
        value=config.PERIODO_PRIORITARIO,
        min_value=fecha_min,
        max_value=config.FECHA_CORTE,
        format="DD/MM/YYYY",
        help="Periodo prioritario: 1-sep a 21-oct-2026. Los reportes indexados empiezan en "
             f"{fecha_min:%d-%m-%Y}; antes de esa fecha el inventario no es exhaustivo.",
    )
    inicio, fin = (rango if isinstance(rango, (list, tuple)) and len(rango) == 2 else config.PERIODO_PRIORITARIO)
    provincias = st.multiselect("Provincia", sorted(inventario["provincia"].dropna().unique()), placeholder="Todas")
    distritos = tablero.leer_geo("limites_cusco_distritos.geojson")
    opciones = distritos[distritos["provincia"].isin(provincias)] if provincias else distritos
    etiquetas = dict(zip(opciones["ubigeo"], opciones["distrito"] + " (" + opciones["provincia"] + ")"))
    seleccion = st.multiselect("Distrito", sorted(etiquetas, key=etiquetas.get), format_func=etiquetas.get,
                              placeholder="Todos")
    estados = st.multiselect("Estado del incendio al último reporte", sorted(inventario["estado"].dropna().unique()),
                             placeholder="Todos")
    st.session_state["filtros"] = tablero.Filtros(inicio, fin, provincias, seleccion, estados)

    st.divider()
    st.caption(
        f"Fecha de corte: **{tablero.fecha_larga(config.FECHA_CORTE)}**. "
        "Proyecto universitario; no reemplaza los registros oficiales de INDECI, COEN ni del "
        "Gobierno Regional del Cusco."
    )

navegacion.run()
