from __future__ import annotations

from app.data.datos_mock import COVERED_DISTRICTS
from app.estado import EstadoCotizacion
from app.fuente_datos import usar_postgres_negocio
from app.repositorios_postgres.cobertura_postgres import validar_cobertura_postgres


# TOOL COBERTURA: valida si el distrito esta dentro de la cobertura operativa.
def mock_validar_cobertura(estado: EstadoCotizacion) -> dict:
    """Confirma si el distrito esta dentro de la cobertura."""
    # COBERTURA: consulta cobertura operativa por zonas, distritos y capacidad logistica.
    if usar_postgres_negocio():
        return validar_cobertura_postgres(estado)

    distrito = (estado.distrito or "").strip().lower()
    ok = distrito in COVERED_DISTRICTS
    return {
        "ok": ok,
        "distrito": estado.distrito,
        "distritos_cubiertos": sorted(COVERED_DISTRICTS),
        "reason": None if ok else f"{estado.distrito} no esta dentro del alcance de cobertura.",
    }
