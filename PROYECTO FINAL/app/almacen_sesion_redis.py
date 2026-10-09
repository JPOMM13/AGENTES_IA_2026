from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.estado import EstadoCotizacion


REDIS_MOCK_PATH = Path(__file__).resolve().parent / "data" / "mock_redis_session.json"


# MEMORIA CORTA MOCK REDIS: guarda el estado vivo de la sesion actual en JSON local.
def guardar_sesion_activa(estado: EstadoCotizacion) -> None:
    """Guarda la memoria corta activa usando id_sesion como clave."""
    # MOCK: PARA ESTA POC LOCAL SE GUARDA SOLO LA ULTIMA SESION ACTIVA; EN REDIS REAL HABRIA UNA KEY POR SESSION_ID CON TTL.
    record = estado.a_diccionario_persistido()
    record["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    store = {estado.id_sesion: record}
    _escribir_almacen(store)


# MEMORIA CORTA MOCK REDIS: recupera el estado vivo de la sesion por id_sesion.
def cargar_sesion_activa(id_sesion: str) -> EstadoCotizacion | None:
    """Recupera la memoria corta activa asociada al id_sesion."""
    # MOCK: AQUI SE CONSULTARIA REDIS POR SESSION_ID PARA REHIDRATAR EL CONTEXTO VIVO DE LA CONVERSACION.
    record = _leer_almacen().get(id_sesion)
    if not record:
        return None
    return EstadoCotizacion.desde_diccionario_persistido(record)


# MEMORIA CORTA MOCK REDIS: elimina la sesion activa cuando se reinicia la conversacion.
def reiniciar_sesion_activa(id_sesion: str) -> None:
    """Elimina la memoria corta activa de una sesion."""
    # MOCK: AQUI SE ELIMINARIA LA CLAVE SESSION_ID EN REDIS AL REINICIAR LA CONVERSACION.
    store = _leer_almacen()
    if id_sesion in store:
        del store[id_sesion]
        _escribir_almacen(store)


# MEMORIA CORTA MOCK REDIS: lee el JSON local que simula Redis.
def _leer_almacen() -> dict[str, Any]:
    """Lee el archivo local que simula Redis."""
    if not REDIS_MOCK_PATH.exists():
        return {}
    try:
        return json.loads(REDIS_MOCK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


# MEMORIA CORTA MOCK REDIS: escribe el JSON local que simula Redis.
def _escribir_almacen(store: dict[str, Any]) -> None:
    """Persiste el mock local de Redis."""
    REDIS_MOCK_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
