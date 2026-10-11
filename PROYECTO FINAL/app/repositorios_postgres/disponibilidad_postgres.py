from __future__ import annotations

from app.repositorios_postgres.conexion import conexion_postgres


# POSTGRES/DISPONIBILIDAD: consulta cupos de paquetes por fecha.
def obtener_cupos_paquetes(fecha_evento: str) -> dict[str, int]:
    """Devuelve cupos por paquete para una fecha."""
    with conexion_postgres() as conexion:
        rows = conexion.execute(
            """
            SELECT paquete_id, cupos
            FROM jpomm_disponibilidad_paquetes
            WHERE fecha_evento = %s
            """,
            (fecha_evento,),
        ).fetchall()
    return {row["paquete_id"]: row["cupos"] for row in rows}


# POSTGRES/STOCK: consulta stock default y stock especifico por fecha.
def obtener_stock_productos(fecha_evento: str) -> dict[str, int]:
    """Combina stock base y stock especifico por fecha para productos."""
    with conexion_postgres() as conexion:
        rows = conexion.execute(
            """
            SELECT producto_id, stock
            FROM jpomm_stock_productos
            WHERE fecha_evento IS NULL OR fecha_evento = %s
            ORDER BY fecha_evento NULLS FIRST
            """,
            (fecha_evento,),
        ).fetchall()
    stock: dict[str, int] = {}
    for row in rows:
        stock[row["producto_id"]] = row["stock"]
    return stock


# POSTGRES/CATEGORIAS: consulta alternativas configuradas por categoria.
def categorias_alternativas_postgres(category: str) -> list[str]:
    """Devuelve categorias alternativas desde jpomm_categoria_alternativas."""
    with conexion_postgres() as conexion:
        rows = conexion.execute(
            """
            SELECT categoria_alternativa
            FROM jpomm_categoria_alternativas
            WHERE categoria = %s
            ORDER BY prioridad, categoria_alternativa
            """,
            (category,),
        ).fetchall()
    return [row["categoria_alternativa"] for row in rows]
