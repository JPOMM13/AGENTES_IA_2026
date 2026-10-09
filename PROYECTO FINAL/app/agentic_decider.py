from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from app.contracts import ToolReadinessContract
from app.llm_config import obtener_configuracion_llm
from app.state import QuoteState


AgentDecision = Literal[
    "pedir_campos_faltantes",
    "answer_price",
    "validate_and_recommend",
    "generate_quote",
    "show_image",
    "handoff",
    "answer_policy",
    "close",
]


# Ejecuta la responsabilidad de debe usar create agent.
def debe_usar_create_agent() -> bool:
    """Indica si la capa agentica con create_agent esta habilitada."""
    return obtener_configuracion_llm().enabled


# Ejecuta la responsabilidad de decidir siguiente accion con agente.
def decidir_siguiente_accion_con_agente(user_message: str, state: QuoteState) -> AgentDecision | None:
    """Optional LangChain create_agent ReAct layer.

    The agent decides the next high-level action. The workflow still executes
    deterministic tools and guardrails after this decision.
    """
    if not debe_usar_create_agent():
        return None
    try:
        readiness = obtener_disponibilidad_tools(user_message, state)
        agent = obtener_agente_decisor()
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "user_message": user_message,
                                "state": state.a_diccionario_panel(),
                                "missing_fields": state.missing_fields,
                                "tool_readiness": readiness,
                                "explicit_handoff_requested": es_solicitud_derivacion_explicita(user_message),
                            },
                            ensure_ascii=False,
                        ),
                    }
                ]
            }
        )
        return extraer_decision_de_mensajes(result["messages"])
    except Exception:
        return None


# Ejecuta la responsabilidad de obtener agente decisor.
@lru_cache(maxsize=1)
def obtener_agente_decisor():
    """Devuelve el agente decisor cacheado para no recrearlo por mensaje."""
    return crear_agente_decisor()


# Ejecuta la responsabilidad de crear agente decisor.
def crear_agente_decisor():
    """Crea el agente decisor con create_agent usando el LLM configurado."""
    from langchain.agents import create_agent
    from langchain.tools import tool

    # Ejecuta la responsabilidad de elegir accion workflow.
    @tool
    def elegir_accion_workflow(
        user_message: str,
        has_missing_fields: bool,
        has_recommendation: bool,
        has_quote: bool,
        can_answer_price: bool,
        can_validate_and_recommend: bool,
        can_generate_quote: bool,
        can_show_image: bool,
        explicit_handoff_requested: bool = False,
    ) -> str:
        """Elige accion respetando prerequisitos minimos antes de usar tools."""
        text = user_message.lower()
        if any(term in text for term in ["imagen", "foto", "visual"]):
            return "show_image" if can_show_image else "pedir_campos_faltantes"
        if explicit_handoff_requested:
            return "handoff"
        if any(term in text for term in ["politica", "feriado", "anticipacion", "anticipación"]):
            return "answer_policy"
        if any(term in text for term in ["cerrar", "finalizar", "terminar"]):
            return "close"
        if any(term in text for term in ["genera la cotizacion", "genera la cotización", "cotizalo", "cotízalo"]):
            return "generate_quote" if can_generate_quote else "pedir_campos_faltantes"
        if any(term in text for term in ["cuanto cuesta", "cuánto cuesta", "precio", "costo"]):
            return "answer_price" if can_answer_price else "pedir_campos_faltantes"
        if has_missing_fields:
            return "pedir_campos_faltantes"
        if not has_recommendation and can_validate_and_recommend:
            return "validate_and_recommend"
        if has_quote:
            return "close"
        return "validate_and_recommend" if can_validate_and_recommend else "pedir_campos_faltantes"

    system_prompt = """
Eres el modulo decisor de un workflow agentico de cotizaciones de eventos.
Tu tarea NO es cotizar, NO es inventar datos y NO es responder comercialmente.
Solo debes elegir una accion de alto nivel.

CONTEXTO:
- Recibiras user_message, state, missing_fields, tool_readiness y
  explicit_handoff_requested.
- state es memoria operativa de la cotizacion en curso.
- tool_readiness indica si ya existen prerequisitos para usar herramientas de
  negocio.

REGLAS IMPORTANTES:
- Usa la tool elegir_accion_workflow.
- Devuelve exactamente una de estas acciones: pedir_campos_faltantes,
  answer_price, validate_and_recommend, generate_quote, show_image, handoff,
  answer_policy, close.
- validate_and_recommend solo si can_validate_and_recommend=true.
- generate_quote solo si can_generate_quote=true.
- answer_price solo si can_answer_price=true.
- show_image solo si can_show_image=true.
- handoff solo si explicit_handoff_requested=true.
- Si faltan datos minimos, elige pedir_campos_faltantes.
- Si el usuario solo revisa o modifica datos, no elijas generate_quote.
- No asumas productos, fechas, cantidades ni intenciones no dichas.

FORMATO DE SALIDA:
- Llama exactamente una vez la tool elegir_accion_workflow.
- No agregues explicaciones ni texto final para el usuario.
- El workflow deterministico ejecutara las validaciones reales despues.
"""
    config = obtener_configuracion_llm()
    agente = create_agent(
        model=config.modelo_langchain,
        tools=[elegir_accion_workflow],
        system_prompt=system_prompt,
    )
    return agente


# Ejecuta la responsabilidad de normalizar decision.
def normalizar_decision(content: str) -> AgentDecision | None:
    """Extrae una accion valida desde texto o salida de tool."""
    allowed: set[str] = {
        "pedir_campos_faltantes",
        "answer_price",
        "validate_and_recommend",
        "generate_quote",
        "show_image",
        "handoff",
        "answer_policy",
        "close",
    }
    text = content.strip().lower()
    for action in allowed:
        if action in text:
            return action  # type: ignore[return-value]
    return None


# Ejecuta la responsabilidad de extraer decision de mensajes.
def extraer_decision_de_mensajes(messages: list) -> AgentDecision | None:
    """Obtiene la decision final priorizando salidas estructuradas."""
    # Prefer tool outputs over final LLM prose. The final prose may hallucinate
    # business facts; the tool output is the constrained action contract.
    for message in reversed(messages):
        content = getattr(message, "content", "")
        decision = normalizar_decision(str(content))
        if decision:
            return decision
    return None


# Ejecuta la responsabilidad de obtener disponibilidad tools.
def obtener_disponibilidad_tools(user_message: str, state: QuoteState) -> dict[str, bool]:
    """Calcula prerequisitos para que el agente sepa que tools puede usar."""
    text = user_message.lower()
    has_product_or_package_reference = any(
        term in text
        for term in [
            "cerveza",
            "vino",
            "gaseosa",
            "hielo",
            "bartender",
            "bar movil",
            "bar móvil",
            "paquete",
        ]
    )
    has_minimum_for_recommendation = not state.missing_fields
    has_recommendation = state.recommended_option is not None
    has_quote = state.quote is not None
    return ToolReadinessContract(
        can_answer_price=has_product_or_package_reference or has_recommendation,
        can_validate_and_recommend=has_minimum_for_recommendation,
        can_generate_quote=has_minimum_for_recommendation and has_recommendation,
        can_show_image=has_quote,
    ).a_diccionario()


# Ejecuta la responsabilidad de es solicitud derivacion explicita.
def es_solicitud_derivacion_explicita(message: str) -> bool:
    """Detecta si el usuario pidio de forma explicita derivacion humana."""
    text = message.lower()
    return any(
        term in text
        for term in [
            "asesor",
            "humano",
            "whatsapp",
            "derivame",
            "derívame",
            "pasame con alguien",
            "pásame con alguien",
            "hablar con alguien",
            "atencion humana",
            "atención humana",
        ]
    )
