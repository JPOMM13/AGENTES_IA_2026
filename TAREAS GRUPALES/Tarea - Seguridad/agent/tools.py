"""Reglas comerciales puras: todos los importes proceden del repositorio."""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from langsmith import traceable

DISCLAIMER = "Cotización referencial mock; precio vigente por 24 horas y disponibilidad sujeta a reconfirmación. No constituye reserva ni compra."


# Convierte un importe a texto con dos decimales usando Decimal y redondeo comercial HALF_UP.
def money(value):
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# Calcula entrega y recojo; si el evento es feriado mock, busca los días hábiles anterior y posterior.
def schedule(repo, event_date):
    event = datetime.fromisoformat(event_date)
    if event.tzinfo is None:
        raise ValueError("La fecha requiere zona horaria.")
    day = event.date()
    holidays = set(repo.get_config()["holidays"])
    delivery, pickup = day, day + timedelta(days=1)
    if day.isoformat() in holidays:
        delivery = day - timedelta(days=1)
        while delivery.weekday() >= 5 or delivery.isoformat() in holidays:
            delivery -= timedelta(days=1)
        while pickup.weekday() >= 5 or pickup.isoformat() in holidays:
            pickup += timedelta(days=1)
    return delivery.isoformat(), pickup.isoformat()

# Devuelve productos activos con afinidad al evento y capacidad suficiente, respetando las categorías solicitadas.
# Los decoradores @traceable identifican estas funciones como herramientas en las trazas de LangSmith.
@traceable(name="search_catalog", run_type="tool")
def search_catalog(repo, state):
    return [p for p in repo.get_products() if p["active"]
            and repo.get_affinity(p["id"], state["event_type"]) > 0
            and p["capacity"] >= state["attendees"]
            and (not state.get("product_categories") or p["category"] in state["product_categories"])]

# Conserva únicamente los productos con cobertura explícita en la ubicación solicitada.
@traceable(name="check_coverage", run_type="tool")
def check_coverage(repo, options, location):
    return [p for p in options if repo.get_coverage(p["id"], location)]

# Exige al menos una unidad disponible cada día desde la entrega hasta el recojo, incluidos ambos extremos.
@traceable(name="check_availability", run_type="tool")
def check_availability(repo, options, event_date, delivery_date, pickup_date):
    # Se requiere stock explícito en TODO el intervalo de ocupación, ambos extremos incluidos.
    start, end = datetime.fromisoformat(delivery_date).date(), datetime.fromisoformat(pickup_date).date()
    days = [(start + timedelta(days=i)).isoformat() for i in range((end-start).days+1)]
    return [p for p in options if all(repo.get_availability(p["id"], d) >= 1 for d in days)]

# Excluye opciones que exceden el presupuesto con impuestos y ordena las restantes con preferencias autorizadas.
@traceable(name="rank_options", run_type="tool")
def rank_options(repo, options, state):
    prefs = repo.get_preferences(state.get("trusted_customer_id"))
    rate = Decimal(repo.get_config()["tax_rate"])
    budget = state.get("budget")
    affordable = [p for p in options if budget is None or Decimal(repo.get_price(p["id"])) * (1 + rate) <= Decimal(str(budget))]
    # Construye la prioridad: mayor afinidad y preferencia; menor exceso de capacidad, precio e ID como desempate.
    def key(p):
        return (-repo.get_affinity(p["id"], state["event_type"]),
                -(p["category"] in prefs), p["capacity"] - state["attendees"],
                Decimal(repo.get_price(p["id"])), p["id"])
    return sorted(affordable, key=key), prefs

# Calcula el precio de un pack, impuesto y total desde el repositorio; añade vigencia de 24 horas y condiciones.
@traceable(name="get_quote", run_type="tool")
def get_quote(repo, product, state, now):
    subtotal = Decimal(repo.get_price(product["id"]))
    tax = Decimal(money(subtotal * Decimal(repo.get_config()["tax_rate"])))
    return {"product_id": product["id"], "quantity": 1, "currency": repo.get_config()["currency"],
            "unit_price": money(subtotal), "subtotal": money(subtotal), "tax": money(tax),
            "total": money(subtotal + tax), "valid_until": (now + timedelta(hours=24)).isoformat(),
            "delivery_date": state["delivery_date"], "pickup_date": state["pickup_date"],
            "conditions": DISCLAIMER}

# Devuelve datos del evento, validaciones y motivo en un resumen estructurado para atención manual.
@traceable(name="human_handoff", run_type="tool")
def human_handoff(state):
    return {"reason": state["handoff_reason"], "data": {k: state.get(k) for k in
            ("event_type", "attendees", "event_date", "location", "budget")},
            "validations": {"coverage": state["validated_coverage"], "availability": state["validated_availability"]},
            "status": "pending_manual_contact"}
