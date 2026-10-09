from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.artifacts import refrescar_artefacto_visual_si_es_necesario
from app.estado import EstadoCotizacion


# Ejecuta la responsabilidad de renderizar panel estado.
def renderizar_panel_estado(estado: EstadoCotizacion) -> None:
    """Muestra estado, dimensionamiento, derivacion y trazas en sidebar."""
    st.sidebar.subheader("Estado de la solicitud")
    st.sidebar.json(estado.a_diccionario_panel())

    if estado.dimensionamiento:
        st.sidebar.subheader("Dimensionamiento mock")
        st.sidebar.json(estado.dimensionamiento)

    if estado.resumen_derivacion:
        st.sidebar.subheader("Resumen para asesor")
        st.sidebar.json(estado.resumen_derivacion["summary"])

    with st.sidebar.expander("Trazas"):
        st.json(estado.trazas[-12:])


# Ejecuta la responsabilidad de renderizar tarjeta imagen.
def renderizar_tarjeta_imagen(estado: EstadoCotizacion) -> None:
    """Muestra la imagen generada para la cotizacion o una imagen solicitada."""
    option = estado.opcion_recomendada
    if not option or not estado.cotizacion:
        return

    st.subheader("Imagen del evento cotizado")
    cols = st.columns([1, 2])
    with cols[0]:
        refrescar_artefacto_visual_si_es_necesario(estado)
        image_path = Path(estado.imagen_artefacto_cotizacion or option.get("image", ""))
        if image_path.exists():
            st.image(str(image_path), use_container_width=True)
        else:
            st.info("Imagen del evento no disponible.")
    with cols[1]:
        st.markdown(f"**{option['name']}**")
        renderizar_resumen_imagen_evento(estado)
        st.caption("Imagen generada como artefacto visual de la cotizacion. No reemplaza la validacion de precio, cobertura ni disponibilidad.")


# Ejecuta la responsabilidad de renderizar resumen imagen evento.
def renderizar_resumen_imagen_evento(estado: EstadoCotizacion) -> None:
    """Muestra el resumen comercial de la cotizacion junto a la imagen."""
    cotizacion = estado.cotizacion or {}
    currency = cotizacion.get("currency", "PEN")

    st.markdown("**Resumen del evento**")
    st.markdown(
        "\n".join(
            [
                f"- Evento: {estado.tipo_evento or 'por confirmar'}",
                f"- Asistentes: {estado.asistentes or 'por confirmar'}",
                f"- Fecha: {estado.fecha_evento or 'por confirmar'}",
                f"- Distrito: {estado.distrito or 'por confirmar'}",
                f"- Cotizante: {estado.nombre_cliente or 'por confirmar'}",
                f"- Contacto: {estado.contacto or 'por confirmar'}",
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


# Ejecuta la responsabilidad de renderizar tarjeta cotizacion.
def renderizar_tarjeta_cotizacion(estado: EstadoCotizacion) -> None:
    """Muestra tarjeta resumida de la cotizacion generada."""
    if not estado.cotizacion:
        return
    cotizacion = estado.cotizacion
    st.subheader("Cotizacion mock")
    st.metric("Total", f"{cotizacion['currency']} {cotizacion['total']:.2f}")
    st.write(f"Subtotal: {cotizacion['currency']} {cotizacion['subtotal']:.2f}")
    st.write(f"IGV: {cotizacion['currency']} {cotizacion['taxes']:.2f}")
    st.write(f"Vigencia: {cotizacion['valid_until']}")
    for condition in cotizacion["conditions"]:
        st.caption(condition)
