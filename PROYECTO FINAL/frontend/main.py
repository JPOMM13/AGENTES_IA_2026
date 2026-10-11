from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

FRONTEND_ROOT = Path(__file__).resolve().parent
if str(FRONTEND_ROOT) not in sys.path:
    sys.path.insert(0, str(FRONTEND_ROOT))

from cliente_api import ErrorApiCotizador, consultar_sesion_api, crear_sesion_api, enviar_mensaje_api, reiniciar_sesion_api
from componentes import renderizar_panel_estado, renderizar_tarjeta_cotizacion, renderizar_tarjeta_imagen


st.set_page_config(page_title="Workflow agentico de eventos", page_icon="WF", layout="wide")

st.title("Workflow agentico para cotizacion de eventos")
st.caption("POC local con catalogo, cobertura, disponibilidad, RAG y cotizacion mockeados.")


# FRONTEND STREAMLIT: esta capa solo renderiza y conversa con FastAPI por HTTP.
def guardar_respuesta_api(respuesta_api: dict) -> None:
    """Guarda en Streamlit solo la respuesta JSON devuelta por el backend."""

    st.session_state.id_sesion = respuesta_api["id_sesion"]
    st.session_state.respuesta_api = respuesta_api


try:
    if "id_sesion" not in st.session_state:
        guardar_respuesta_api(crear_sesion_api())
    else:
        guardar_respuesta_api(consultar_sesion_api(st.session_state.id_sesion))
except ErrorApiCotizador as error:
    st.error(str(error))
    st.info("Levanta primero el backend con: uvicorn app.api:aplicacion --reload --port 8000")
    st.stop()

respuesta_api = st.session_state.respuesta_api

if st.sidebar.button("Reiniciar conversacion"):
    try:
        guardar_respuesta_api(reiniciar_sesion_api(respuesta_api["id_sesion"]))
    except ErrorApiCotizador as error:
        st.error(str(error))
    st.rerun()

renderizar_panel_estado(respuesta_api)

for message in respuesta_api.get("mensajes", []):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Ej.: Necesito bebidas para un matrimonio de 100 personas el 25 de octubre en Miraflores")
if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    try:
        respuesta_chat = enviar_mensaje_api(respuesta_api["id_sesion"], prompt)
        guardar_respuesta_api(respuesta_chat)
        with st.chat_message("assistant"):
            st.markdown(respuesta_chat["respuesta"])
    except ErrorApiCotizador as error:
        st.error(str(error))
    st.rerun()

renderizar_tarjeta_cotizacion(respuesta_api)
renderizar_tarjeta_imagen(respuesta_api)

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
