from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.cliente_api import ErrorApiCotizador, consultar_sesion_api, crear_sesion_api, enviar_mensaje_api, reiniciar_sesion_api
from app.estado import EstadoCotizacion
from app.ui.componentes import renderizar_tarjeta_imagen, renderizar_tarjeta_cotizacion, renderizar_panel_estado


st.set_page_config(page_title="Workflow agentico de eventos", page_icon="WF", layout="wide")

st.title("Workflow agentico para cotizacion de eventos")
st.caption("Asesoria y cotizacion de servicios y bebidas para eventos.")


# FRONTEND STREAMLIT: esta capa solo renderiza y conversa con FastAPI por HTTP.
def cargar_estado_desde_respuesta(respuesta_api: dict) -> EstadoCotizacion:
    """Reconstruye el estado para que los componentes visuales actuales puedan renderizar."""
    return EstadoCotizacion.desde_diccionario_persistido(respuesta_api["estado"])


try:
    if "id_sesion" not in st.session_state:
        respuesta_inicial = crear_sesion_api()
        st.session_state.id_sesion = respuesta_inicial["id_sesion"]
        st.session_state.estado_api = respuesta_inicial["estado"]
    else:
        respuesta_actual = consultar_sesion_api(st.session_state.id_sesion)
        st.session_state.estado_api = respuesta_actual["estado"]
except ErrorApiCotizador as error:
    st.error(str(error))
    st.info("Levanta primero el backend con: uvicorn app.api:aplicacion --reload --port 8000")
    st.stop()

estado: EstadoCotizacion = cargar_estado_desde_respuesta({"estado": st.session_state.estado_api})

if st.sidebar.button("Reiniciar conversacion"):
    try:
        respuesta_reinicio = reiniciar_sesion_api(estado.id_sesion)
        st.session_state.id_sesion = respuesta_reinicio["id_sesion"]
        st.session_state.estado_api = respuesta_reinicio["estado"]
    except ErrorApiCotizador as error:
        st.error(str(error))
    st.rerun()

renderizar_panel_estado(estado)

for message in estado.mensajes:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Ej.: Necesito bebidas para un matrimonio de 100 personas el 25 de octubre en Miraflores")
if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    try:
        respuesta_api = enviar_mensaje_api(estado.id_sesion, prompt)
        st.session_state.id_sesion = respuesta_api["id_sesion"]
        st.session_state.estado_api = respuesta_api["estado"]
        with st.chat_message("assistant"):
            st.markdown(respuesta_api["respuesta"])
    except ErrorApiCotizador as error:
        st.error(str(error))
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
