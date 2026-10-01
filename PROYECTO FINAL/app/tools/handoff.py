from __future__ import annotations

from urllib.parse import quote

from app.data.mock_data import WHATSAPP_NUMBER
from app.state import QuoteState


# Ejecuta la responsabilidad de mock derivar whatsapp.
def mock_derivar_whatsapp(state: QuoteState, reason: str) -> dict:
    """Prepara una derivacion mock por WhatsApp con resumen del caso."""
    # MOCK: ESTA TOOL DEBERIA CREAR LA DERIVACION EN CRM/TICKETING Y ENVIAR O PREPARAR EL MENSAJE POR WHATSAPP BUSINESS API.
    summary = {
        "intent": state.intent,
        "captured_data": {
            "event_type": state.event_type,
            "attendees": state.attendees,
            "event_date": state.event_date,
            "district": state.district,
            "budget": state.budget,
        },
        "recommended_option": state.recommended_option["name"] if state.recommended_option else None,
        "quote_total": state.quote["total"] if state.quote else None,
        "reason": reason,
    }
    text = quote(f"Hola, necesito ayuda con mi cotizacion POC. Resumen: {summary}")
    return {
        "handoff_id": "H-POC-0001",
        "channel": "whatsapp",
        "url": f"https://wa.me/{WHATSAPP_NUMBER}?text={text}",
        "summary": summary,
    }
