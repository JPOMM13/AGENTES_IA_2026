"""Tools autorizadas y reglas determinísticas del agente."""

from typing import Annotated, Optional

from langchain.tools import InjectedState, InjectedToolCallId, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from recomendaciones import CATALOGO, COBERTURA, calcular_utilidad


REQUIRED_FIELDS = ("occasion", "attendees", "event_date", "location")


@tool
def actualizar_modelo_interno(
    occasion: Optional[str] = None,
    attendees: Optional[int] = None,
    event_date: Optional[str] = None,
    location: Optional[str] = None,
    preferences: Optional[list[str]] = None,
    *,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Registra solo los datos expresados por el usuario y conserva los anteriores."""
    estado = state
    update = {
        "occasion": occasion if occasion is not None else estado.get("occasion"),
        "attendees": attendees if attendees is not None else estado.get("attendees"),
        "event_date": event_date if event_date is not None else estado.get("event_date"),
        "location": location if location is not None else estado.get("location"),
        "preferences": list(dict.fromkeys((estado.get("preferences") or []) + (preferences or []))),
        "conversation_state": "COLLECTING_DATA",
    }
    faltantes = [campo for campo in REQUIRED_FIELDS if update.get(campo) is None]
    update["missing_fields"] = faltantes
    update["messages"] = [ToolMessage(
        f"Modelo interno actualizado. Campos faltantes: {faltantes or 'ninguno'}.",
        tool_call_id=tool_call_id,
    )]
    return Command(update=update)


@tool
def aplicar_reglas_reflejo(
    user_requests_human: bool = False,
    discount_requested: bool = False,
    *,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Simple Reflex: aplica reglas exactas antes de buscar alternativas."""
    estado = state
    faltantes = [campo for campo in REQUIRED_FIELDS if estado.get(campo) is None]
    requiere_humano = user_requests_human or discount_requested
    razon = None
    if user_requests_human:
        razon = "solicitud de atención humana"
    elif discount_requested:
        razon = "solicitud de descuento o negociación"

    if requiere_humano:
        accion, objetivo, etapa = "ESCALATE", "ESCALATE", "ESCALATING"
    elif faltantes:
        accion, objetivo, etapa = "ASK_MISSING_DATA", "COLLECT_REQUIRED_DATA", "COLLECTING_DATA"
    else:
        accion, objetivo, etapa = "VALIDATE_COVERAGE", "VALIDATE_CONDITIONS", "VALIDATING_CONDITIONS"

    return Command(update={
        "missing_fields": faltantes,
        "requires_human": requiere_humano,
        "escalation_reason": razon,
        "current_goal": objetivo,
        "conversation_state": etapa,
        "messages": [ToolMessage(f"Regla aplicada. Acción obligatoria: {accion}.", tool_call_id=tool_call_id)],
    })


@tool
def validar_cobertura(
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Comprueba cobertura usando la fuente operativa simulada."""
    location = state.get("location")
    covered = bool(location and location.lower() in COBERTURA)
    return Command(update={
        "coverage_status": "covered" if covered else "not_covered",
        "current_goal": "RETRIEVE_OPTIONS" if covered else "FINISH",
        "conversation_state": "RETRIEVING_OPTIONS" if covered else "COMPLETED",
        "messages": [ToolMessage(
            f"Cobertura en {location}: {'confirmada' if covered else 'no disponible'}.",
            tool_call_id=tool_call_id,
        )],
    })


@tool
def evaluar_alternativas(
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Filtra opciones inválidas, calcula utilidad y elige la mejor opción válida."""
    asistentes = state.get("attendees") or 0
    ocasion = state.get("occasion") or ""
    preferencias = state.get("preferences") or []
    validas, rechazadas = [], []

    for original in CATALOGO:
        opcion = dict(original)
        capacidad_valida = opcion["min_personas"] <= asistentes <= opcion["max_personas"]
        if not opcion["disponible"] or not capacidad_valida:
            rechazadas.append({**opcion, "motivo_rechazo": "disponibilidad o capacidad"})
            continue
        opcion.update(calcular_utilidad(opcion, ocasion, preferencias))
        validas.append(opcion)

    validas.sort(key=lambda item: item["utility_score"], reverse=True)
    recomendada = validas[0] if validas else None
    return Command(update={
        "valid_options": validas,
        "rejected_options": rechazadas,
        "recommended_option": recomendada,
        "requires_human": not bool(validas),
        "escalation_reason": None if validas else "no existen opciones válidas",
        "current_goal": "PRESENT_RECOMMENDATION" if validas else "ESCALATE",
        "conversation_state": "PRESENTING_RECOMMENDATION" if validas else "ESCALATING",
        "messages": [ToolMessage(
            f"Evaluación terminada: {len(validas)} válidas y {len(rechazadas)} rechazadas. "
            f"Mejor opción: {recomendada['nombre'] if recomendada else 'ninguna'}.",
            tool_call_id=tool_call_id,
        )],
    })


TOOLS = [actualizar_modelo_interno, aplicar_reglas_reflejo, validar_cobertura, evaluar_alternativas]
