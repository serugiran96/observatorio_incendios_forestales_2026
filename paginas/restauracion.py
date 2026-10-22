"""F. Restauración: medidas por ecosistema con su sustento, separando lo justificado de las hipótesis."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from observatorio import indicadores, restauracion, tablero
from observatorio.tablero import fmt

f = tablero.filtros()
inv = tablero.aplicar(tablero.inventario(), f)
fuentes, _, _ = tablero.registro_curado()
medidas = restauracion.cargar_medidas()
por_distrito = tablero.leer_procesado("restauracion_medidas_distrito.csv", dtype={"ubigeo": str})
ind = tablero.leer_procesado("indicadores_distrito.csv", dtype={"ubigeo": str})
colores = tablero.paleta()

st.title("Restauración")
st.caption("Horizonte de 3 meses a 5 años, salvo las medidas de emergencia antes de las lluvias.")
st.info(
    "**No se recomienda la reforestación indiscriminada.** Los distritos con más cobertura destruida tienen sobre "
    "todo pajonal, matorral y bofedales (ver gráfico), que no son bosque: la base es la regeneración natural, la protección "
    "del suelo y del agua, y el monitoreo. Plantar solo especies nativas, en bosques nativos y donde no haya rebrote.",
    icon=":material/eco:",
)

st.subheader("Ecosistemas de los distritos más afectados")
afectados = indicadores.agregar_por_ubigeo(inv).merge(ind.drop(columns=["n_incendios", *indicadores.CIFRAS], errors="ignore"),
                                                     on="ubigeo")
afectados = afectados.nlargest(12, "cobertura_natural_destruida_ha")
afectados = afectados[afectados["cobertura_natural_destruida_ha"] > 0]
grupos = {"ha_pajonal": "Pajonal", "ha_bofedal": "Bofedal", "ha_bosque": "Bosque nativo",
          "ha_matorral": "Matorral", "ha_zona_agricola": "Zona agrícola"}
if afectados.empty:
    st.info("Sin cifras de cobertura destruida con los filtros actuales.")
else:
    figura = go.Figure()
    for i, (col, nombre) in enumerate(grupos.items()):
        pct = afectados[col].fillna(0) / (afectados["area_km2"] * 100) * 100
        figura.add_bar(
            y=afectados["distrito"], x=pct, name=nombre, orientation="h",
            marker={"color": colores["categorica"][i], "line": {"width": 2, "color": colores["superficie"]}},
            hovertemplate=f"{nombre}: " + "%{x:.1f} % del distrito<extra>%{y}</extra>",
        )
    figura.update_layout(barmode="stack", height=420, margin={"l": 8, "r": 8, "t": 8, "b": 8},
                         xaxis_title="% de la superficie del distrito", legend={"orientation": "h", "y": -0.18, "traceorder": "normal"},
                         bargap=0.3)
    figura.update_yaxes(autorange="reversed")
    st.plotly_chart(figura)
    st.caption("Distritos con más cobertura natural destruida según la EDAN, de mayor a menor. El resto de la "
               "superficie son otros ecosistemas (glaciar, lagunas, vegetación secundaria, etc.). Muestra los "
               "ecosistemas presentes, no los quemados.")
    tabla = afectados[["provincia", "distrito", "cobertura_natural_destruida_ha", *grupos]].rename(columns=grupos)
    tablero.ver_tabla(tabla)

st.subheader("Catálogo de medidas")
titulos = dict(zip(fuentes["id_fuente"], fuentes["titulo"]))
enlaces = dict(zip(fuentes["id_fuente"], fuentes["url"]))
for nivel, etiqueta in restauracion.NIVELES_SUSTENTO.items():
    del_nivel = medidas[medidas["nivel_sustento"] == nivel]
    if del_nivel.empty:
        continue
    st.markdown(f"**{etiqueta}** ({len(del_nivel)})")
    for m in del_nivel.itertuples():
        with st.expander(f"{m.id_medida} · {m.medida} · {m.horizonte}"):
            st.markdown(f"{m.descripcion}\n\n**Cuándo aplica:** {m.condicion_aplicacion}\n\n"
                        f"**Sustento:** {m.sustento}\n\n**Indicador de seguimiento:** {m.indicador_monitoreo}\n\n"
                        f"**Entidades de referencia:** {m.entidades_referenciales}")
            referencias = [f"- [{i}] [{titulos.get(i, i)}]({enlaces.get(i, '')})"
                           for i in (x.strip() for x in m.fuentes.split(";"))]
            st.markdown("**Fuentes:**\n" + "\n".join(referencias))

st.subheader("Medidas por distrito")
st.caption("✔ aplica · ◐ verificar en campo (o con el análisis satelital) · vacío: no corresponde. "
           "Solo distritos con incendios en el periodo prioritario.")
vista = por_distrito
if f.provincias:
    vista = vista[vista["provincia"].isin(f.provincias)]
if f.distritos:
    vista = vista[vista["ubigeo"].isin(f.distritos)]
if vista.empty:
    st.info("Sin distritos con los filtros actuales.")
else:
    simbolo = {"aplica": "✔", "verificar en campo": "◐"}
    tabla = vista.assign(s=vista["estado_aplicacion"].map(simbolo)).pivot_table(
        index=["provincia", "distrito", "n_incendios", "cobertura_destruida_ha_edan"], columns="id_medida",
        values="s", aggfunc="first", fill_value="").reset_index().sort_values(
        "cobertura_destruida_ha_edan", ascending=False)
    nombres = dict(zip(medidas["id_medida"], medidas["medida"]))
    st.dataframe(tabla, hide_index=True, column_config={
        "n_incendios": "Incendios", "cobertura_destruida_ha_edan": st.column_config.NumberColumn("Cobertura (ha)"),
        **{k: st.column_config.TextColumn(k, help=v, width="small") for k, v in nombres.items()},
    })
    st.download_button("Descargar medidas por distrito (CSV)", vista.to_csv(index=False),
                       file_name="restauracion_medidas_distrito.csv", mime="text/csv", icon=":material/download:")
