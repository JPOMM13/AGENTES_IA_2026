from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.state import QuoteState


STORE_PATH = Path(__file__).resolve().parent / "data" / "mock_session_memory.json"


# Ejecuta la responsabilidad de guardar estado conversacion.
def guardar_estado_conversacion(state: QuoteState) -> None:
    """Guarda el estado si ya existe una identidad minima del cotizante."""
    # MOCK: ESTA MEMORIA ENTRE SESIONES DEBERIA GUARDARSE EN POSTGRESQL/NOSQL USANDO CONTACT COMO IDENTIFICADOR PRINCIPAL.
    if not state.contact:
        return
    if not _tiene_datos_para_memoria_persistente(state):
        return

    store = _leer_almacen()
    record = state.a_diccionario_persistido()
    record["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    store[_clave_contacto(state.contact)] = record
    _escribir_almacen(store)


# Ejecuta la responsabilidad de buscar conversacion previa.
def buscar_conversacion_previa(customer_name: str | None, contact: str | None) -> QuoteState | None:
    """Busca una conversacion anterior usando contacto como identidad principal."""
    # MOCK: ESTA CONSULTA DEBERIA IR A POSTGRESQL O NOSQL BUSCANDO POR TELEFONO/CORREO, NO POR NOMBRE.
    if not contact:
        return None
    record = _leer_almacen().get(_clave_contacto(contact))
    if not record:
        return None
    return QuoteState.desde_diccionario_persistido(record)


# Ejecuta la responsabilidad de hidratar estado.
def hidratar_estado(target: QuoteState, source: QuoteState) -> QuoteState:
    """Carga una conversacion previa dentro de la nueva sesion actual."""
    current_session_id = target.session_id
    restored = source.a_diccionario_persistido()
    restored["session_id"] = current_session_id
    restored["messages"] = target.messages
    restored["logs"] = target.logs + source.logs[-20:]
    return QuoteState.desde_diccionario_persistido(restored)


# Ejecuta logica interna para clave contacto.
def _clave_contacto(contact: str) -> str:
    """Normaliza telefono o correo para identificar al cliente."""
    return re.sub(r"\D+", "", contact.lower()) or contact.strip().lower()


# Ejecuta logica interna para tiene datos para memoria persistente.
def _tiene_datos_para_memoria_persistente(state: QuoteState) -> bool:
    """Evita guardar busquedas vacias como si fueran cotizaciones previas."""
    return any(
        [
            state.event_type,
            state.attendees,
            state.event_date,
            state.district,
            state.requested_products,
            state.recommended_option,
            state.quote,
        ]
    )


# Ejecuta logica interna para leer almacen.
def _leer_almacen() -> dict[str, Any]:
    """Lee el archivo local de memoria mock y devuelve un diccionario seguro."""
    if not STORE_PATH.exists():
        return {}
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


# Ejecuta logica interna para escribir almacen.
def _escribir_almacen(store: dict[str, Any]) -> None:
    """Persiste el diccionario de memoria mock en disco."""
    STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
