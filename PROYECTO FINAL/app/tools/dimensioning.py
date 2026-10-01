from __future__ import annotations

import math

from app.state import QuoteState


# Ejecuta la responsabilidad de mock dimensionar evento.
def mock_dimensionar_evento(state: QuoteState) -> dict:
    """Calcula cantidades referenciales segun asistentes y productos elegidos."""
    # MOCK: ESTA TOOL DEBERIA USAR REGLAS COMERCIALES REALES O UN MOTOR DE DIMENSIONAMIENTO VERSIONADO EN BD PARA CALCULAR CANTIDADES.
    attendees = state.attendees or 0
    requested_products = state.requested_products or []
    rules = {
        "cerveza": {"concept": "cerveza", "quantity": math.ceil(attendees * 1.2), "unit": "unidades"},
        "vino": {"concept": "vino", "quantity": math.ceil(attendees * 0.35), "unit": "botellas"},
        "ron": {"concept": "ron", "quantity": math.ceil(attendees * 0.2), "unit": "botellas"},
        "gaseosa": {"concept": "gaseosa", "quantity": math.ceil(attendees * 0.5), "unit": "botellas"},
        "agua": {"concept": "agua", "quantity": math.ceil(attendees * 1.0), "unit": "botellas"},
        "hielo": {"concept": "hielo", "quantity": math.ceil(attendees * 0.4), "unit": "kg"},
        "bartenders": {"concept": "bartenders", "quantity": max(1, math.ceil(attendees / 50)), "unit": "personas"},
    }
    return {
        "rule_id": "DIM-POC-001",
        "rule_version": "2026-09",
        "items": [rules[product] for product in requested_products if product in rules],
    }
