from __future__ import annotations

from app.data.mock_data import COVERED_DISTRICTS
from app.estado import EstadoCotizacion


# Ejecuta la responsabilidad de mock validar cobertura.
def mock_validar_cobertura(estado: EstadoCotizacion) -> dict:
    """Confirma si el distrito esta dentro de la cobertura mock."""
    # MOCK: ESTA TOOL DEBERIA CONSULTAR COBERTURA OPERATIVA REAL EN UN API/SISTEMA DE ZONAS, DISTRITOS Y CAPACIDAD LOGISTICA.
    distrito = (estado.distrito or "").strip().lower()
    ok = distrito in COVERED_DISTRICTS
    return {
        "ok": ok,
        "distrito": estado.distrito,
        "reason": None if ok else f"No hay cobertura mock confirmada para {estado.distrito}.",
    }
