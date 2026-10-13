"""Partes visuales de la respuesta del agente."""

from pathlib import Path

import streamlit as st


def renderizar_tarjeta_cotizacion(respuesta):
    cotizacion = respuesta.get("cotizacion")
    if not cotizacion:
        return

    estado = respuesta.get("estado") or {}
    derivacion = estado.get("resumen_derivacion") or {}
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
        if derivacion.get("url"):
            st.markdown("**Continuar venta con asesor humano**")
            st.write(
                f"Tu cotización ya está lista. Para completar la venta, puedes continuar con "
                f"{derivacion.get('assigned_to', 'Asesor humano 1')} por WhatsApp."
            )
            st.link_button("Abrir WhatsApp", derivacion["url"])


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
            st.caption("La imagen no está disponible en este servicio.")
