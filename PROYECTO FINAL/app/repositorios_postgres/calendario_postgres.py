from __future__ import annotations

from app.repositorios_postgres.conexion import conexion_postgres


# POSTGRES/CALENDARIO: obtiene la capacidad maxima configurada por fecha y distrito.
def obtener_max_eventos_por_distrito_dia() -> int:
    """Lee MAX_EVENTOS_POR_DISTRITO_DIA desde jpomm_configuracion_calendario."""
    with conexion_postgres() as conexion:
        row = conexion.execute(
            """
            SELECT valor
            FROM jpomm_configuracion_calendario
            WHERE clave = 'MAX_EVENTOS_POR_DISTRITO_DIA'
            """
        ).fetchone()
    if not row:
        return 1
    return int(row["valor"].get("valor", 1))


# POSTGRES/CALENDARIO: lista reservas que cruzan fecha y distrito.
def buscar_reservas_cruzadas(fecha_evento: str, distrito: str) -> list[dict]:
    """Consulta reservas activas por fecha y distrito."""
    with conexion_postgres() as conexion:
        rows = conexion.execute(
            """
            SELECT id_reserva, id_sesion, quote_id, nombre_cliente, contacto, tipo_evento,
                   asistentes, fecha_evento, distrito, productos_solicitados, registrado_en, estado
            FROM jpomm_reservas_eventos
            WHERE fecha_evento = %s
              AND lower(trim(distrito)) = lower(trim(%s))
              AND estado IN ('reservado', 'confirmado')
            ORDER BY registrado_en
            """,
            (fecha_evento, distrito),
        ).fetchall()
    return [_reserva_a_dict(row) for row in rows]


# POSTGRES/CALENDARIO: inserta una reserva de evento cotizado.
def agregar_reserva_postgres(reserva: dict) -> None:
    """Guarda una reserva nueva en jpomm_reservas_eventos."""
    with conexion_postgres() as conexion:
        conexion.execute(
            """
            INSERT INTO jpomm_reservas_eventos (
                id_reserva, id_sesion, quote_id, nombre_cliente, contacto, tipo_evento,
                asistentes, fecha_evento, distrito, productos_solicitados, registrado_en, estado
            )
            VALUES (%(id_reserva)s, %(id_sesion)s, %(quote_id)s, %(nombre_cliente)s, %(contacto)s,
                    %(tipo_evento)s, %(asistentes)s, %(fecha_evento)s, %(distrito)s,
                    %(productos_solicitados)s, %(registrado_en)s, 'reservado')
            ON CONFLICT (id_reserva) DO NOTHING
            """,
            reserva,
        )


def _reserva_a_dict(row: dict) -> dict:
    """Convierte una fila PostgreSQL de reserva al contrato usado por la tool."""
    return {
        "id_reserva": row["id_reserva"],
        "id_sesion": row["id_sesion"],
        "quote_id": row["quote_id"],
        "nombre_cliente": row["nombre_cliente"],
        "contacto": row["contacto"],
        "tipo_evento": row["tipo_evento"],
        "asistentes": row["asistentes"],
        "fecha_evento": row["fecha_evento"].isoformat() if hasattr(row["fecha_evento"], "isoformat") else row["fecha_evento"],
        "distrito": row["distrito"],
        "productos_solicitados": list(row["productos_solicitados"] or []),
        "registrado_en": row["registrado_en"].isoformat() if hasattr(row["registrado_en"], "isoformat") else row["registrado_en"],
        "estado": row["estado"],
    }
