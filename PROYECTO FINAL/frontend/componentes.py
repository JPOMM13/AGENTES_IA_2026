from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st


# FRONTEND STREAMLIT: muestra el estado interno recibido por API para depurar el flujo del agente.
def renderizar_panel_estado(respuesta_api: dict[str, Any]) -> None:
    """Muestra estado, dimensionamiento, derivacion y trazas usando solo JSON del backend."""

    estado = respuesta_api.get("estado", {})
    estado_panel = respuesta_api.get("estado_panel", {})
    st.sidebar.subheader("Estado de la solicitud")
    st.sidebar.json(estado_panel)

    if estado.get("dimensionamiento"):
        st.sidebar.subheader("Dimensionamiento mock")
        st.sidebar.json(estado["dimensionamiento"])

    if estado.get("resumen_derivacion"):
        st.sidebar.subheader("Resumen para asesor")
        st.sidebar.json(estado["resumen_derivacion"].get("summary", {}))

    with st.sidebar.expander("Trazas"):
        st.json(estado.get("trazas", [])[-12:])


# FRONTEND STREAMLIT: muestra totales y detalle economico de la cotizacion devuelta por API.
def renderizar_tarjeta_cotizacion(respuesta_api: dict[str, Any]) -> None:
    """Muestra tarjeta resumida de la cotizacion generada por el backend."""

    cotizacion = respuesta_api.get("cotizacion")
    if not cotizacion:
        return
    st.subheader("Cotizacion mock")
    st.metric("Total", f"{cotizacion['currency']} {cotizacion['total']:.2f}")
    st.write(f"Subtotal: {cotizacion['currency']} {cotizacion['subtotal']:.2f}")
    st.write(f"IGV: {cotizacion['currency']} {cotizacion['taxes']:.2f}")
    st.write(f"Vigencia: {cotizacion['valid_until']}")
    for condition in cotizacion["conditions"]:
        st.caption(condition)


# FRONTEND STREAMLIT: muestra imagen del evento solo cuando la API devuelve un artefacto disponible.
def renderizar_tarjeta_imagen(respuesta_api: dict[str, Any]) -> None:
    """Muestra la imagen de cotizacion si el archivo esta disponible para este frontend."""

    estado = respuesta_api.get("estado", {})
    cotizacion = respuesta_api.get("cotizacion")
    opcion = estado.get("opcion_recomendada")
    if not opcion or not cotizacion:
        return

    st.subheader("Imagen del evento cotizado")
    cols = st.columns([1, 2])
    with cols[0]:
        ruta_imagen = respuesta_api.get("imagen_artefacto_cotizacion") or opcion.get("image", "")
        image_path = Path(ruta_imagen)
        if ruta_imagen and image_path.exists():
            st.image(str(image_path), use_container_width=True)
        else:
            st.info("Imagen del evento no disponible en este frontend. Si Streamlit corre en otra maquina, el backend deberia exponer la imagen por URL.")
    with cols[1]:
        st.markdown(f"**{opcion['name']}**")
        renderizar_resumen_imagen_evento(respuesta_api)
        st.caption("Imagen generada como artefacto visual de la cotizacion. No reemplaza la validacion de precio, cobertura ni disponibilidad.")


# FRONTEND STREAMLIT: muestra resumen lateral de evento, productos y servicios junto a la imagen.
def renderizar_resumen_imagen_evento(respuesta_api: dict[str, Any]) -> None:
    """Muestra el resumen comercial de la cotizacion usando datos del backend."""

    estado = respuesta_api.get("estado", {})
    cotizacion = respuesta_api.get("cotizacion") or {}
    currency = cotizacion.get("currency", "PEN")

    st.markdown("**Resumen del evento**")
    st.markdown(
        "\n".join(
            [
                f"- Evento: {estado.get('tipo_evento') or 'por confirmar'}",
                f"- Asistentes: {estado.get('asistentes') or 'por confirmar'}",
                f"- Fecha: {estado.get('fecha_evento') or 'por confirmar'}",
                f"- Distrito: {estado.get('distrito') or 'por confirmar'}",
                f"- Cotizante: {estado.get('nombre_cliente') or 'por confirmar'}",
                f"- Contacto: {estado.get('contacto') or 'por confirmar'}",
            ]
        )
    )

    st.markdown("**Productos y servicios cotizados**")
    for item in cotizacion.get("details", []):
        concept = item.get("product_name") or item.get("concept", "item")
        quantity = item.get("quantity", 1)
        unit = item.get("unit", "unidad")
        subtotal = item.get("subtotal", 0)
        st.markdown(f"- {concept}: {quantity} {unit} · {currency} {subtotal:.2f}")

    st.markdown("**Totales**")
    st.markdown(
        "\n".join(
            [
                f"- Subtotal: {currency} {cotizacion.get('subtotal', 0):.2f}",
                f"- IGV: {currency} {cotizacion.get('taxes', 0):.2f}",
                f"- Total: **{currency} {cotizacion.get('total', 0):.2f}**",
            ]
        )
    )
