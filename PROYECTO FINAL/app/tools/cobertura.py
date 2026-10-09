from __future__ import annotations

from app.data.datos_mock import COVERED_DISTRICTS
from app.estado import EstadoCotizacion


# TOOL MOCK/COBERTURA: valida si el distrito esta dentro de la cobertura operativa simulada.
def mock_validar_cobertura(estado: EstadoCotizacion) -> dict:
    """Confirma si el distrito esta dentro de la cobertura mock."""
    # MOCK: ESTA TOOL DEBERIA CONSULTAR COBERTURA OPERATIVA REAL EN UN API/SISTEMA DE ZONAS, DISTRITOS Y CAPACIDAD LOGISTICA.
    distrito = (estado.distrito or "").strip().lower()
    ok = distrito in COVERED_DISTRICTS
    return {
        "ok": ok,
        "distrito": estado.distrito,
        "distritos_cubiertos": sorted(COVERED_DISTRICTS),
        "reason": None if ok else f"{estado.distrito} no esta dentro del alcance de cobertura mock.",
    }
