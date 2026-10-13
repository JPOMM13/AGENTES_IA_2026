"""Partes visuales de la respuesta del agente."""

from pathlib import Path

import streamlit as st


def renderizar_tarjeta_cotizacion(respuesta):
    cotizacion = respuesta.get("cotizacion")
    if not cotizacion:
        return

    moneda = "S/" if cotizacion.get("currency") == "PEN" else cotizacion.get("currency", "")
    with st.container(border=True):
        st.markdown(f"**Cotización · {moneda} {cotizacion['total']:,.2f}**")
        st.caption(
            f"Subtotal: {moneda} {cotizacion['subtotal']:,.2f} · "
            f"IGV: {moneda} {cotizacion['taxes']:,.2f} · "
            f"Vigencia: {cotizacion['valid_until']}"
        )
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

    with st.expander("Ver imagen del evento"):
        if ruta.startswith(("http://", "https://")) or Path(ruta).is_file():
            st.image(ruta, use_container_width=True)
        else:
            # El backend puede correr en otro contenedor: la imagen se pide por la API por nombre de archivo.
            from cliente_api import url_imagen_api

            st.image(url_imagen_api(Path(ruta).name), use_container_width=True)
