from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.estado import EstadoCotizacion
from app.repositories import RepositorioSesionActiva
from app.ui.components import renderizar_tarjeta_imagen, renderizar_tarjeta_cotizacion, renderizar_panel_estado
from app.workflow import manejar_mensaje


st.set_page_config(page_title="Workflow agentico de eventos", page_icon="WF", layout="wide")

st.title("Workflow agentico para cotizacion de eventos")
st.caption("POC local con catalogo, cobertura, disponibilidad, RAG y cotizacion mockeados.")

sesiones_activas = RepositorioSesionActiva()

if "quote_state" not in st.session_state:
    st.session_state.quote_state = EstadoCotizacion()
else:
    estado_restaurado = sesiones_activas.obtener(st.session_state.quote_state.id_sesion)
    if estado_restaurado:
        st.session_state.quote_state = estado_restaurado

estado: EstadoCotizacion = st.session_state.quote_state

if st.sidebar.button("Reiniciar conversacion"):
    sesiones_activas.reiniciar(estado.id_sesion)
    st.session_state.quote_state = EstadoCotizacion()
    st.rerun()

renderizar_panel_estado(estado)

for message in estado.mensajes:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Ej.: Necesito bebidas para un matrimonio de 100 personas el 25 de octubre en Miraflores")
if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    respuesta, estado_actualizado = manejar_mensaje(prompt, estado)
    st.session_state.quote_state = estado_actualizado
    with st.chat_message("assistant"):
        st.markdown(respuesta)
    st.rerun()

renderizar_tarjeta_cotizacion(estado)
renderizar_tarjeta_imagen(estado)

with st.expander("Guia rapida"):
    st.markdown(
        """
        Prueba estos mensajes:

        - `Necesito bebidas para un matrimonio de 100 personas el 25 de octubre en Miraflores`
        - `Cuanto cuesta?`
        - `Me haces 15% de descuento?`
        - `Si, derivame con un asesor`
        - `Muestrame una imagen del evento`
        - `Que politica tienen para descuentos?`
        - `Necesito bebidas para 80 personas el 25 de octubre en Chosica`
        """
    )
