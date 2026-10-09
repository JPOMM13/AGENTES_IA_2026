from __future__ import annotations

from app.data.datos_mock import CATALOG, PRODUCTS
from app.estado import EstadoCotizacion


# TOOL MOCK/CATALOGO: consulta paquetes, productos y servicios simulados disponibles para cotizar.
def mock_buscar_catalogo(estado: EstadoCotizacion) -> dict:
    """Filtra paquetes y productos mock segun evento, capacidad y pedido."""
    # MOCK: ESTA TOOL DEBERIA CONSULTAR EL CATALOGO COMERCIAL REAL EN POSTGRESQL O EN EL API/SISTEMA DE CATALOGO DE PRODUCTOS Y SERVICIOS.
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
