from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from app.contracts import ContratoDisponibilidadHerramientas
from app.guardrails.decision import es_derivacion_humana_explicita, es_solicitud_nueva_cotizacion, es_solicitud_recuperar_memoria
from app.guardrails.middleware import invocar_agente_con_guardrails, obtener_middleware_langchain_guardrails
from app.llm_config import obtener_configuracion_llm
from app.estado import EstadoCotizacion


DecisionAgente = Literal[
    "pedir_campos_faltantes",
    "responder_precio",
    "validar_y_recomendar",
    "generar_cotizacion",
    "mostrar_imagen",
    "derivacion",
    "responder_politica",
    "cierre",
    "retomar_previa",
    "nueva_cotizacion",
]


# Ejecuta la responsabilidad de debe usar create agente.
def debe_usar_create_agent() -> bool:
    """Indica si la capa agentica con create_agent esta habilitada."""
    return obtener_configuracion_llm().habilitado


# Ejecuta la responsabilidad de decidir siguiente accion con agente.
def decidir_siguiente_accion_con_agente(mensaje_usuario: str, estado: EstadoCotizacion) -> DecisionAgente | None:
    """Optional LangChain create_agent ReAct layer.

    The agente decides the next high-level accion. The workflow still executes
    deterministic tools and guardrails after this decision.
    """
    if not debe_usar_create_agent():
        return None
    try:
        disponibilidad = obtener_disponibilidad_tools(mensaje_usuario, estado)
        agente = obtener_agente_decisor()
        carga_agente = (
            {
                "messages": [
                    {
                        "role": "user",
        "content": json.dumps(
                            {
                                "mensaje_usuario": mensaje_usuario,
                                "estado": estado.a_diccionario_panel(),
                                "campos_faltantes": estado.campos_faltantes,
                                "disponibilidad_herramientas": disponibilidad,
                                "explicit_handoff_requested": es_solicitud_derivacion_explicita(mensaje_usuario),
                                "explicit_resume_requested": es_solicitud_recuperar_memoria(mensaje_usuario.lower()),
                                "explicit_new_quote_requested": es_solicitud_nueva_cotizacion(mensaje_usuario.lower()),
                            },
                            ensure_ascii=False,
                        ),
                    }
                ]
            }
        )
        resultado = invocar_agente_con_guardrails(agente, carga_agente, mensaje_usuario, estado, "agente_decisor")
        if not resultado:
            return None
        return extraer_decision_de_mensajes(resultado["messages"])
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
        mensaje_usuario: str,
        tiene_campos_faltantes: bool,
        tiene_recomendacion: bool,
        tiene_cotizacion: bool,
        puede_responder_precio: bool,
        puede_validar_y_recomendar: bool,
        puede_generar_cotizacion: bool,
        puede_mostrar_imagen: bool,
        explicit_handoff_requested: bool = False,
        explicit_resume_requested: bool = False,
        explicit_new_quote_requested: bool = False,
    ) -> str:
        """Elige accion respetando prerequisitos minimos antes de usar tools."""
        texto = mensaje_usuario.lower()
        if explicit_new_quote_requested:
            return "nueva_cotizacion"
        if explicit_resume_requested:
            return "retomar_previa"
        if any(term in texto for term in ["imagen", "foto", "visual"]):
            return "mostrar_imagen" if puede_mostrar_imagen else "pedir_campos_faltantes"
        if explicit_handoff_requested:
            return "derivacion"
        if any(term in texto for term in ["politica", "feriado", "anticipacion", "anticipación"]):
            return "responder_politica"
        if any(term in texto for term in ["cerrar", "finalizar", "terminar"]):
            return "cierre"
        if any(term in texto for term in ["genera la cotizacion", "genera la cotización", "cotizalo", "cotízalo"]):
            return "generar_cotizacion" if puede_generar_cotizacion else "pedir_campos_faltantes"
        if any(term in texto for term in ["cuanto cuesta", "cuánto cuesta", "precio", "costo"]):
            return "responder_precio" if puede_responder_precio else "pedir_campos_faltantes"
        if tiene_campos_faltantes:
            return "pedir_campos_faltantes"
        if not tiene_recomendacion and puede_validar_y_recomendar:
            return "validar_y_recomendar"
        if tiene_cotizacion:
            return "cierre"
        return "validar_y_recomendar" if puede_validar_y_recomendar else "pedir_campos_faltantes"

    system_prompt = """
Eres el modulo decisor de un workflow agentico de cotizaciones de eventos.
Tu tarea NO es cotizar, NO es inventar datos y NO es responder comercialmente.
Solo debes elegir una accion de alto nivel.

CONTEXTO:
- Recibiras mensaje_usuario, estado, campos_faltantes, disponibilidad_herramientas,
  explicit_handoff_requested, explicit_resume_requested y
  explicit_new_quote_requested.
- estado es memoria operativa de la cotizacion en curso.
- disponibilidad_herramientas indica si ya existen prerequisitos para usar herramientas de
  negocio.

REGLAS IMPORTANTES:
- Usa la tool elegir_accion_workflow.
- Devuelve exactamente una de estas acciones: pedir_campos_faltantes,
  responder_precio, validar_y_recomendar, generar_cotizacion, mostrar_imagen, derivacion,
  responder_politica, cierre, retomar_previa, nueva_cotizacion.
- Si el usuario indica que quiere otra/nueva cotizacion, otro numero, otro
  contacto u otra persona, elige nueva_cotizacion.
- Si el usuario indica que ya tuvo una sesion/conversacion anterior, que ya
  conversaron, que ya dio/dejo todos sus datos, que ya dio datos antes aunque
  escriba con errores como "enteriormente", o que quiere continuar lo anterior,
  elige retomar_previa aunque no entregue telefono todavia.
- validar_y_recomendar solo si puede_validar_y_recomendar=true.
- generar_cotizacion solo si puede_generar_cotizacion=true.
- responder_precio solo si puede_responder_precio=true.
- mostrar_imagen solo si puede_mostrar_imagen=true.
- handoff solo si explicit_handoff_requested=true.
- Si faltan datos minimos, elige pedir_campos_faltantes.
- Si el usuario solo revisa o modifica datos, no elijas generar_cotizacion.
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
        middleware=obtener_middleware_langchain_guardrails(),
    )
    return agente


# Ejecuta la responsabilidad de normalizar decision.
def normalizar_decision(content: str) -> DecisionAgente | None:
    """Extrae una accion valida desde texto o salida de tool."""
    allowed: set[str] = {
        "pedir_campos_faltantes",
        "responder_precio",
        "validar_y_recomendar",
        "generar_cotizacion",
        "mostrar_imagen",
        "derivacion",
        "responder_politica",
        "cierre",
        "retomar_previa",
        "nueva_cotizacion",
    }
    texto = content.strip().lower()
    for accion in allowed:
        if accion in texto:
            return accion  # type: ignore[return-value]
    return None


# Ejecuta la responsabilidad de extraer decision de mensajes.
def extraer_decision_de_mensajes(mensajes: list) -> DecisionAgente | None:
    """Obtiene la decision final priorizando salidas estructuradas."""
    # Prefer tool outputs over final LLM prose. The final prose may hallucinate
    # business facts; the tool output is the constrained accion contract.
    for message in reversed(mensajes):
        content = getattr(message, "content", "")
        decision = normalizar_decision(str(content))
        if decision:
            return decision
    return None


# Ejecuta la responsabilidad de obtener disponibilidad tools.
def obtener_disponibilidad_tools(mensaje_usuario: str, estado: EstadoCotizacion) -> dict[str, bool]:
    """Calcula prerequisitos para que el agente sepa que tools puede usar."""
    texto = mensaje_usuario.lower()
    tiene_referencia_producto_o_paquete = any(
        term in texto
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
    tiene_minimo_para_recomendacion = not estado.campos_faltantes
    tiene_recomendacion = estado.opcion_recomendada is not None
    tiene_cotizacion = estado.cotizacion is not None
    return ContratoDisponibilidadHerramientas(
        puede_responder_precio=tiene_referencia_producto_o_paquete or tiene_recomendacion,
        puede_validar_y_recomendar=tiene_minimo_para_recomendacion,
        puede_generar_cotizacion=tiene_minimo_para_recomendacion and tiene_recomendacion,
        puede_mostrar_imagen=tiene_cotizacion,
    ).a_diccionario()


# Ejecuta la responsabilidad de es solicitud derivacion explicita.
def es_solicitud_derivacion_explicita(message: str) -> bool:
    """Detecta si el usuario pidio de forma explicita derivacion humana."""
    return es_derivacion_humana_explicita(message.lower())
