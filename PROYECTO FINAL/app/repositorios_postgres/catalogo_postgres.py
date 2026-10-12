from __future__ import annotations

from app.estado import EstadoCotizacion
from app.repositorios_postgres.conexion import conexion_postgres


# POSTGRES/CATALOGO: consulta paquetes y productos desde tablas jpomm_* sin cambiar la firma de la tool.
def buscar_catalogo_postgres(estado: EstadoCotizacion) -> dict:
    """Lee la estructura de catalogo usando PostgreSQL como fuente."""
    paquetes = _listar_paquetes()
    productos = _listar_productos()
    package_options = []
    similar_packages = []

    if _cliente_solicito_paquete_o_servicio(estado):
        for paquete in paquetes:
            if estado.tipo_evento and estado.tipo_evento not in paquete["event_types"]:
                continue
            option = paquete.copy()
            if estado.asistentes and estado.asistentes > paquete["capacity_max"]:
                option["fit_status"] = "similar_capacity_low"
                option["discard_reason"] = "El paquete se parece por ocasion, pero queda corto para la cantidad solicitada."
                similar_packages.append(option)
                continue
            option["fit_status"] = "package_match"
            package_options.append(option)

    product_options = [
        product.copy()
        for product in productos
        if not estado.tipo_evento or estado.tipo_evento in product["event_types"]
        if not estado.productos_solicitados or product["category"] in estado.productos_solicitados
    ]
    return {
        "options": package_options,
        "similar_packages": similar_packages,
        "products": product_options,
        "all_products": [
            product.copy()
            for product in productos
            if not estado.tipo_evento or estado.tipo_evento in product["event_types"]
        ],
    }


def _listar_paquetes() -> list[dict]:
    """Lee paquetes comerciales activos desde PostgreSQL."""
    with conexion_postgres() as conexion:
        rows = conexion.execute(
            """
            SELECT id, nombre, servicio, tipos_evento, capacidad_min, capacidad_max,
                   precio_base, moneda, imagen, afinidad_evento, incluye
            FROM jpomm_paquetes
            WHERE activo = true
            ORDER BY id
            """
        ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["nombre"],
            "service": row["servicio"],
            "event_types": list(row["tipos_evento"] or []),
            "capacity_min": row["capacidad_min"],
            "capacity_max": row["capacidad_max"],
            "base_price": float(row["precio_base"]),
            "currency": row["moneda"],
            "image": row["imagen"],
            "event_affinity": dict(row["afinidad_evento"] or {}),
            "includes": list(row["incluye"] or []),
        }
        for row in rows
    ]


def _listar_productos() -> list[dict]:
    """Lee productos activos desde PostgreSQL."""
    with conexion_postgres() as conexion:
        rows = conexion.execute(
            """
            SELECT id, nombre, categoria, familia, unidad, precio_unitario, moneda, tipos_evento
            FROM jpomm_productos
            WHERE activo = true
            ORDER BY id
            """
        ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["nombre"],
            "category": row["categoria"],
            "family": row["familia"],
            "unit": row["unidad"],
            "unit_price": float(row["precio_unitario"]),
            "currency": row["moneda"],
            "event_types": list(row["tipos_evento"] or []),
        }
        for row in rows
    ]


def _cliente_solicito_paquete_o_servicio(estado: EstadoCotizacion) -> bool:
    """Detecta si el usuario pidio un servicio/paquete y no solo productos."""
    return any(product in {"bar movil", "bartenders"} for product in estado.productos_solicitados)
