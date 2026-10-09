from __future__ import annotations

import math

from app.estado import EstadoCotizacion


# TOOL MOCK/DIMENSIONAMIENTO: calcula cantidades sugeridas por producto segun asistentes y evento.
def mock_dimensionar_evento(estado: EstadoCotizacion) -> dict:
    """Calcula cantidades referenciales segun asistentes y productos elegidos."""
    # MOCK: ESTA TOOL DEBERIA USAR REGLAS COMERCIALES REALES O UN MOTOR DE DIMENSIONAMIENTO VERSIONADO EN BD PARA CALCULAR CANTIDADES.
    asistentes = estado.asistentes or 0
    productos_solicitados = estado.productos_solicitados or []
    rules = {
        "cerveza": {"concept": "cerveza", "quantity": math.ceil(asistentes * 1.2), "unit": "unidades"},
        "vino": {"concept": "vino", "quantity": math.ceil(asistentes * 0.35), "unit": "botellas"},
        "ron": {"concept": "ron", "quantity": math.ceil(asistentes * 0.2), "unit": "botellas"},
        "gaseosa": {"concept": "gaseosa", "quantity": math.ceil(asistentes * 0.5), "unit": "botellas"},
        "agua": {"concept": "agua", "quantity": math.ceil(asistentes * 1.0), "unit": "botellas"},
        "hielo": {"concept": "hielo", "quantity": math.ceil(asistentes * 0.4), "unit": "kg"},
        "bartenders": {"concept": "bartenders", "quantity": max(1, math.ceil(asistentes / 50)), "unit": "personas"},
    }
    return {
        "rule_id": "DIM-POC-001",
        "rule_version": "2026-09",
        "items": [rules[product] for product in productos_solicitados if product in rules],
    }
