from __future__ import annotations

from datetime import datetime, timedelta

from app.state import QuoteState


# Ejecuta la responsabilidad de mock comparar opciones.
def mock_comparar_opciones(state: QuoteState) -> dict:
    """Ordena opciones disponibles con un scoring simple de afinidad."""
    # MOCK: ESTA TOOL DEBERIA USAR REGLAS REALES DE RECOMENDACION, SCORING COMERCIAL O UN SERVICIO DE OPTIMIZACION DE PAQUETES.
    ranked = []
    for option in state.valid_options:
        affinity = option.get("event_affinity", {}).get(state.event_type or "", 0.5)
        capacity_fit = _ajuste_capacidad(option, state.attendees or 0)
        availability = 1.0 if option.get("available_slots", 0) > 0 else 0.0
        budget_fit = _ajuste_presupuesto(option, state.budget)
        preference_fit = _ajuste_preferencia(option, state.preferences)
        score = (
            affinity * 0.35
            + capacity_fit * 0.25
            + availability * 0.25
            + budget_fit * 0.10
            + preference_fit * 0.05
        )
        enriched = option.copy()
        enriched["score"] = round(score, 3)
        enriched["reasons"] = [
            f"Afinidad alta con {state.event_type}.",
            f"Capacidad sugerida: {option['capacity_min']} a {option['capacity_max']} personas.",
            "Disponibilidad mock confirmada para la fecha.",
        ]
        ranked.append(enriched)

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return {"recommended": ranked[0] if ranked else None, "ranking": ranked}


# Ejecuta la responsabilidad de mock generar cotizacion.
def mock_generar_cotizacion(state: QuoteState) -> dict:
    """Genera una cotizacion mock desde el paquete o productos recomendados."""
    # MOCK: ESTA TOOL DEBERIA GENERAR LA COTIZACION EN EL SISTEMA TRANSACCIONAL REAL, PERSISTIRLA EN POSTGRESQL Y DEVOLVER ID, TOTALES E IMPUESTOS OFICIALES.
    if not state.recommended_option:
        raise ValueError("No existe opcion recomendada para cotizar.")
    if state.recommended_option.get("source") == "products":
        subtotal = round(sum(item["subtotal"] for item in state.recommended_option["items"]), 2)
        details = state.recommended_option["items"]
    else:
        subtotal = float(state.recommended_option["base_price"])
        details = [
            {
                "concept": state.recommended_option["name"],
                "quantity": 1,
                "unit": "paquete",
                "unit_price": subtotal,
                "subtotal": subtotal,
            }
        ]
    taxes = round(subtotal * 0.18, 2)
    total = round(subtotal + taxes, 2)
    valid_until = (datetime.now() + timedelta(hours=48)).replace(microsecond=0).isoformat()
    return {
        "quote_id": "Q-POC-0001",
        "currency": state.recommended_option.get("currency", "PEN"),
        "subtotal": subtotal,
        "taxes": taxes,
        "total": total,
        "details": details,
        "valid_until": valid_until,
        "conditions": [
            "Precio referencial para POC.",
            "Sujeto a disponibilidad y confirmacion final.",
            "No incluye descuentos ni condiciones negociadas.",
        ],
    }


# Ejecuta logica interna para ajuste capacidad.
def _ajuste_capacidad(option: dict, attendees: int) -> float:
    """Calcula que tan bien calza la capacidad del paquete."""
    if option["capacity_min"] <= attendees <= option["capacity_max"]:
        return 1.0
    if attendees < option["capacity_min"]:
        return max(0.3, 1 - ((option["capacity_min"] - attendees) / option["capacity_min"]))
    return 0.0


# Ejecuta logica interna para ajuste presupuesto.
def _ajuste_presupuesto(option: dict, budget: float | None) -> float:
    """Evalua si el precio base entra en el presupuesto declarado."""
    if not budget:
        return 0.75
    return 1.0 if option["base_price"] <= budget else max(0.0, 1 - ((option["base_price"] - budget) / option["base_price"]))


# Ejecuta logica interna para ajuste preferencia.
def _ajuste_preferencia(option: dict, preferences: list[str]) -> float:
    """Mide coincidencia simple entre preferencias y texto del paquete."""
    text = " ".join([option["name"], *option.get("includes", [])]).lower()
    if not preferences:
        return 0.7
    matches = sum(1 for preference in preferences if preference.lower() in text)
    return min(1.0, matches / max(1, len(preferences)))
