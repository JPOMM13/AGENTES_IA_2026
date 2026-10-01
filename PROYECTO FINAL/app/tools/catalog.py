from __future__ import annotations

from app.data.mock_data import CATALOG, PRODUCTS
from app.state import QuoteState


# Ejecuta la responsabilidad de mock buscar catalogo.
def mock_buscar_catalogo(state: QuoteState) -> dict:
    """Filtra paquetes y productos mock segun evento, capacidad y pedido."""
    # MOCK: ESTA TOOL DEBERIA CONSULTAR EL CATALOGO COMERCIAL REAL EN POSTGRESQL O EN EL API/SISTEMA DE CATALOGO DE PRODUCTOS Y SERVICIOS.
    package_options = []
    similar_packages = []
    if _cliente_solicito_paquete_o_servicio(state):
        for product in CATALOG:
            if state.event_type and state.event_type not in product["event_types"]:
                continue
            option = product.copy()
            if state.attendees and state.attendees > product["capacity_max"]:
                option["fit_status"] = "similar_capacity_low"
                option["discard_reason"] = "El paquete se parece por ocasion, pero queda corto para la cantidad solicitada."
                similar_packages.append(option)
                continue
            option["fit_status"] = "package_match"
            package_options.append(option)

    product_options = [
        product.copy()
        for product in PRODUCTS
        if not state.event_type or state.event_type in product["event_types"]
        if not state.requested_products or product["category"] in state.requested_products
    ]
    return {
        "options": package_options,
        "similar_packages": similar_packages,
        "products": product_options,
        "all_products": [
            product.copy()
            for product in PRODUCTS
            if not state.event_type or state.event_type in product["event_types"]
        ],
    }


# Ejecuta logica interna para cliente solicito paquete o servicio.
def _cliente_solicito_paquete_o_servicio(state: QuoteState) -> bool:
    """Detecta si el usuario pidio un servicio/paquete y no solo productos."""
    return any(product in {"bar movil", "bartenders"} for product in state.requested_products)
