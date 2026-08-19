"""Estado que representa el modelo interno de la conversación."""

from typing import Annotated, Optional

from langchain.agents import AgentState


def _ultimo_valor(anterior, nuevo):
    """Reducer: conserva la actualización más reciente de cada campo."""
    return nuevo


class EstadoRecomendacion(AgentState):
    """Model-Based Reflex: recuerda hechos y resultados entre mensajes."""

    session_id: Annotated[str, _ultimo_valor]
    occasion: Annotated[Optional[str], _ultimo_valor]
    attendees: Annotated[Optional[int], _ultimo_valor]
    event_date: Annotated[Optional[str], _ultimo_valor]
    location: Annotated[Optional[str], _ultimo_valor]
    preferences: Annotated[list[str], _ultimo_valor]
    missing_fields: Annotated[list[str], _ultimo_valor]
    coverage_status: Annotated[Optional[str], _ultimo_valor]
    valid_options: Annotated[list[dict], _ultimo_valor]
    rejected_options: Annotated[list[dict], _ultimo_valor]
    recommended_option: Annotated[Optional[dict], _ultimo_valor]
    conversation_state: Annotated[str, _ultimo_valor]
    current_goal: Annotated[str, _ultimo_valor]
    requires_human: Annotated[bool, _ultimo_valor]
    escalation_reason: Annotated[Optional[str], _ultimo_valor]


def crear_estado_inicial(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "occasion": None,
        "attendees": None,
        "event_date": None,
        "location": None,
        "preferences": [],
        "missing_fields": [],
        "coverage_status": None,
        "valid_options": [],
        "rejected_options": [],
        "recommended_option": None,
        "conversation_state": "START",
        "current_goal": "IDENTIFY_INTENT",
        "requires_human": False,
        "escalation_reason": None,
        "messages": [],
    }

