"""Partes visuales de la respuesta del agente."""

from pathlib import Path

import streamlit as st


def renderizar_tarjeta_cotizacion(respuesta):
    cotizacion = respuesta.get("cotizacion")
    if not cotizacion:
        return

    moneda = "S/" if cotizacion.get("currency") == "PEN" else cotizacion.get("currency", "")
    with st.container(border=True):
        st.subheader("Cotización")
        st.metric("Total", f"{moneda} {cotizacion['total']:,.2f}")
        st.write(f"Subtotal: {moneda} {cotizacion['subtotal']:,.2f}")
        st.write(f"IGV: {moneda} {cotizacion['taxes']:,.2f}")
        st.caption(f"Vigencia: {cotizacion['valid_until']}")
        with st.expander("Ver detalle"):
            for item in cotizacion.get("details", []):
                nombre = item.get("product_name") or item.get("concept", "Producto")
                st.write(f"{nombre}: {item.get('quantity', 1)} {item.get('unit', 'unidad')} · {moneda} {item.get('subtotal', 0):,.2f}")
            for condicion in cotizacion.get("conditions", []):
                st.caption(condicion)


def renderizar_tarjeta_imagen(respuesta):
    estado = respuesta.get("estado") or {}
    opcion = estado.get("opcion_recomendada") or {}
    ruta = respuesta.get("imagen_artefacto_cotizacion") or opcion.get("image")
    if not respuesta.get("cotizacion") or not ruta:
        return

    with st.container(border=True):
        st.subheader("Imagen del evento")
        if ruta.startswith(("http://", "https://")) or Path(ruta).is_file():
            st.image(ruta, use_container_width=True)
        else:
            st.caption("La imagen no está disponible en este servicio.")
