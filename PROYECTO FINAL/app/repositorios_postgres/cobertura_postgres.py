from __future__ import annotations

from app.estado import EstadoCotizacion
from app.repositorios_postgres.conexion import conexion_postgres


# POSTGRES/COBERTURA: valida distrito contra la tabla operacional de cobertura.
def validar_cobertura_postgres(estado: EstadoCotizacion) -> dict:
    """Valida cobertura usando jpomm_cobertura_distritos."""
    distrito = (estado.distrito or "").strip().lower()
    with conexion_postgres() as conexion:
        distritos = [
            row["distrito"]
            for row in conexion.execute(
                """
                SELECT distrito
                FROM jpomm_cobertura_distritos
                WHERE activo = true
                ORDER BY distrito
                """
            ).fetchall()
        ]
    ok = distrito in set(distritos)
    return {
        "ok": ok,
        "distrito": estado.distrito,
        "distritos_cubiertos": sorted(distritos),
        "reason": None if ok else f"{estado.distrito} no esta dentro del alcance de cobertura mock.",
    }
