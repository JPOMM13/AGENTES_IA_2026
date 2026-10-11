from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.almacen_calendario import agregar_reserva_evento, cargar_reservas_eventos
from app.data.datos_mock import MAX_EVENTOS_POR_DISTRITO_DIA
from app.estado import EstadoCotizacion


# TOOL MOCK/CALENDARIO: valida que la fecha y distrito no crucen con eventos ya reservados.
def mock_validar_calendario_eventos(estado: EstadoCotizacion) -> dict:
    """Consulta la agenda mock para evitar cruces por fecha y distrito."""
    # MOCK: AQUI SE CONSULTARIA UNA TABLA TRANSACCIONAL DE RESERVAS/CALENDARIO EN POSTGRESQL CON BLOQUEOS REALES.
    if not estado.fecha_evento or not estado.distrito:
        return {"ok": False, "reason": "Falta fecha o distrito para validar calendario.", "reservas_cruzadas": []}

    distrito_normalizado = estado.distrito.strip().lower()
    reservas = cargar_reservas_eventos()
    reservas_cruzadas = [
        reserva
        for reserva in reservas
        if reserva.get("fecha_evento") == estado.fecha_evento
        and str(reserva.get("distrito", "")).strip().lower() == distrito_normalizado
    ]
    ok = len(reservas_cruzadas) < MAX_EVENTOS_POR_DISTRITO_DIA
    return {
        "ok": ok,
        "fecha_evento": estado.fecha_evento,
        "distrito": estado.distrito,
        "capacidad_dia_distrito": MAX_EVENTOS_POR_DISTRITO_DIA,
        "reservas_cruzadas": reservas_cruzadas,
        "reason": None if ok else "Ya existe una reserva mock para esa fecha y distrito.",
    }


# TOOL MOCK/CALENDARIO: registra la cotizacion emitida como evento reservado para futuras validaciones.
def mock_registrar_evento_cotizado(estado: EstadoCotizacion) -> dict:
    """Guarda la reserva mock cuando se genera una cotizacion."""
    # MOCK: EN PRODUCCION ESTO DEBERIA INSERTAR/ACTUALIZAR UNA RESERVA EN POSTGRESQL DENTRO DE UNA TRANSACCION.
    reserva = {
        "id_reserva": f"R-POC-{uuid4().hex[:8].upper()}",
        "id_sesion": estado.id_sesion,
        "quote_id": (estado.cotizacion or {}).get("quote_id"),
        "nombre_cliente": estado.nombre_cliente,
        "contacto": estado.contacto,
        "tipo_evento": estado.tipo_evento,
        "asistentes": estado.asistentes,
        "fecha_evento": estado.fecha_evento,
        "distrito": estado.distrito,
        "productos_solicitados": list(estado.productos_solicitados),
        "registrado_en": datetime.now().replace(microsecond=0).isoformat(),
    }
    agregar_reserva_evento(reserva)
    return reserva
