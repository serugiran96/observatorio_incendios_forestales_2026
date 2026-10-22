"""A. Resumen ejecutivo."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from observatorio import config, indicadores, tablero
from observatorio.tablero import fmt

f = tablero.filtros()
inv = tablero.aplicar(tablero.inventario(), f)
matriz = tablero.aplicar(tablero.matriz_atencion(), f, columna_estado="estado_evento")
fuentes, evidencias, vacios = tablero.registro_curado()
satelite = tablero.estado_satelital()

st.title("Cusco — del incendio a la recuperación")
st.markdown(
    f"Observatorio territorial de los incendios forestales en la región Cusco · "
    f"información al **{tablero.fecha_larga(config.FECHA_CORTE)}** · {f.describir()}"
)
st.info(
    "Las cifras de daños provienen de los reportes oficiales COEN-INDECI (evaluación de daños, EDAN). "
    "La «cobertura natural destruida» es una estimación de campo de las municipalidades, no una "
    "medición satelital. Que no haya un registro público de ayuda **no prueba** que no se entregó.",
    icon=":material/info:",
)

if inv.empty:
    st.warning("No hay incendios registrados con los filtros elegidos.")
    st.stop()

sumas = indicadores.sumar_sin_duplicados(inv)
ubigeos = inv["ubigeo"].astype(str).str.split("|").explode().unique()
abiertos = int(inv["estado"].eq("abierto al último reporte").sum())
compartida = pd.to_numeric(inv.loc[inv["varios_distritos"].astype(str).eq("True"), "cobertura_natural_destruida_ha"],
                           errors="coerce").sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Incendios registrados", fmt(len(inv)), border=True,
          help="Eventos en reportes COEN-INDECI y OGRD-Congreso, agrupados por lugar y fecha.")
c2.metric("Distritos con incendios", f"{len(ubigeos)} de 112", border=True)
c3.metric("Cobertura natural destruida", f"{fmt(sumas['cobertura_natural_destruida_ha'] + compartida)} ha", border=True,
          help="Suma de la EDAN sin posibles duplicados. No es área quemada medida por satélite.")
c4.metric("Abiertos al último reporte", fmt(abiertos), border=True,
          help="El último reporte público no informa cierre; puede deberse a falta de actualización.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Personas fallecidas (COEN)", fmt(sumas["personas_fallecidas"]), border=True,
          help="Solo reportes COEN-INDECI. La prensa informa más fallecidos en 2026; ver vacío V-0014.")
c2.metric("Personas lesionadas", fmt(sumas["personas_lesionadas"]), border=True)
c3.metric("Personas damnificadas", fmt(sumas["personas_damnificadas"]), border=True)
no_verificada = int(matriz["estado_atencion"].eq("atencion_no_verificada").sum())
c4.metric("Atención no verificada", fmt(no_verificada), border=True,
          help="Hay daños a personas, viviendas o medios de vida y no se encontró registro público de atención.")

st.subheader("Qué muestran los datos")
documentada = int(matriz["estado_atencion"].eq("atencion_documentada").sum())
con_danos_humanos = int(matriz["seguimiento_humanitario"].sum())
provincia_top = (inv.groupby("provincia").size().sort_values(ascending=False))
por_distrito = indicadores.agregar_por_ubigeo(inv).merge(
    tablero.leer_procesado("indicadores_distrito.csv", dtype={"ubigeo": str})[
        ["ubigeo", "distrito", "ecosistemas_principales"]], on="ubigeo")
top = por_distrito.nlargest(5, "cobertura_natural_destruida_ha")
top = top[top["cobertura_natural_destruida_ha"] > 0]
ecosistema_top = top["ecosistemas_principales"].fillna("").str.split(" \\(").str[0]
texto_top = ", ".join(f"{d} ({e.lower()})" for d, e in zip(top["distrito"], ecosistema_top))
hechos = [
    f"Se registran **{fmt(len(inv))} incendios** en **{len(ubigeos)} distritos**; la provincia con más "
    f"incendios es **{provincia_top.index[0]}** ({provincia_top.iloc[0]}).",
    f"**{con_danos_humanos} incendios** del periodo prioritario afectaron a personas, viviendas o medios de vida. "
    f"La atención está documentada en **{documentada}**; en **{no_verificada}** no se encontró registro público "
    "de atención (*atención no verificada*).",
    f"La EDAN suma **{fmt(sumas['cobertura_natural_destruida_ha'] + compartida)} ha** de cobertura natural destruida. "
    f"Distritos con más hectáreas y su ecosistema principal (MINAM): {texto_top or 'sin cifras'}. "
    "El ecosistema principal del distrito no es necesariamente el que se quemó.",
    f"Hay **{len(vacios)} vacíos de información** registrados: reportes no recuperables, fallecidos sin "
    "registro oficial localizado y cifras regionales que no concuerdan.",
]
for h in hechos:
    st.markdown(f"- {h}")

st.subheader("Qué no se puede afirmar todavía")
pendiente = "pendiente: requiere credenciales de Earth Engine y NASA FIRMS" if not satelite["gee"] else "disponible"
st.markdown(
    f"- **Área quemada medida por satélite:** {pendiente}. Mientras tanto, las hectáreas son las de la EDAN.\n"
    "- **Ubicación exacta:** ninguna fuente oficial publica coordenadas; el mapa ubica cada incendio en su distrito.\n"
    "- **Fallecidos:** los reportes COEN registran menos fallecidos que la prensa; la cifra oficial no está "
    "actualizada en las fuentes revisadas.\n"
    "- **Ayuda recibida:** los reportes describen entregas en pocos casos; la ausencia de registro no equivale "
    "a ausencia de ayuda."
)

st.subheader("Evolución y distribución")
izquierda, derecha = st.columns(2)
with izquierda:
    st.markdown("**Incendios por semana de ocurrencia**")
    inicio_semana = inv["fecha_ocurrencia"].dt.to_period("W-SUN").dt.start_time  # lunes de cada semana
    semanas = inicio_semana.value_counts().sort_index().rename("incendios").rename_axis("fecha_ocurrencia").reset_index()
    semanas["detalle"] = "Semana del " + semanas["fecha_ocurrencia"].dt.strftime("%d-%m-%Y") + ": " + \
        semanas["incendios"].astype(str) + " incendios"
    figura = tablero.barras(semanas, "fecha_ocurrencia", "incendios", titulo_x="Semana (inicio, lunes)",
                            titulo_y="Incendios", texto_hover="detalle")
    figura.update_xaxes(type="date", tickformat="%d/%m", dtick=7 * 24 * 3600 * 1000)
    st.plotly_chart(figura)
    st.caption("La semana que contiene la fecha de corte está incompleta.")
    tablero.ver_tabla(semanas[["fecha_ocurrencia", "incendios"]].rename(columns={"fecha_ocurrencia": "inicio_semana"}))
with derecha:
    st.markdown("**Cobertura natural destruida por provincia (ha, EDAN)**")
    por_provincia = (inv.groupby("provincia")
                     .apply(lambda g: indicadores.sumar_sin_duplicados(g)["cobertura_natural_destruida_ha"],
                            include_groups=False)
                     .rename("ha").reset_index().sort_values("ha", ascending=False))
    por_provincia["detalle"] = por_provincia["provincia"] + ": " + por_provincia["ha"].map(fmt) + " ha"
    st.plotly_chart(tablero.barras(por_provincia, "provincia", "ha", horizontal=True, titulo_y="Hectáreas",
                                   texto_hover="detalle"))
    tablero.ver_tabla(por_provincia[["provincia", "ha"]])
tablero.aviso_fuente("reportes COEN-INDECI y OGRD-Congreso; sin posibles duplicados; los incendios de varios "
                     "distritos no se reparten.")

st.subheader("Contexto regional")
st.caption("Cifras de otras fuentes, con su estado de verificación. No se suman al inventario.")
contexto = evidencias[
    evidencias["variable"].isin(["numero_incendios", "superficie_afectada", "personas_fallecidas"])
    & evidencias["provincia"].fillna("").eq("")
].copy()
contexto["valor"] = pd.to_numeric(contexto["valor"], errors="coerce")
contexto["estado"] = contexto["estado_verificacion"].map(tablero.ETIQUETAS_ATENCION)
st.dataframe(
    contexto[["descripcion", "valor", "estado", "institucion", "fecha_publicacion", "url"]],
    hide_index=True,
    column_config={
        "descripcion": st.column_config.TextColumn("Dato", width="large"),
        "valor": st.column_config.NumberColumn("Cifra", format="localized"),
        "estado": "Estado de verificación",
        "institucion": "Fuente",
        "fecha_publicacion": "Publicado",
        "url": st.column_config.LinkColumn("Enlace", display_text="abrir"),
    },
)
