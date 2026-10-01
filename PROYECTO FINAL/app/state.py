from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any
from uuid import uuid4


@dataclass
class QuoteState:
    """Estado completo de una cotizacion conversacional durante la sesion."""
    session_id: str = field(default_factory=lambda: str(uuid4()))
    stage: str = "inicio"
    intent: str | None = None

    event_type: str | None = None
    attendees: int | None = None
    event_date: str | None = None
    partial_date: dict[str, int | None] = field(default_factory=lambda: {"day": None, "month": None, "year": None})
    district: str | None = None
    budget: float | None = None
    requested_products: list[str] = field(default_factory=list)
    unsupported_requested_products: list[str] = field(default_factory=list)
    stock_shortage_products: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    customer_name: str | None = None
    contact: str | None = None

    missing_fields: list[str] = field(default_factory=list)
    catalog_options: list[dict[str, Any]] = field(default_factory=list)
    valid_options: list[dict[str, Any]] = field(default_factory=list)
    discarded_options: list[dict[str, Any]] = field(default_factory=list)
    recommended_option: dict[str, Any] | None = None
    dimensioning: dict[str, Any] | None = None
    quote: dict[str, Any] | None = None

    coverage_ok: bool | None = None
    availability_ok: bool | None = None
    policy_ok: bool | None = None

    handoff_offered: bool = False
    handoff_confirmed: bool = False
    handoff_summary: dict[str, Any] | None = None
    image_requested: bool = False
    quote_artifact_image: str | None = None
    product_change_cleared_unsupported: bool = False
    pending_previous_state: dict[str, Any] | None = None

    messages: list[dict[str, str]] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)

    # Ejecuta la responsabilidad de registrar log.
    def registrar_log(self, event: str, payload: dict[str, Any] | None = None) -> None:
        """Registra una traza interna del flujo para debugging y evals."""
        self.logs.append({"event": event, "payload": payload or {}})

    # Ejecuta la responsabilidad de a diccionario panel.
    def a_diccionario_panel(self) -> dict[str, Any]:
        """Devuelve una vista compacta del estado para mostrar en el panel lateral."""
        return {
            "stage": self.stage,
            "intent": self.intent,
            "event_type": self.event_type,
            "attendees": self.attendees,
            "event_date": self.event_date,
            "partial_date": self.partial_date,
            "district": self.district,
            "budget": self.budget,
            "requested_products": self.requested_products,
            "unsupported_requested_products": self.unsupported_requested_products,
            "stock_shortage_products": self.stock_shortage_products,
            "customer_name": self.customer_name,
            "contact": self.contact,
            "preferences": self.preferences,
            "missing_fields": self.missing_fields,
            "coverage_ok": self.coverage_ok,
            "availability_ok": self.availability_ok,
            "recommended": self.recommended_option["name"] if self.recommended_option else None,
            "quote_total": self.quote["total"] if self.quote else None,
            "handoff_offered": self.handoff_offered,
            "handoff_confirmed": self.handoff_confirmed,
            "image_requested": self.image_requested,
            "quote_artifact_image": self.quote_artifact_image,
        }

    # Ejecuta la responsabilidad de a diccionario persistido.
    def a_diccionario_persistido(self) -> dict[str, Any]:
        """Serializa el estado para guardarlo en la memoria mock entre sesiones."""
        data = asdict(self)
        data["messages"] = data["messages"][-20:]
        data["logs"] = data["logs"][-50:]
        return data

    # Ejecuta la responsabilidad de desde diccionario persistido.
    @classmethod
    def desde_diccionario_persistido(cls, data: dict[str, Any]) -> "QuoteState":
        """Reconstruye un QuoteState desde datos guardados previamente."""
        allowed = {field.name for field in fields(cls)}
        filtered = {key: value for key, value in data.items() if key in allowed}
        return cls(**filtered)
