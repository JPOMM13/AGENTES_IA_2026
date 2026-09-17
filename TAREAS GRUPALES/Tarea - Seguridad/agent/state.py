from typing import Literal, TypedDict
from pydantic import BaseModel, Field, ConfigDict

# Esquema de lo que puede extraer el LLM; no admite campos de precio ni permisos de consentimiento.
class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["information", "recommendation", "quotation", "modify_request", "human_support"] = "quotation"
    event_type: str | None = Field(default=None, max_length=120)
    attendees: int | None = Field(default=None, gt=0, le=100000, strict=True)
    event_date: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=200)
    budget: float | None = Field(default=None, ge=0, le=100000000, allow_inf_nan=False)
    product_categories: list[str] | None = Field(default=None, max_length=20)
    clear_fields: list[Literal["event_type", "attendees", "event_date", "location", "budget", "product_categories"]] = Field(default_factory=list)
    risk: Literal["none", "discount", "exception", "payment", "purchase", "complaint", "privacy", "ambiguity"] = "none"

# Estado de una sesión: datos del evento, validaciones, resultados y mensajes intercambiados.
class AgentState(TypedDict, total=False):
    turn_count: int
    message: str
    messages: list[dict]
    intent: str
    event_type: str | None
    attendees: int | None
    event_date: str | None
    location: str | None
    budget: float | None
    product_categories: list[str]
    customer_email: str | None
    customer_phone: str | None
    missing_fields: list[str]
    validated_coverage: bool
    validated_availability: bool
    recommended_option: dict | None
    quote: dict | None
    current_stage: str
    needs_human: bool
    handoff_reason: str | None
    handoff: dict | None
    extracted: dict
    options: list[dict]
    tools_called: list[str]
    attempts: dict[str, int]
    response: str
    delivery_date: str
    pickup_date: str
    preferences_used: list[str]
    trusted_customer_id: str | None
