from __future__ import annotations

from app.data.datos_mock import CATALOG, PRODUCTS
from app.estado import EstadoCotizacion
from app.fuente_datos import usar_postgres_negocio
from app.repositorios_postgres.catalogo_postgres import buscar_catalogo_postgres


# TOOL CATALOGO: consulta paquetes, productos y servicios disponibles para cotizar.
def buscar_catalogo(estado: EstadoCotizacion) -> dict:
    """Filtra paquetes y productos segun evento, capacidad y pedido."""
    # CATALOGO: consulta el catalogo comercial de productos, servicios y paquetes.
    if usar_postgres_negocio():
        return buscar_catalogo_postgres(estado)

    package_options = []
    similar_packages = []
    if _cliente_solicito_paquete_o_servicio(estado):
        for product in CATALOG:
            if estado.tipo_evento and estado.tipo_evento not in product["event_types"]:
                continue
            option = product.copy()
            if estado.asistentes and estado.asistentes > product["capacity_max"]:
                option["fit_status"] = "similar_capacity_low"
                option["discard_reason"] = "El paquete se parece por ocasion, pero queda corto para la cantidad solicitada."
                similar_packages.append(option)
                continue
            option["fit_status"] = "package_match"
            package_options.append(option)

    product_options = [
        product.copy()
        for product in PRODUCTS
        if not estado.tipo_evento or estado.tipo_evento in product["event_types"]
        if not estado.productos_solicitados or product["category"] in estado.productos_solicitados
    ]
    return {
        "options": package_options,
        "similar_packages": similar_packages,
        "products": product_options,
        "all_products": [
            product.copy()
            for product in PRODUCTS
            if not estado.tipo_evento or estado.tipo_evento in product["event_types"]
        ],
    }


# VALIDACION DE CATALOGO: detecta si el usuario pidio paquete/servicio o productos especificos.
def _cliente_solicito_paquete_o_servicio(estado: EstadoCotizacion) -> bool:
    """Detecta si el usuario pidio un servicio/paquete y no solo productos."""
    return any(product in {"bar movil", "bartenders"} for product in estado.productos_solicitados)
