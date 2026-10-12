from __future__ import annotations

from urllib.parse import quote as codificar_url

from app.data.datos_mock import WHATSAPP_NUMBER
from app.estado import EstadoCotizacion


# TOOL DERIVACION HUMANA: prepara enlace WhatsApp solo cuando el usuario solicita humano.
def mock_derivar_whatsapp(estado: EstadoCotizacion, reason: str) -> dict:
    """Prepara una derivacion por WhatsApp con resumen del caso."""
    # DERIVACION: crea la derivacion en CRM/ticketing y prepara el mensaje por WhatsApp Business API.
    summary = {
        "intencion": estado.intencion,
        "captured_data": {
            "tipo_evento": estado.tipo_evento,
            "asistentes": estado.asistentes,
            "fecha_evento": estado.fecha_evento,
            "distrito": estado.distrito,
            "presupuesto": estado.presupuesto,
        },
        "opcion_recomendada": estado.opcion_recomendada["name"] if estado.opcion_recomendada else None,
        "quote_total": estado.cotizacion["total"] if estado.cotizacion else None,
        "reason": reason,
    }
    texto = codificar_url(f"Hola, necesito ayuda con mi cotizacion. Resumen: {summary}")
    return {
        "handoff_id": "DER-0001",
        "channel": "whatsapp",
        "url": f"https://wa.me/{WHATSAPP_NUMBER}?texto={texto}",
        "summary": summary,
    }
