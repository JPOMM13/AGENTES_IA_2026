from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from app.contratos import ContratoDisponibilidadHerramientas
from app.guardrails.decision import (
    es_derivacion_humana_explicita,
    es_solicitud_generar_cotizacion,
    es_solicitud_nueva_cotizacion,
    es_solicitud_recuperar_memoria,
)
from app.guardrails.capa_intermedia import invocar_agente_con_guardrails, obtener_middleware_langchain_guardrails
from app.configuracion_llm import obtener_configuracion_llm
from app.estado import EstadoCotizacion
from app.modelo_agentico import construir_modelo_chat_agentico, debe_usar_retorno_directo_agentico
from app.prompts_agenticos import PROMPT_SISTEMA_DECISOR


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


# CONFIGURACION AGENTICA: valida si el agente con create_agent debe activarse segun el .env.
def debe_usar_create_agent() -> bool:
    """Indica si la capa agentica con create_agent esta habilitada."""
    return obtener_configuracion_llm().habilitado


# AGENTE DECISOR CREATE_AGENT: interpreta la intencion del usuario y propone una accion, sin ejecutar negocio directamente.
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
                                "solicito_derivar": es_solicitud_derivacion_explicita(mensaje_usuario),
                                "solicito_recuperar_memoria": es_solicitud_recuperar_memoria(mensaje_usuario.lower()),
                                "solicito_empezar_otro_pedido": es_solicitud_nueva_cotizacion(mensaje_usuario.lower()),
                                "solicito_emitir_propuesta": es_solicitud_generar_cotizacion(mensaje_usuario.lower(), estado),
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


# CACHE AGENTICO: reutiliza el agente decisor para no recrearlo en cada interaccion.
@lru_cache(maxsize=1)
def obtener_agente_decisor():
    """Devuelve el agente decisor cacheado para no recrearlo por mensaje."""
    return crear_agente_decisor()


# AGENTE DECISOR CREATE_AGENT: construye el agente con su system prompt, tool de decision y middleware guardrail.
def crear_agente_decisor():
    """Crea el agente decisor con create_agent usando el LLM configurado."""
    from langchain.agents import create_agent
    from langchain.tools import tool

    # TOOL DEL AGENTE DECISOR: devuelve una accion permitida segun prerequisitos, evitando que el LLM salte validaciones.
    @tool(return_direct=debe_usar_retorno_directo_agentico())
    def elegir_accion_workflow(
        mensaje_usuario: str,
        tiene_campos_faltantes: bool,
        tiene_recomendacion: bool,
        tiene_cotizacion: bool,
        puede_responder_precio: bool,
        puede_validar_y_recomendar: bool,
        puede_generar_cotizacion: bool,
        puede_mostrar_imagen: bool,
        solicito_derivar: bool = False,
        solicito_recuperar_memoria: bool = False,
        solicito_empezar_otro_pedido: bool = False,
        solicito_emitir_propuesta: bool = False,
    ) -> str:
        """Elige accion respetando prerequisitos minimos antes de usar tools."""
        texto = mensaje_usuario.lower()
        if solicito_emitir_propuesta:
            if puede_generar_cotizacion:
                return "generar_cotizacion"
            return "validar_y_recomendar" if puede_validar_y_recomendar else "pedir_campos_faltantes"
        if solicito_empezar_otro_pedido:
            return "nueva_cotizacion"
        if solicito_recuperar_memoria:
            return "retomar_previa"
        if any(term in texto for term in ["imagen", "foto", "visual"]):
            return "mostrar_imagen" if puede_mostrar_imagen else "pedir_campos_faltantes"
        if solicito_derivar:
            return "derivacion"
        if any(term in texto for term in ["politica", "feriado", "anticipacion", "anticipación"]):
            return "responder_politica"
        if any(term in texto for term in ["cerrar", "finalizar", "terminar"]):
            return "cierre"
        if es_solicitud_generar_cotizacion(texto):
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

    config = obtener_configuracion_llm()
    modelo = construir_modelo_chat_agentico(config)
    # CREATE_AGENT / LLM: une modelo configurado, system prompt centralizado, tool y middleware guardrail.
    agente = create_agent(
        model=modelo,
        tools=[elegir_accion_workflow],
        system_prompt=PROMPT_SISTEMA_DECISOR,
        middleware=obtener_middleware_langchain_guardrails(),
    )
    return agente


# VALIDACION DE SALIDA AGENTICA: extrae una accion permitida escrita en español por el agente.
def extraer_accion_permitida(content: str) -> DecisionAgente | None:
    """Extrae una accion valida desde texto o salida de tool."""
    acciones_permitidas = {
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
    for accion in acciones_permitidas:
        if accion in texto:
            return accion  # type: ignore[return-value]
    return None


# VALIDACION DE SALIDA AGENTICA: prioriza la salida de tool sobre texto libre para reducir alucinaciones.
def extraer_decision_de_mensajes(mensajes: list) -> DecisionAgente | None:
    """Obtiene la decision final priorizando salidas estructuradas."""
    # Prefer tool outputs over final LLM prose. The final prose may hallucinate
    # business facts; the tool output is the constrained accion contract.
    for message in reversed(mensajes):
        content = getattr(message, "content", "")
        decision = extraer_accion_permitida(str(content))
        if decision:
            return decision
    return None


# CONTRATO DE TOOLS / VALIDACION PREVIA: informa al agente que herramientas puede pedir segun datos ya capturados.
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


# VALIDACION DE DERIVACION HUMANA: confirma que la derivacion fue solicitada explicitamente por el usuario.
def es_solicitud_derivacion_explicita(message: str) -> bool:
    """Detecta si el usuario pidio de forma explicita derivacion humana."""
    return es_derivacion_humana_explicita(message.lower())
