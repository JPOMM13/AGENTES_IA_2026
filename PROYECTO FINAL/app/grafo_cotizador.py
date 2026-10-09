from __future__ import annotations

# RESUMEN: ESTE MODULO IMPLEMENTA EL WORKFLOW AGENTICO CON LANGGRAPH.
# RESUMEN: EL GRAFO ORQUESTA GUARDRAIL DE ENTRADA, EXTRACCION/ROUTER,
# MEMORIA PERSISTENTE MOCK, DECISION AGENTICA, TOOLS MOCK DE NEGOCIO
# Y GUARDRAIL/EVALUADOR DE SALIDA ANTES DE RESPONDER AL USUARIO.

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.guardrails.entrada import validar_mensaje_entrada
from app.guardrails.salida import asegurar_respuesta_final
from app.observabilidad import configurar_langsmith
from app.state import QuoteState
from app.workflow import (
    decidir_accion_agentica_turno,
    ejecutar_decision_negocio,
    finalizar_turno_cotizador,
    preparar_turno_usuario,
    resolver_memoria_y_elecciones_previas,
)


class EstadoGrafoCotizador(TypedDict, total=False):
    """Estado interno que viaja entre nodos del grafo LangGraph."""

    mensaje_usuario: str
    estado_cotizacion: QuoteState
    respuesta_base: str
    respuesta_final: str
    etapa: str
    finalizado: bool


# Ejecuta la responsabilidad de ejecutar grafo cotizador.
def ejecutar_grafo_cotizador(mensaje_usuario: str, estado: QuoteState) -> tuple[str, QuoteState]:
    """Ejecuta el workflow agentico conversacional basado en LangGraph."""
    configurar_langsmith()
    resultado = obtener_grafo_cotizador().invoke(
        {
            "mensaje_usuario": mensaje_usuario,
            "estado_cotizacion": estado,
            "respuesta_base": "",
            "respuesta_final": "",
            "etapa": "inicio",
            "finalizado": False,
        }
    )
    return resultado["respuesta_final"], resultado["estado_cotizacion"]


# Ejecuta la responsabilidad de obtener grafo cotizador.
@lru_cache(maxsize=1)
def obtener_grafo_cotizador():
    """Compila y reutiliza el grafo para no reconstruirlo en cada mensaje."""
    grafo = StateGraph(EstadoGrafoCotizador)

    grafo.add_node("validar_entrada", validar_entrada)
    grafo.add_node("extraer_y_enrutar_intencion", extraer_y_enrutar_intencion)
    grafo.add_node("gestionar_memoria_persistente", gestionar_memoria_persistente)
    grafo.add_node("decidir_accion_agentica", decidir_accion_agentica)
    grafo.add_node("ejecutar_tools_mock_negocio", ejecutar_tools_mock_negocio)
    grafo.add_node("evaluar_salida_guardrail", evaluar_salida_guardrail)

    grafo.add_edge(START, "validar_entrada")
    grafo.add_conditional_edges(
        "validar_entrada",
        ruta_si_finalizado,
        {"finalizar": "evaluar_salida_guardrail", "continuar": "extraer_y_enrutar_intencion"},
    )
    grafo.add_edge("extraer_y_enrutar_intencion", "gestionar_memoria_persistente")
    grafo.add_conditional_edges(
        "gestionar_memoria_persistente",
        ruta_si_finalizado,
        {"finalizar": "evaluar_salida_guardrail", "continuar": "decidir_accion_agentica"},
    )
    grafo.add_edge("decidir_accion_agentica", "ejecutar_tools_mock_negocio")
    grafo.add_edge("ejecutar_tools_mock_negocio", "evaluar_salida_guardrail")
    grafo.add_edge("evaluar_salida_guardrail", END)

    return grafo.compile()


# Ejecuta la responsabilidad de validar entrada.
def validar_entrada(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Aplica guardrail simple de entrada antes de usar LLM o tools."""
    mensaje = estado_grafo["mensaje_usuario"].strip()
    estado = estado_grafo["estado_cotizacion"]
    validacion = validar_mensaje_entrada(mensaje)
    estado.registrar_log(
        "nodo_validar_entrada",
        {
            "bloqueado": not validacion.permitido,
            "motivo": validacion.motivo,
        },
    )
    if not validacion.permitido:
        return {
            **estado_grafo,
            "respuesta_base": validacion.respuesta_segura,
            "etapa": "guardrail_entrada",
            "finalizado": True,
        }
    return {**estado_grafo, "finalizado": False}


# Ejecuta la responsabilidad de extraer y enrutar intencion.
def extraer_y_enrutar_intencion(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Usa extractor LLM/reglas para actualizar estado y dejar la intencion lista."""
    mensaje = estado_grafo["mensaje_usuario"]
    estado = preparar_turno_usuario(mensaje, estado_grafo["estado_cotizacion"])
    estado.registrar_log(
        "nodo_extraer_y_enrutar_intencion",
        {"intent": estado.intent, "missing_fields": estado.missing_fields},
    )
    return {**estado_grafo, "estado_cotizacion": estado}


# Ejecuta la responsabilidad de gestionar memoria persistente.
def gestionar_memoria_persistente(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Consulta memoria mock si hay contacto o si existe una eleccion pendiente."""
    mensaje = estado_grafo["mensaje_usuario"]
    estado = estado_grafo["estado_cotizacion"]
    resultado = resolver_memoria_y_elecciones_previas(mensaje, estado)
    estado.registrar_log(
        "nodo_gestionar_memoria_persistente",
        {"resuelto_en_memoria": bool(resultado), "contact": estado.contact},
    )
    if not resultado:
        return {**estado_grafo, "estado_cotizacion": estado, "finalizado": False}
    respuesta, estado_resuelto, etapa = resultado
    return {
        **estado_grafo,
        "estado_cotizacion": estado_resuelto,
        "respuesta_base": respuesta,
        "etapa": etapa,
        "finalizado": True,
    }


# Ejecuta la responsabilidad de decidir accion agentica.
def decidir_accion_agentica(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Permite que create_agent decida la siguiente accion de alto nivel."""
    mensaje = estado_grafo["mensaje_usuario"]
    estado = decidir_accion_agentica_turno(mensaje, estado_grafo["estado_cotizacion"])
    estado.registrar_log("nodo_decidir_accion_agentica", {"intent_resultante": estado.intent})
    return {**estado_grafo, "estado_cotizacion": estado}


# Ejecuta la responsabilidad de ejecutar tools mock negocio.
def ejecutar_tools_mock_negocio(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Ejecuta reglas de negocio y tools mock: catalogo, stock, cobertura y cotizacion."""
    mensaje = estado_grafo["mensaje_usuario"]
    respuesta, estado, etapa = ejecutar_decision_negocio(mensaje, estado_grafo["estado_cotizacion"])
    estado.registrar_log("nodo_ejecutar_tools_mock_negocio", {"etapa": etapa})
    return {
        **estado_grafo,
        "estado_cotizacion": estado,
        "respuesta_base": respuesta,
        "etapa": etapa,
        "finalizado": True,
    }


# Ejecuta la responsabilidad de evaluar salida guardrail.
def evaluar_salida_guardrail(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Aplica evaluacion final antes de persistir y mostrar la respuesta."""
    estado = estado_grafo["estado_cotizacion"]
    respuesta = estado_grafo.get("respuesta_base") or "No pude completar el turno. Intentemos nuevamente con tu solicitud."
    etapa = estado_grafo.get("etapa") or "respuesta"
    respuesta_segura = asegurar_respuesta_final(respuesta, estado)
    estado.registrar_log(
        "nodo_evaluar_salida_guardrail",
        {
            "etapa": etapa,
            "respuesta_modificada": respuesta_segura != respuesta,
        },
    )
    respuesta_final, estado_final = finalizar_turno_cotizador(respuesta_segura, estado, etapa)
    return {
        **estado_grafo,
        "estado_cotizacion": estado_final,
        "respuesta_final": respuesta_final,
        "finalizado": True,
    }


# Ejecuta la responsabilidad de ruta si finalizado.
def ruta_si_finalizado(estado_grafo: EstadoGrafoCotizador) -> str:
    """Decide si el grafo continua o pasa directo a salida."""
    return "finalizar" if estado_grafo.get("finalizado") else "continuar"
