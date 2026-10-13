from __future__ import annotations

# TOOL DERIVACION HUMANA (HUMAN-IN-THE-LOOP, patron handoff): el agente llega hasta la cotizacion; la confirmacion y el
# pago los continua un asesor por WhatsApp. Aqui se arma el ticket y el MENSAJE QUE RECIBE EL ASESOR.
# Como llega: (1) enlace wa.me con el mensaje precargado, que el cliente envia con un clic; (2) si DERIVACION_WEBHOOK_URL
# esta configurado, el backend ademas notifica el ticket por HTTP (punto de integracion con WhatsApp Business API o CRM).

import json
import logging
import os
import urllib.request
from urllib.parse import quote as codificar_url

from app.data.datos_mock import WHATSAPP_NUMBER
from app.estado import EstadoCotizacion

logger = logging.getLogger("cotizador.derivacion")
ASESOR_POR_DEFECTO = "Asesor humano 1"


def numero_asesor() -> str:
    """Numero del asesor (WHATSAPP_ASESOR); el valor de datos_mock es solo para desarrollo."""
    return os.getenv("WHATSAPP_ASESOR", "").strip() or WHATSAPP_NUMBER


def nombre_asesor() -> str:
    return os.getenv("ASESOR_NOMBRE", "").strip() or ASESOR_POR_DEFECTO


# MENSAJE PARA EL ASESOR: texto legible (antes se enviaba el repr de un dict), con todo lo que necesita para seguir.
def armar_mensaje_asesor(estado: EstadoCotizacion, reason: str, handoff_id: str) -> str:
    cotizacion = estado.cotizacion or {}
    lineas = [
        f"Hola, soy {estado.nombre_cliente or 'un cliente'} y vengo del asistente de Tus Eventos ({handoff_id}).",
        f"Motivo: {reason.rstrip('.')}.",
        f"Evento: {estado.tipo_evento or '-'} para {estado.asistentes or '-'} personas, {estado.fecha_evento or 'fecha por definir'}, {estado.distrito or 'distrito por definir'}.",
    ]
    if estado.contacto:
        lineas.append(f"Mi contacto: {estado.contacto}.")
    if estado.opcion_recomendada:
        lineas.append(f"Opcion: {estado.opcion_recomendada.get('name')}.")
    elif estado.productos_solicitados:
        lineas.append(f"Productos: {', '.join(estado.productos_solicitados)}.")
    if cotizacion:
        detalle = cotizacion.get("details") or []
        items = "; ".join(
            f"{d.get('quantity', '')} {d.get('unit', '')} {d.get('concept') or d.get('name', '')}".strip() for d in detalle[:6]
        ) if isinstance(detalle, list) else ""
        if items:
            lineas.append(f"Detalle: {items}.")
        lineas.append(
            f"Cotizacion {cotizacion.get('quote_id')}: total {cotizacion.get('currency', 'PEN')} {cotizacion.get('total')} "
            f"(vigente hasta {str(cotizacion.get('valid_until', '')).replace('T', ' ')[:16]})."
        )
    lineas.append("Quiero continuar con la confirmacion y el pago.")
    return "\n".join(lineas)


# NOTIFICACION OPCIONAL: POST del ticket a un webhook (CRM / WhatsApp Business API). Nunca rompe el turno.
def notificar_asesor(ticket: dict) -> bool:
    url = os.getenv("DERIVACION_WEBHOOK_URL", "").strip()
    if not url:
        return False
    try:
        datos = json.dumps(ticket, ensure_ascii=False).encode("utf-8")
        peticion = urllib.request.Request(url, data=datos, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(peticion, timeout=float(os.getenv("DERIVACION_WEBHOOK_TIMEOUT", "3"))) as respuesta:
            return 200 <= respuesta.status < 300
    except Exception as error:  # noqa: BLE001 - best-effort: el enlace del cliente sigue valiendo.
        logger.warning("derivacion: no se pudo notificar al asesor (%s)", type(error).__name__)
        return False


def derivar_whatsapp(estado: EstadoCotizacion, reason: str) -> dict:
    """Prepara una derivacion por WhatsApp con el resumen del caso para el asesor."""
    handoff_id = f"DER-{(estado.id_sesion or '0001')[:4].upper()}"  # un ticket por sesion, no DER-0001 fijo
    mensaje = armar_mensaje_asesor(estado, reason, handoff_id)
    summary = {
        "intencion": estado.intencion,
        "asesor_asignado": nombre_asesor(),
        "captured_data": {
            "tipo_evento": estado.tipo_evento,
            "asistentes": estado.asistentes,
            "fecha_evento": estado.fecha_evento,
            "distrito": estado.distrito,
            "presupuesto": estado.presupuesto,
            "nombre_cliente": estado.nombre_cliente,
            "contacto": estado.contacto,
            "productos_solicitados": list(estado.productos_solicitados or []),
        },
        "opcion_recomendada": estado.opcion_recomendada["name"] if estado.opcion_recomendada else None,
        "quote_id": (estado.cotizacion or {}).get("quote_id"),
        "quote_total": (estado.cotizacion or {}).get("total"),
        "reason": reason,
        "mensaje": mensaje,
    }
    ticket = {
        "handoff_id": handoff_id,
        "channel": "whatsapp",
        "assigned_to": nombre_asesor(),
        "mock": not bool(os.getenv("DERIVACION_WEBHOOK_URL", "").strip()),
        "url": f"https://wa.me/{numero_asesor()}?text={codificar_url(mensaje)}",
        "summary": summary,
    }
    ticket["notificado"] = notificar_asesor({k: v for k, v in ticket.items() if k != "url"})
    return ticket
