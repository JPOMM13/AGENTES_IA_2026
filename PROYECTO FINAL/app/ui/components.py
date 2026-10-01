from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.artifacts import refrescar_artefacto_visual_si_es_necesario
from app.state import QuoteState


# Ejecuta la responsabilidad de renderizar panel estado.
def renderizar_panel_estado(state: QuoteState) -> None:
    """Muestra estado, dimensionamiento, derivacion y trazas en sidebar."""
    st.sidebar.subheader("Estado de la solicitud")
    st.sidebar.json(state.a_diccionario_panel())

    if state.dimensioning:
        st.sidebar.subheader("Dimensionamiento mock")
        st.sidebar.json(state.dimensioning)

    if state.handoff_summary:
        st.sidebar.subheader("Resumen para asesor")
        st.sidebar.json(state.handoff_summary["summary"])

    with st.sidebar.expander("Trazas"):
        st.json(state.logs[-12:])


# Ejecuta la responsabilidad de renderizar tarjeta imagen.
def renderizar_tarjeta_imagen(state: QuoteState) -> None:
    """Muestra la imagen generada para la cotizacion o una imagen solicitada."""
    option = state.recommended_option
    if not option or not state.quote:
        return

    st.subheader("Imagen del evento cotizado")
    cols = st.columns([1, 2])
    with cols[0]:
        refrescar_artefacto_visual_si_es_necesario(state)
        image_path = Path(state.quote_artifact_image or option.get("image", ""))
        if image_path.exists():
            st.image(str(image_path), use_container_width=True)
        else:
            st.info("Imagen del evento no disponible.")
    with cols[1]:
        st.markdown(f"**{option['name']}**")
        renderizar_resumen_imagen_evento(state)
        st.caption("Imagen generada como artefacto visual de la cotizacion. No reemplaza la validacion de precio, cobertura ni disponibilidad.")


# Ejecuta la responsabilidad de renderizar resumen imagen evento.
def renderizar_resumen_imagen_evento(state: QuoteState) -> None:
    """Muestra el resumen comercial de la cotizacion junto a la imagen."""
    quote = state.quote or {}
    currency = quote.get("currency", "PEN")

    st.markdown("**Resumen del evento**")
    st.markdown(
        "\n".join(
            [
                f"- Evento: {state.event_type or 'por confirmar'}",
                f"- Asistentes: {state.attendees or 'por confirmar'}",
                f"- Fecha: {state.event_date or 'por confirmar'}",
                f"- Distrito: {state.district or 'por confirmar'}",
                f"- Cotizante: {state.customer_name or 'por confirmar'}",
                f"- Contacto: {state.contact or 'por confirmar'}",
            ]
        )
    )

    st.markdown("**Productos y servicios cotizados**")
    for item in quote.get("details", []):
        concept = item.get("product_name") or item.get("concept", "item")
        quantity = item.get("quantity", 1)
        unit = item.get("unit", "unidad")
        subtotal = item.get("subtotal", 0)
        st.markdown(f"- {concept}: {quantity} {unit} · {currency} {subtotal:.2f}")

    st.markdown("**Totales**")
    st.markdown(
        "\n".join(
            [
                f"- Subtotal: {currency} {quote.get('subtotal', 0):.2f}",
                f"- IGV: {currency} {quote.get('taxes', 0):.2f}",
                f"- Total: **{currency} {quote.get('total', 0):.2f}**",
            ]
        )
    )


# Ejecuta la responsabilidad de renderizar tarjeta cotizacion.
def renderizar_tarjeta_cotizacion(state: QuoteState) -> None:
    """Muestra tarjeta resumida de la cotizacion generada."""
    if not state.quote:
        return
    quote = state.quote
    st.subheader("Cotizacion mock")
    st.metric("Total", f"{quote['currency']} {quote['total']:.2f}")
    st.write(f"Subtotal: {quote['currency']} {quote['subtotal']:.2f}")
    st.write(f"IGV: {quote['currency']} {quote['taxes']:.2f}")
    st.write(f"Vigencia: {quote['valid_until']}")
    for condition in quote["conditions"]:
        st.caption(condition)
