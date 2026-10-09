from __future__ import annotations

from datetime import datetime, timedelta

from app.estado import EstadoCotizacion


# Ejecuta la responsabilidad de mock comparar opciones.
def mock_comparar_opciones(estado: EstadoCotizacion) -> dict:
    """Ordena opciones disponibles con un scoring simple de afinidad."""
    # MOCK: ESTA TOOL DEBERIA USAR REGLAS REALES DE RECOMENDACION, SCORING COMERCIAL O UN SERVICIO DE OPTIMIZACION DE PAQUETES.
    ranked = []
    for option in estado.opciones_validas:
        affinity = option.get("event_affinity", {}).get(estado.tipo_evento or "", 0.5)
        capacity_fit = _ajuste_capacidad(option, estado.asistentes or 0)
        availability = 1.0 if option.get("available_slots", 0) > 0 else 0.0
        budget_fit = _ajuste_presupuesto(option, estado.presupuesto)
        preference_fit = _ajuste_preferencia(option, estado.preferencias)
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
            f"Afinidad alta con {estado.tipo_evento}.",
            f"Capacidad sugerida: {option['capacity_min']} a {option['capacity_max']} personas.",
            "Disponibilidad mock confirmada para la fecha.",
        ]
        ranked.append(enriched)

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return {"recommended": ranked[0] if ranked else None, "ranking": ranked}


# Ejecuta la responsabilidad de mock generar cotizacion.
def mock_generar_cotizacion(estado: EstadoCotizacion) -> dict:
    """Genera una cotizacion mock desde el paquete o productos recomendados."""
    # MOCK: ESTA TOOL DEBERIA GENERAR LA COTIZACION EN EL SISTEMA TRANSACCIONAL REAL, PERSISTIRLA EN POSTGRESQL Y DEVOLVER ID, TOTALES E IMPUESTOS OFICIALES.
    if not estado.opcion_recomendada:
        raise ValueError("No existe opcion recomendada para cotizar.")
    if estado.opcion_recomendada.get("origen") == "products":
        subtotal = round(sum(item["subtotal"] for item in estado.opcion_recomendada["items"]), 2)
        details = estado.opcion_recomendada["items"]
    else:
        subtotal = float(estado.opcion_recomendada["base_price"])
        details = [
            {
                "concept": estado.opcion_recomendada["name"],
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
        "currency": estado.opcion_recomendada.get("currency", "PEN"),
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
def _ajuste_capacidad(option: dict, asistentes: int) -> float:
    """Calcula que tan bien calza la capacidad del paquete."""
    if option["capacity_min"] <= asistentes <= option["capacity_max"]:
        return 1.0
    if asistentes < option["capacity_min"]:
        return max(0.3, 1 - ((option["capacity_min"] - asistentes) / option["capacity_min"]))
    return 0.0


# Ejecuta logica interna para ajuste presupuesto.
def _ajuste_presupuesto(option: dict, presupuesto: float | None) -> float:
    """Evalua si el precio base entra en el presupuesto declarado."""
    if not presupuesto:
        return 0.75
    return 1.0 if option["base_price"] <= presupuesto else max(0.0, 1 - ((option["base_price"] - presupuesto) / option["base_price"]))


# Ejecuta logica interna para ajuste preferencia.
def _ajuste_preferencia(option: dict, preferencias: list[str]) -> float:
    """Mide coincidencia simple entre preferencias y texto del paquete."""
    texto = " ".join([option["name"], *option.get("includes", [])]).lower()
    if not preferencias:
        return 0.7
    matches = sum(1 for preference in preferencias if preference.lower() in texto)
    return min(1.0, matches / max(1, len(preferencias)))
