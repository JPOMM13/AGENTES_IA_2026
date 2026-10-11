from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# MOCK: ESTE JSON SIMULA UNA TABLA TRANSACCIONAL DE RESERVAS DE EVENTOS; EN REALIDAD DEBERIA SER POSTGRESQL.
CALENDARIO_MOCK_PATH = Path("app/data/mock_calendario_eventos.json")


# MOCK/CALENDARIO: carga reservas de eventos ya confirmadas para validar cruces de fecha y distrito.
def cargar_reservas_eventos() -> list[dict[str, Any]]:
    """Lee reservas mock del calendario transaccional local."""
    if not CALENDARIO_MOCK_PATH.exists():
        return []
    try:
        data = json.loads(CALENDARIO_MOCK_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


# MOCK/CALENDARIO: persiste reservas confirmadas como si fuera una tabla de agenda.
def guardar_reservas_eventos(reservas: list[dict[str, Any]]) -> None:
    """Guarda reservas mock del calendario transaccional local."""
    CALENDARIO_MOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    CALENDARIO_MOCK_PATH.write_text(json.dumps(reservas, ensure_ascii=False, indent=2), encoding="utf-8")


# MOCK/CALENDARIO: registra o actualiza la reserva asociada a una sesion/cotizacion.
def upsert_reserva_evento(reserva: dict[str, Any]) -> None:
    """Inserta o actualiza una reserva usando id_sesion como identificador."""
    reservas = cargar_reservas_eventos()
    reservas = [item for item in reservas if item.get("id_sesion") != reserva.get("id_sesion")]
    reservas.append(reserva)
    guardar_reservas_eventos(reservas)
