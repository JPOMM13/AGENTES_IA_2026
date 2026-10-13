"""Vista Streamlit del asistente de eventos."""

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from cliente_api import ErrorApiCotizador, consultar_sesion_api, crear_sesion_api, enviar_mensaje_api, reiniciar_sesion_api, subir_foto_api
from componentes import renderizar_tarjeta_cotizacion, renderizar_tarjeta_imagen


st.set_page_config(page_title="Tus eventos", page_icon="💬", layout="wide", initial_sidebar_state="collapsed")
st.markdown(f"<style>{(RAIZ / 'estilos.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

if not st.session_state.get("mayor_edad", False):
    with st.container(border=True, key="portada_edad"):
        st.title("Tus eventos")
        st.caption("Asesoría y cotización de servicios y bebidas para eventos")
        st.markdown("### Confirma tu edad")
        st.write("Este servicio incluye bebidas alcohólicas.")
        confirmado = st.checkbox("Confirmo que tengo 18 años o más")
        if st.button("Continuar", disabled=not confirmado, use_container_width=True):
            st.session_state.mayor_edad = True
            st.rerun()
    st.stop()


def guardar_respuesta(respuesta):
    # FRONTEND / SESION:
    # Streamlit solo conserva el id_sesion y la ultima respuesta renderizable.
    # La conversacion completa no se recupera desde aqui; cuando el frontend envia id_sesion,
    # el backend usa ese identificador para buscar la sesion activa en Redis si SESSION_STORE=redis.
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
        # FRONTEND / RECUPERACION DE SESION:
        # Si Streamlit ya tiene id_sesion, llama GET /api/sesiones/{id_sesion}.
        # En el backend, ese endpoint usa RepositorioSesionActiva.obtener(id_sesion).
        # Con SESSION_STORE=redis, esa llamada recupera desde Redis la key:
        # cotizador:eventos:sesion:{id_sesion}
        guardar_respuesta(consultar_sesion_api(st.session_state.id_sesion))
    else:
        # FRONTEND / CREACION DE SESION:
        # Si no hay id_sesion en Streamlit, llama POST /api/sesiones.
        # El backend crea EstadoCotizacion limpio y lo guarda como sesion activa.
        # Con SESSION_STORE=redis, esa sesion inicial se guarda en Redis con TTL.
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
            # FRONTEND / REINICIO:
            # Llama POST /api/sesiones/{id_sesion}/reiniciar.
            # En backend se elimina la sesion anterior; con SESSION_STORE=redis se borra la key de Redis.
            # Luego el backend crea y guarda una sesion nueva.
            guardar_respuesta(reiniciar_sesion_api(respuesta["id_sesion"]))
            st.session_state.hora_saludo = datetime.now().strftime("%d/%m/%Y · %H:%M")
            st.rerun()
        except ErrorApiCotizador as error:
            st.error(str(error))

with st.container(border=True, key="chat_completo"):
    caja_mensajes = st.container(height=350, border=False, autoscroll=True, key="historial_chat")
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
                if indice == len(mensajes) - 1 and mensaje["role"] == "assistant":
                    renderizar_tarjeta_cotizacion(respuesta)
                    renderizar_tarjeta_imagen(respuesta)

    texto = st.chat_input("Escribe tu mensaje...")
    if texto:
        # Mostramos el mensaje antes de esperar la respuesta de la API.
        with caja_mensajes:
            with st.chat_message("user"):
                st.markdown(texto)
                st.caption(datetime.now().strftime("%d/%m/%Y · %H:%M"))
        try:
            with st.spinner("Preparando respuesta..."):
                # FRONTEND / CHAT:
                # Envia POST /api/chat con id_sesion + mensaje.
                # El backend primero recupera la sesion activa por id_sesion.
                # Con SESSION_STORE=redis, esa recuperacion lee Redis antes de ejecutar LangGraph.
                # Al terminar el flujo, el backend vuelve a guardar el estado actualizado en Redis.
                guardar_respuesta(enviar_mensaje_api(respuesta["id_sesion"], texto))
            st.rerun()
        except ErrorApiCotizador as error:
            st.error(f"No se pudo enviar el mensaje: {error}")

# FOTO DEL LOCAL (opcional): con ella la imagen final de la cotizacion se compone sobre el espacio real del cliente.
with st.sidebar.expander("Foto de tu local (opcional)", expanded=False):
    archivo = st.file_uploader("Sube una foto del espacio del evento", type=["jpg", "jpeg", "png", "webp"], key="foto_local")
    if archivo is not None and st.session_state.get("foto_subida") != archivo.name:
        try:
            guardar_respuesta(subir_foto_api(respuesta["id_sesion"], archivo.getvalue(), archivo.name))
            st.session_state.foto_subida = archivo.name
            st.success("Foto recibida: la imagen de tu cotización se armará sobre tu local.")
        except ErrorApiCotizador as error:
            st.error(f"No se pudo subir la foto: {error}")
    if respuesta.get("foto_local"):
        st.caption("Foto del local cargada para esta conversación.")

with st.sidebar.expander("Datos técnicos"):
    st.json(respuesta.get("estado_panel", {}))
    estado = respuesta.get("estado", {})
    if estado.get("dimensionamiento"):
        st.json(estado["dimensionamiento"])
    if estado.get("resumen_derivacion"):
        st.json(estado["resumen_derivacion"])
    st.json(estado.get("trazas", [])[-12:])
