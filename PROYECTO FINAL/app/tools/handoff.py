from __future__ import annotations

from urllib.parse import quote as codificar_url

from app.data.mock_data import WHATSAPP_NUMBER
from app.estado import EstadoCotizacion


# Ejecuta la responsabilidad de mock derivar whatsapp.
def mock_derivar_whatsapp(estado: EstadoCotizacion, reason: str) -> dict:
    """Prepara una derivacion mock por WhatsApp con resumen del caso."""
    # MOCK: ESTA TOOL DEBERIA CREAR LA DERIVACION EN CRM/TICKETING Y ENVIAR O PREPARAR EL MENSAJE POR WHATSAPP BUSINESS API.
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
    texto = codificar_url(f"Hola, necesito ayuda con mi cotizacion POC. Resumen: {summary}")
    return {
        "handoff_id": "H-POC-0001",
        "channel": "whatsapp",
        "url": f"https://wa.me/{WHATSAPP_NUMBER}?texto={texto}",
        "summary": summary,
    }
