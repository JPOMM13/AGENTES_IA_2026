from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.state import QuoteState


REDIS_MOCK_PATH = Path(__file__).resolve().parent / "data" / "mock_redis_session.json"


# Ejecuta la responsabilidad de guardar sesion activa.
def guardar_sesion_activa(state: QuoteState) -> None:
    """Guarda la memoria corta activa usando session_id como clave."""
    # MOCK: PARA ESTA POC LOCAL SE GUARDA SOLO LA ULTIMA SESION ACTIVA; EN REDIS REAL HABRIA UNA KEY POR SESSION_ID CON TTL.
    record = state.a_diccionario_persistido()
    record["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    store = {state.session_id: record}
    _escribir_almacen(store)


# Ejecuta la responsabilidad de cargar sesion activa.
def cargar_sesion_activa(session_id: str) -> QuoteState | None:
    """Recupera la memoria corta activa asociada al session_id."""
    # MOCK: AQUI SE CONSULTARIA REDIS POR SESSION_ID PARA REHIDRATAR EL CONTEXTO VIVO DE LA CONVERSACION.
    record = _leer_almacen().get(session_id)
    if not record:
        return None
    return QuoteState.desde_diccionario_persistido(record)


# Ejecuta la responsabilidad de reiniciar sesion activa.
def reiniciar_sesion_activa(session_id: str) -> None:
    """Elimina la memoria corta activa de una sesion."""
    # MOCK: AQUI SE ELIMINARIA LA CLAVE SESSION_ID EN REDIS AL REINICIAR LA CONVERSACION.
    store = _leer_almacen()
    if session_id in store:
        del store[session_id]
        _escribir_almacen(store)


# Ejecuta logica interna para leer almacen.
def _leer_almacen() -> dict[str, Any]:
    """Lee el archivo local que simula Redis."""
    if not REDIS_MOCK_PATH.exists():
        return {}
    try:
        return json.loads(REDIS_MOCK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


# Ejecuta logica interna para escribir almacen.
def _escribir_almacen(store: dict[str, Any]) -> None:
    """Persiste el mock local de Redis."""
    REDIS_MOCK_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
