"""Vista Streamlit del asistente de eventos."""

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from cliente_api import ErrorApiCotizador, consultar_sesion_api, crear_sesion_api, enviar_mensaje_api, reiniciar_sesion_api
from componentes import renderizar_tarjeta_cotizacion, renderizar_tarjeta_imagen


st.set_page_config(page_title="Tus eventos", page_icon="💬", layout="wide", initial_sidebar_state="collapsed")
st.markdown(f"<style>{(RAIZ / 'estilos.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def guardar_respuesta(respuesta):
    st.session_state.id_sesion = respuesta["id_sesion"]
    st.session_state.respuesta_api = respuesta

    # La API no envía fechas: conservamos la hora local al mostrar cada mensaje.
    mensajes = respuesta.get("mensajes", [])
    anteriores = st.session_state.get("mensajes_anteriores", [])
    horas = st.session_state.get("horas_mensajes", [])
    while anteriores and mensajes[:len(anteriores)] != anteriores:
        anteriores = anteriores[1:]
        horas = horas[1:]
    horas += [datetime.now().strftime("%d/%m/%Y · %H:%M")] * (len(mensajes) - len(anteriores))
    st.session_state.mensajes_anteriores = mensajes
    st.session_state.horas_mensajes = horas


try:
    if "id_sesion" in st.session_state:
        guardar_respuesta(consultar_sesion_api(st.session_state.id_sesion))
    else:
        guardar_respuesta(crear_sesion_api())
except ErrorApiCotizador as error:
    st.error(f"No se pudo conectar con el agente: {error}")
    st.stop()

respuesta = st.session_state.respuesta_api
titulo, boton = st.columns([4, 1], vertical_alignment="bottom")
with titulo:
    st.title("Tus eventos")
    st.caption("Asesoría y cotización de servicios y bebidas para eventos")
with boton:
    if st.button("Nueva conversación", use_container_width=True):
        try:
            guardar_respuesta(reiniciar_sesion_api(respuesta["id_sesion"]))
            st.session_state.hora_saludo = datetime.now().strftime("%d/%m/%Y · %H:%M")
            st.rerun()
        except ErrorApiCotizador as error:
            st.error(str(error))

with st.container(border=True, key="chat_completo"):
    caja_mensajes = st.container(height=350, border=False, autoscroll=True)
    with caja_mensajes:
        mensajes = respuesta.get("mensajes", [])
        if "hora_saludo" not in st.session_state:
            st.session_state.hora_saludo = datetime.now().strftime("%d/%m/%Y · %H:%M")
        with st.chat_message("assistant"):
            st.write("¡Hola! ¿Qué evento estás organizando y qué productos o servicios necesitas?")
            st.caption(st.session_state.hora_saludo)
        for indice, mensaje in enumerate(mensajes):
            with st.chat_message(mensaje["role"]):
                st.markdown(mensaje["content"])
                st.caption(st.session_state.horas_mensajes[indice])

    texto = st.chat_input("Escribe tu mensaje...")
    if texto:
        # Mostramos el mensaje antes de esperar la respuesta de la API.
        with caja_mensajes:
            with st.chat_message("user"):
                st.markdown(texto)
                st.caption(datetime.now().strftime("%d/%m/%Y · %H:%M"))
        try:
            with st.spinner("Preparando respuesta..."):
                guardar_respuesta(enviar_mensaje_api(respuesta["id_sesion"], texto))
            st.rerun()
        except ErrorApiCotizador as error:
            st.error(f"No se pudo enviar el mensaje: {error}")

with st.expander("¿Qué puedo preguntar?"):
    st.write("Por ejemplo: Necesito bebidas para un matrimonio de 100 personas en Miraflores.")

renderizar_tarjeta_cotizacion(respuesta)
renderizar_tarjeta_imagen(respuesta)

with st.sidebar.expander("Datos técnicos"):
    st.json(respuesta.get("estado_panel", {}))
    estado = respuesta.get("estado", {})
    if estado.get("dimensionamiento"):
        st.json(estado["dimensionamiento"])
    if estado.get("resumen_derivacion"):
        st.json(estado["resumen_derivacion"])
    st.json(estado.get("trazas", [])[-12:])
