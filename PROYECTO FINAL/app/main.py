from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.state import QuoteState
from app.repositories import ActiveSessionRepository
from app.ui.components import renderizar_tarjeta_imagen, renderizar_tarjeta_cotizacion, renderizar_panel_estado
from app.workflow import manejar_mensaje


st.set_page_config(page_title="Workflow agentico de eventos", page_icon="WF", layout="wide")

st.title("Workflow agentico para cotizacion de eventos")
st.caption("POC local con catalogo, cobertura, disponibilidad, RAG y cotizacion mockeados.")

active_sessions = ActiveSessionRepository()

if "quote_state" not in st.session_state:
    st.session_state.quote_state = QuoteState()
else:
    restored_state = active_sessions.obtener(st.session_state.quote_state.session_id)
    if restored_state:
        st.session_state.quote_state = restored_state

state: QuoteState = st.session_state.quote_state

if st.sidebar.button("Reiniciar conversacion"):
    active_sessions.reiniciar(state.session_id)
    st.session_state.quote_state = QuoteState()
    st.rerun()

renderizar_panel_estado(state)

for message in state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Ej.: Necesito bebidas para un matrimonio de 100 personas el 25 de octubre en Miraflores")
if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    response, updated_state = manejar_mensaje(prompt, state)
    st.session_state.quote_state = updated_state
    with st.chat_message("assistant"):
        st.markdown(response)
    st.rerun()

renderizar_tarjeta_cotizacion(state)
renderizar_tarjeta_imagen(state)

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
