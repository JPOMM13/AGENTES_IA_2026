from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.almacen_calendario import agregar_reserva_evento, cargar_reservas_eventos
from app.data.datos_mock import MAX_EVENTOS_POR_DISTRITO_DIA
from app.estado import EstadoCotizacion
from app.fuente_datos import usar_postgres_negocio
from app.repositorios_postgres.calendario_postgres import agregar_reserva_postgres, buscar_reservas_cruzadas, obtener_max_eventos_por_distrito_dia


# TOOL CALENDARIO: valida que la fecha y distrito no crucen con eventos ya reservados.
def validar_calendario_eventos(estado: EstadoCotizacion) -> dict:
    """Consulta la agenda para evitar cruces por fecha y distrito."""
    # CALENDARIO: consulta reservas/bloqueos por fecha y distrito.
    if not estado.fecha_evento or not estado.distrito:
        return {"ok": False, "reason": "Falta fecha o distrito para validar calendario.", "reservas_cruzadas": []}

    if usar_postgres_negocio():
        reservas_cruzadas = buscar_reservas_cruzadas(estado.fecha_evento, estado.distrito)
        capacidad = obtener_max_eventos_por_distrito_dia()
    else:
        distrito_normalizado = estado.distrito.strip().lower()
        reservas = cargar_reservas_eventos()
        reservas_cruzadas = [
            reserva
            for reserva in reservas
            if reserva.get("fecha_evento") == estado.fecha_evento
            and str(reserva.get("distrito", "")).strip().lower() == distrito_normalizado
        ]
        capacidad = MAX_EVENTOS_POR_DISTRITO_DIA
    ok = len(reservas_cruzadas) < capacidad
    return {
        "ok": ok,
        "fecha_evento": estado.fecha_evento,
        "distrito": estado.distrito,
        "capacidad_dia_distrito": capacidad,
        "reservas_cruzadas": reservas_cruzadas,
        "reason": None if ok else "Ya existe una reserva para esa fecha y distrito.",
    }


# TOOL CALENDARIO: registra la cotizacion emitida como evento reservado para futuras validaciones.
def registrar_evento_cotizado(estado: EstadoCotizacion) -> dict:
    """Guarda la reserva cuando se genera una cotizacion."""
    # CALENDARIO: inserta/actualiza una reserva dentro de una transaccion.
    reserva = {
        "id_reserva": f"RES-{uuid4().hex[:8].upper()}",
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
    if usar_postgres_negocio():
        agregar_reserva_postgres(reserva)
    else:
        agregar_reserva_evento(reserva)
    return reserva
