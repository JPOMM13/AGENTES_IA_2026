from __future__ import annotations

from app.data.mock_data import COVERED_DISTRICTS
from app.state import QuoteState


# Ejecuta la responsabilidad de mock validar cobertura.
def mock_validar_cobertura(state: QuoteState) -> dict:
    """Confirma si el distrito esta dentro de la cobertura mock."""
    # MOCK: ESTA TOOL DEBERIA CONSULTAR COBERTURA OPERATIVA REAL EN UN API/SISTEMA DE ZONAS, DISTRITOS Y CAPACIDAD LOGISTICA.
    district = (state.district or "").strip().lower()
    ok = district in COVERED_DISTRICTS
    return {
        "ok": ok,
        "district": state.district,
        "reason": None if ok else f"No hay cobertura mock confirmada para {state.district}.",
    }
