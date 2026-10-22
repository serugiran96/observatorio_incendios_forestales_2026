"""D. Ficha territorial por distrito."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from observatorio import indicadores, restauracion, tablero
from observatorio.tablero import fmt

f = tablero.filtros()
inventario = tablero.inventario()
inv = tablero.aplicar(inventario, f)
ind = tablero.leer_procesado("indicadores_distrito.csv", dtype={"ubigeo": str})
fuentes, evidencias, vacios = tablero.registro_curado()

st.title("Ficha territorial")

conteo = indicadores.agregar_por_ubigeo(inv).set_index("ubigeo")["n_incendios"]
candidatos = ind[ind["ubigeo"].isin(f.distritos)] if f.distritos else (
    ind[ind["provincia"].isin(f.provincias)] if f.provincias else ind)
candidatos = candidatos.assign(n=candidatos["ubigeo"].map(conteo).fillna(0)).sort_values(
    ["n", "distrito"], ascending=[False, True])
etiquetas = dict(zip(candidatos["ubigeo"], candidatos["distrito"] + " (" + candidatos["provincia"] + ") · "
                     + candidatos["n"].astype(int).astype(str) + " incendios"))
ubigeo = st.selectbox("Distrito", list(etiquetas), format_func=etiquetas.get,
                      help="Ordenados por número de incendios con los filtros actuales.")
d = ind.set_index("ubigeo").loc[ubigeo]

st.subheader(f"{d['distrito']} · provincia de {d['provincia']}")
st.caption(f"UBIGEO {ubigeo} · población censada 2018: {fmt(d['poblacion_2018'])} · superficie: "
           f"{fmt(d['area_km2'])} km² · {f.describir()}")

del_distrito = inv[inv["ubigeo"].astype(str).str.split("|").apply(lambda us: ubigeo in us)]
sumas = indicadores.sumar_sin_duplicados(del_distrito) if len(del_distrito) else pd.Series(0, index=indicadores.CIFRAS)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Incendios", fmt(len(del_distrito)), border=True)
c2.metric("Cobertura (EDAN)", f"{fmt(sumas['cobertura_natural_destruida_ha'], 1)} ha", border=True)
c3.metric("Fallecidas / lesionadas", f"{fmt(sumas['personas_fallecidas'])} / {fmt(sumas['personas_lesionadas'])}",
          border=True)
c4.metric("Damnificadas", fmt(sumas["personas_damnificadas"]), border=True)
c5.metric("Abiertos al último reporte", fmt(del_distrito["estado"].eq("abierto al último reporte").sum()), border=True)

pestanas = st.tabs(["Incendios", "Atención", "Evidencias y fuentes", "Ecosistemas", "Restauración",
                    "Presupuesto", "Vacíos de información"])

with pestanas[0]:
    if del_distrito.empty:
        st.info("Sin incendios registrados con los filtros actuales.")
    else:
        sin_dato = {c: del_distrito[c].map(lambda v: "—" if pd.isna(v) else fmt(v, 1 if c.endswith("_ha") else 0))
                    for c in ["cobertura_natural_destruida_ha", "personas_damnificadas", "personas_afectadas"]}
        st.dataframe(
            del_distrito.assign(**sin_dato, posibles_duplicados=del_distrito["posibles_duplicados"].fillna(""))
            .sort_values("fecha_ocurrencia", ascending=False)[[
                "fecha_ocurrencia", "localidad", "estado", "cobertura_natural_destruida_ha", "personas_damnificadas",
                "personas_afectadas", "fecha_ultimo_reporte", "ultimo_reporte", "n_reportes", "posibles_duplicados"]],
            hide_index=True,
            column_config={
                "fecha_ocurrencia": st.column_config.DateColumn("Ocurrencia", format="DD/MM/YYYY"),
                "localidad": "Localidad (según el reporte)",
                "estado": "Estado al último reporte",
                "cobertura_natural_destruida_ha": "Cobertura destruida (ha)",
                "personas_damnificadas": "Damnificadas",
                "personas_afectadas": "Afectadas",
                "fecha_ultimo_reporte": st.column_config.DateColumn("Último reporte", format="DD/MM/YYYY"),
                "ultimo_reporte": "Fuente",
                "n_reportes": "Reportes",
                "posibles_duplicados": "Posibles duplicados",
            },
        )

with pestanas[1]:
    matriz = tablero.matriz_atencion()
    filas = matriz[matriz["ubigeo"].astype(str).str.split("|").apply(lambda us: ubigeo in us)]
    if filas.empty:
        st.info("Sin incendios en el periodo prioritario (1-sep a 21-oct-2026).")
    for fila in filas.itertuples():
        estado = tablero.ETIQUETAS_ATENCION.get(fila.estado_atencion, fila.estado_atencion)
        lugar = fila.localidad if isinstance(fila.localidad, str) and fila.localidad else "sin localidad"
        with st.expander(f"{fila.fecha_ocurrencia:%d-%m-%Y} · {lugar} · {estado}"):
            for titulo, valor in [("Daños", fila.danos), ("Personas y medios de vida", fila.personas_y_medios_de_vida),
                                  ("Necesidades documentadas", fila.necesidades_documentadas),
                                  ("Ayuda anunciada", fila.ayuda_anunciada),
                                  ("Ayuda entregada con evidencia", fila.ayuda_entregada_con_evidencia),
                                  ("Necesidades pendientes", fila.necesidades_pendientes),
                                  ("Instituciones", fila.instituciones), ("Fuentes", fila.fuentes)]:
                if isinstance(valor, str) and valor:
                    st.markdown(f"**{titulo}:** {valor}")
            st.caption(f"Última actualización: {fila.ultima_actualizacion} · motivos: {fila.motivos or 'ninguno'}")

with pestanas[2]:
    nombre = d["distrito"]
    del_lugar = evidencias[(evidencias["provincia"] == d["provincia"]) & (
        evidencias["distrito"].fillna("").str.split("|").apply(lambda ds: nombre in ds)
        | evidencias["ubigeo"].fillna("").eq(ubigeo))].copy()
    st.caption(f"{len(del_lugar)} evidencias registradas para el distrito (todas las fechas). Cada fila remite a "
               "su fuente con enlace y fechas.")
    del_lugar["estado"] = del_lugar["estado_verificacion"].map(tablero.ETIQUETAS_ATENCION)
    st.dataframe(
        del_lugar.sort_values("fecha_evento", ascending=False)[[
            "fecha_evento", "categoria", "variable", "valor", "unidad", "descripcion", "estado", "nivel_confianza",
            "institucion", "fecha_publicacion", "url", "id_evidencia"]],
        hide_index=True,
        column_config={
            "fecha_evento": "Fecha del hecho",
            "descripcion": st.column_config.TextColumn("Descripción", width="large"),
            "estado": "Estado de verificación",
            "nivel_confianza": "Confianza",
            "institucion": "Fuente",
            "fecha_publicacion": "Publicado",
            "url": st.column_config.LinkColumn("Enlace", display_text="abrir"),
        },
    )

with pestanas[3]:
    ecos = tablero.leer_procesado("ecosistemas_por_distrito.csv", dtype={"ubigeo": str})
    del_eco = ecos[ecos["ubigeo"] == ubigeo].sort_values("ha", ascending=False).head(10)
    if del_eco.empty:
        st.info("Sin datos de ecosistemas para este distrito.")
    else:
        del_eco["detalle"] = del_eco["ecosistema"] + ": " + del_eco["ha"].map(fmt) + " ha (" + \
            del_eco["pct_distrito"].map(lambda p: fmt(p, 1)) + " %)"
        st.markdown("**Ecosistemas presentes en el distrito (MINAM, 2018), en hectáreas**")
        st.plotly_chart(tablero.barras(del_eco, "ecosistema", "ha", horizontal=True, titulo_y="Hectáreas",
                                       texto_hover="detalle", alto=max(220, 34 * len(del_eco))))
        tablero.ver_tabla(del_eco[["ecosistema", "ha", "pct_distrito"]])
        st.caption("Son los ecosistemas del distrito, no necesariamente los que se quemaron.")

with pestanas[4]:
    medidas = tablero.leer_procesado("restauracion_medidas_distrito.csv", dtype={"ubigeo": str})
    del_d = medidas[medidas["ubigeo"] == ubigeo]
    if del_d.empty:
        st.info("Sin medidas: el distrito no registra incendios en el periodo prioritario.")
    else:
        del_d = del_d.assign(nivel=del_d["nivel_sustento"].map(restauracion.NIVELES_SUSTENTO))
        st.dataframe(del_d[["id_medida", "medida", "horizonte", "nivel", "estado_aplicacion", "motivo", "fuentes"]],
                     hide_index=True,
                     column_config={"medida": st.column_config.TextColumn("Medida", width="large"),
                                    "nivel": "Nivel de sustento", "estado_aplicacion": "Aplicación",
                                    "motivo": st.column_config.TextColumn("Motivo", width="large")})
        st.caption("Detalle y sustento de cada medida en la página Restauración.")

with pestanas[5]:
    lineas = tablero.leer_procesado("matriz_presupuesto.csv", dtype={"ubigeo": str})
    del_d = lineas[lineas["ubigeo"].astype(str) == ubigeo]
    st.dataframe(del_d[["intervencion", "problema", "cantidad", "unidad", "estado_costo", "recursos_documentados",
                        "donaciones_o_anuncios", "brecha", "entidades_competentes"]],
                 hide_index=True,
                 column_config={"intervencion": st.column_config.TextColumn("Intervención", width="large"),
                                "cantidad": st.column_config.NumberColumn("Cantidad", format="localized")})
    st.caption("Ningún costo unitario tiene fuente todavía: todos figuran como pendientes de cotización.")

with pestanas[6]:
    del_vacio = vacios[(vacios["distrito"].fillna("") == d["distrito"])
                       | ((vacios["provincia"].fillna("") == d["provincia"]) & vacios["distrito"].fillna("").eq(""))
                       | vacios["provincia"].fillna("").eq("")]
    st.dataframe(del_vacio[["id_vacio", "tema", "provincia", "distrito", "descripcion", "accion_sugerida"]],
                 hide_index=True,
                 column_config={"descripcion": st.column_config.TextColumn("Descripción", width="large"),
                                "accion_sugerida": st.column_config.TextColumn("Acción sugerida", width="medium")})
    st.caption("Incluye los vacíos del distrito, de su provincia y los de alcance regional.")
