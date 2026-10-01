from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Customer:
    """Representa a la persona que cotiza y su identificador de contacto."""
    name: str | None
    contact: str | None


@dataclass(frozen=True)
class EventRequest:
    """Representa los datos principales del evento que el usuario quiere cotizar."""
    event_type: str | None
    attendees: int | None
    event_date: str | None
    district: str | None
    preferences: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RequestedProduct:
    """Representa un producto o servicio solicitado por el usuario."""
    category: str


@dataclass(frozen=True)
class QuoteItem:
    """Representa una linea de detalle de la cotizacion."""
    concept: str
    quantity: float
    unit: str
    unit_price: float
    subtotal: float


@dataclass(frozen=True)
class Quote:
    """Representa la cotizacion formal generada por el flujo."""
    quote_id: str
    currency: str
    subtotal: float
    taxes: float
    total: float
    details: list[dict[str, Any]]
    valid_until: str
    conditions: list[str]


@dataclass(frozen=True)
class SessionMemory:
    """Representa la memoria serializable de una conversacion."""
    session_id: str
    customer: Customer
    event: EventRequest
    requested_products: list[RequestedProduct]
    stage: str
    quote: Quote | None = None


# Ejecuta la responsabilidad de cliente desde estado.
def cliente_desde_estado(state: Any) -> Customer:
    """Construye el modelo Customer desde QuoteState sin modificar el estado."""
    return Customer(name=state.customer_name, contact=state.contact)


# Ejecuta la responsabilidad de solicitud evento desde estado.
def solicitud_evento_desde_estado(state: Any) -> EventRequest:
    """Construye el modelo EventRequest desde QuoteState."""
    return EventRequest(
        event_type=state.event_type,
        attendees=state.attendees,
        event_date=state.event_date,
        district=state.district,
        preferences=list(state.preferences),
    )


# Ejecuta la responsabilidad de cotizacion desde estado.
def cotizacion_desde_estado(state: Any) -> Quote | None:
    """Construye el modelo Quote desde QuoteState si ya existe cotizacion."""
    if not state.quote:
        return None
    return Quote(
        quote_id=state.quote["quote_id"],
        currency=state.quote["currency"],
        subtotal=state.quote["subtotal"],
        taxes=state.quote["taxes"],
        total=state.quote["total"],
        details=state.quote["details"],
        valid_until=state.quote["valid_until"],
        conditions=state.quote["conditions"],
    )


# Ejecuta la responsabilidad de memoria sesion desde estado.
def memoria_sesion_desde_estado(state: Any) -> SessionMemory:
    """Construye una vista de dominio de la memoria conversacional."""
    return SessionMemory(
        session_id=state.session_id,
        customer=cliente_desde_estado(state),
        event=solicitud_evento_desde_estado(state),
        requested_products=[RequestedProduct(category=product) for product in state.requested_products],
        stage=state.stage,
        quote=cotizacion_desde_estado(state),
    )
