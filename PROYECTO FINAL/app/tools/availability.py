from __future__ import annotations

from datetime import date, datetime, timedelta

from app.data.mock_data import AVAILABILITY, DEFAULT_PRODUCT_STOCK, PRODUCT_CATEGORIES
from app.state import QuoteState


# Ejecuta la responsabilidad de mock validar disponibilidad.
def mock_validar_disponibilidad(state: QuoteState, options: list[dict]) -> dict:
    """Valida disponibilidad mock de paquetes para la fecha solicitada."""
    # MOCK: ESTA TOOL DEBERIA CONSULTAR DISPONIBILIDAD REAL EN EL SISTEMA DE RESERVAS/CALENDARIO O EN UNA TABLA TRANSACCIONAL DE CUPOS POR FECHA.
    available_options = []
    discarded_options = []

    if not state.event_date:
        return {"available_options": [], "discarded_options": options}

    event_date = datetime.fromisoformat(state.event_date).date()
    if event_date < date.today() + timedelta(hours=72):
        return {
            "available_options": [],
            "discarded_options": [{"option": option, "reason": "No cumple anticipacion minima de 72 horas."} for option in options],
        }

    day_availability = AVAILABILITY.get(state.event_date, {})
    for option in options:
        cupos = day_availability.get(option["id"], 1)
        if cupos > 0:
            enriched = option.copy()
            enriched["available_slots"] = cupos
            available_options.append(enriched)
        else:
            discarded_options.append({"option": option, "reason": "Sin disponibilidad para la fecha solicitada."})

    return {"available_options": available_options, "discarded_options": discarded_options}


# Ejecuta la responsabilidad de mock validar stock productos.
def mock_validar_stock_productos(state: QuoteState, requested_items: list[dict], products: list[dict]) -> dict:
    """Valida stock mock por producto y calcula faltantes con alternativas."""
    # MOCK: ESTA TOOL DEBERIA CONSULTAR STOCK REAL EN INVENTARIO, ERP O TABLAS TRANSACCIONALES DE DISPONIBILIDAD POR PRODUCTO Y FECHA.
    if not state.event_date:
        return {"available_items": [], "missing_items": requested_items}

    day_availability = {**DEFAULT_PRODUCT_STOCK, **AVAILABILITY.get(state.event_date, {})}
    product_by_category = {product["category"]: product for product in products}
    available_items = []
    missing_items = []

    for item in requested_items:
        product = product_by_category.get(item["concept"])
        if not product:
            missing_items.append({**item, "reason": "No existe producto mock para este concepto."})
            continue
        stock = day_availability.get(product["id"], 0)
        if stock >= item["quantity"]:
            available_items.append({**item, "product": product, "stock": stock})
        else:
            missing_items.append(
                {
                    **item,
                    "product": product,
                    "stock": stock,
                    "reason": "Stock insuficiente.",
                    "alternatives": buscar_alternativas_producto_disponibles(item, products, day_availability),
                }
            )

    return {"available_items": available_items, "missing_items": missing_items}


# Ejecuta la responsabilidad de buscar alternativas producto disponibles.
def buscar_alternativas_producto_disponibles(item: dict, products: list[dict], day_availability: dict) -> list[dict]:
    """Busca alternativas de la misma familia con stock disponible."""
    alternatives = []
    product_by_category = {product["category"]: product for product in products}
    for category in categorias_alternativas_para(item["concept"]):
        product = product_by_category.get(category)
        if not product:
            continue
        stock = day_availability.get(product["id"], 0)
        if stock <= 0:
            continue
        alternatives.append(
            {
                "category": category,
                "product": product,
                "stock": stock,
                "suggested_quantity": min(item["quantity"], stock),
            }
        )
    return alternatives


# Ejecuta la responsabilidad de categorias alternativas para.
def categorias_alternativas_para(category: str) -> list[str]:
    """Devuelve categorias alternativas configuradas para un producto."""
    for config in PRODUCT_CATEGORIES.values():
        if category in config.get("alternatives", {}):
            return config["alternatives"][category]
        if category in config.get("categories", []):
            return [candidate for candidate in config["categories"] if candidate != category]
    return []
