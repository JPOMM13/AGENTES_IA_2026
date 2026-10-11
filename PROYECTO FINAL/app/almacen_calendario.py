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


# MOCK/CALENDARIO: registra una nueva reserva como una fila independiente de calendario.
def agregar_reserva_evento(reserva: dict[str, Any]) -> None:
    """Inserta una nueva reserva sin reemplazar otras cotizaciones de la misma sesion."""
    reservas = cargar_reservas_eventos()
    reservas.append(reserva)
    guardar_reservas_eventos(reservas)
