from __future__ import annotations

# RESUMEN: ESTE MODULO IMPLEMENTA EL WORKFLOW AGENTICO CON LANGGRAPH.
# RESUMEN: EL GRAFO ORQUESTA GUARDRAIL DE ENTRADA, EXTRACCION/ROUTER,
# MEMORIA PERSISTENTE, DECISION AGENTICA, TOOLS DE NEGOCIO
# Y GUARDRAIL/EVALUADOR DE SALIDA ANTES DE RESPONDER AL USUARIO.
# RUTA PRODUCTIVA:
# main/API -> flujo.manejar_mensaje -> ejecutar_grafo_cotizador -> nodos
# validar_entrada -> extraer_y_enrutar_intencion -> gestionar_memoria_persistente
# -> decidir_accion_agentica -> ejecutar_tools_negocio -> evaluar_salida_guardrail.

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.guardrails.entrada import validar_mensaje_entrada
from app.guardrails.salida import asegurar_respuesta_final
from app.observabilidad import configurar_langsmith
from app.estado import EstadoCotizacion
from app.flujo import (
    decidir_accion_agentica_turno,
    ejecutar_decision_negocio,
    finalizar_turno_cotizador,
    preparar_turno_usuario,
    resolver_memoria_y_elecciones_previas,
)


class EstadoGrafoCotizador(TypedDict, total=False):
    """Estado interno que viaja entre nodos del grafo LangGraph."""

    mensaje_usuario: str
    estado_cotizacion: EstadoCotizacion
    respuesta_base: str
    respuesta_final: str
    etapa: str
    finalizado: bool


# NODO LANGGRAPH / ORQUESTADOR: punto de entrada del workflow agentico; recibe el mensaje y ejecuta el grafo completo.
def ejecutar_grafo_cotizador(mensaje_usuario: str, estado: EstadoCotizacion) -> tuple[str, EstadoCotizacion]:
    """Ejecuta el workflow agentico conversacional basado en LangGraph."""
    configurar_langsmith()
    estado.registrar_log(
        "grafo_inicio",
        {
            "mensaje_usuario": mensaje_usuario,
            "estado_inicial": resumir_estado_para_log(estado),
        },
    )
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
    resultado["estado_cotizacion"].registrar_log(
        "grafo_fin",
        {
            "etapa": resultado.get("etapa"),
            "finalizado": resultado.get("finalizado"),
            "respuesta_base": resultado.get("respuesta_base"),
            "respuesta_final": resultado.get("respuesta_final"),
            "estado_final": resumir_estado_para_log(resultado["estado_cotizacion"]),
        },
    )
    return resultado["respuesta_final"], resultado["estado_cotizacion"]


# NODO LANGGRAPH / DEFINICION DEL GRAFO: registra nodos, rutas y orden de ejecucion del flujo conversacional.
@lru_cache(maxsize=1)
def obtener_grafo_cotizador():
    """Compila y reutiliza el grafo para no reconstruirlo en cada mensaje."""
    grafo = StateGraph(EstadoGrafoCotizador)

    # NODO validar_entrada:
    # - Que hace: revisa el texto del usuario antes de usar LLM, memoria o tools.
    # - LLM/system prompt: no usa LLM ni system prompt; es validacion deterministica.
    # - Tools/BD: no usa tools, Redis, PostgreSQL negocio ni PostgreSQL NoSQL memory.
    grafo.add_node("validar_entrada", validar_entrada)

    # NODO extraer_y_enrutar_intencion:
    # - Que hace: entiende que quiere el usuario, extrae campos del evento y actualiza EstadoCotizacion.
    # - LLM: si LLM_ENABLED=true usa OpenAI segun LLM_PROVIDER=openai y LLM_MODEL del .env.
    # - System prompts: PROMPT_SISTEMA_CLASIFICADOR_INTENCION para intencion y PROMPT_SISTEMA_EXTRACTOR para campos.
    # - Tools: usa tool interna registrar_campos_extraidos; no ejecuta negocio.
    # - BD: no consulta Redis, PostgreSQL negocio ni PostgreSQL NoSQL memory.
    grafo.add_node("extraer_y_enrutar_intencion", extraer_y_enrutar_intencion)

    # NODO gestionar_memoria_persistente:
    # - Que hace: busca cotizaciones anteriores por telefono/correo y resuelve si retomar o seguir con la actual.
    # - LLM/system prompt: no usa LLM actualmente; la eleccion previa pendiente se valida por codigo.
    # - Tools: no usa tools agenticas.
    # - BD: con MEMORY_DATA_SOURCE=postgres consulta PostgreSQL NoSQL memory en memory.jpomm_memoria_cotizaciones.
    # - Redis/PostgreSQL negocio: no usa Redis ni PostgreSQL negocio en este nodo.
    grafo.add_node("gestionar_memoria_persistente", gestionar_memoria_persistente)

    # NODO decidir_accion_agentica:
    # - Que hace: decide la siguiente accion del workflow: pedir faltantes, recomendar, cotizar, derivar, etc.
    # - LLM: si LLM_ENABLED=true usa create_agent con OpenAI segun LLM_PROVIDER=openai.
    # - System prompt: PROMPT_SISTEMA_DECISOR.
    # - Tools: usa tool interna elegir_accion_workflow; esa tool solo devuelve una accion permitida.
    # - BD: no consulta Redis, PostgreSQL negocio ni PostgreSQL NoSQL memory.
    grafo.add_node("decidir_accion_agentica", decidir_accion_agentica)

    # NODO ejecutar_tools_negocio:
    # - Que hace: ejecuta negocio real: cobertura, calendario, catalogo, stock, RAG, recomendacion, cotizacion e imagen.
    # - LLM/system prompt: no usa un system prompt propio del nodo; RAG usa embeddings/OpenAI y la imagen depende de IMAGE_GENERATION_ENABLED.
    # - Tools: si usa tools de negocio del cotizador.
    # - BD: con BUSINESS_DATA_SOURCE=postgres consulta PostgreSQL negocio; con RAG_THRESHOLD configurado puede consultar RAG.
    # - Redis/PostgreSQL NoSQL memory: no usa Redis ni memoria persistente en este nodo.
    grafo.add_node("ejecutar_tools_negocio", ejecutar_tools_negocio)

    # NODO evaluar_salida_guardrail:
    # - Que hace: valida la respuesta final, la pule si corresponde, agrega memoria visible y persiste el turno.
    # - LLM: si LLM_ENABLED=true puede usar OpenAI para pulido final.
    # - System prompt: SYSTEM_PROMPT en app/llm.py, limitado a reescribir sin inventar datos.
    # - Tools: no usa tools de negocio.
    # - BD: con SESSION_STORE=redis guarda sesion corta en Redis; con MEMORY_DATA_SOURCE=postgres guarda memoria persistente en PostgreSQL NoSQL memory.
    # - PostgreSQL negocio: no consulta tablas de negocio en este nodo.
    grafo.add_node("evaluar_salida_guardrail", evaluar_salida_guardrail)

    # RUTA LANGGRAPH: primero entra el guardrail de entrada; si bloquea, salta a salida segura.
    grafo.add_edge(START, "validar_entrada")
    grafo.add_conditional_edges(
        "validar_entrada",
        ruta_si_finalizado,
        {"finalizar": "evaluar_salida_guardrail", "continuar": "extraer_y_enrutar_intencion"},
    )
    # RUTA LANGGRAPH: despues de extraer datos, memoria puede resolver el turno o dejar continuar al decisor.
    grafo.add_edge("extraer_y_enrutar_intencion", "gestionar_memoria_persistente")
    grafo.add_conditional_edges(
        "gestionar_memoria_persistente",
        ruta_si_finalizado,
        {"finalizar": "evaluar_salida_guardrail", "continuar": "decidir_accion_agentica"},
    )
    # RUTA LANGGRAPH: el decisor elige accion; las tools ejecutan negocio; salida valida y persiste respuesta.
    grafo.add_edge("decidir_accion_agentica", "ejecutar_tools_negocio")
    grafo.add_edge("ejecutar_tools_negocio", "evaluar_salida_guardrail")
    grafo.add_edge("evaluar_salida_guardrail", END)

    return grafo.compile()


# GUARDRAIL DE ENTRADA / NODO LANGGRAPH: bloquea mensajes inseguros antes de usar LLM, memoria o tools.
def validar_entrada(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Aplica guardrail simple de entrada antes de usar LLM o tools."""
    mensaje = estado_grafo["mensaje_usuario"].strip()
    estado = estado_grafo["estado_cotizacion"]
    estado.registrar_log(
        "nodo_validar_entrada_inicio",
        {
            "mensaje_usuario": mensaje,
            "estado": resumir_estado_para_log(estado),
        },
    )
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


# EXTRACCION / NODO LANGGRAPH: interpreta el mensaje, actualiza memoria temporal y deja lista la intencion del turno.
def extraer_y_enrutar_intencion(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Usa extractor LLM/reglas para actualizar estado y dejar la intencion lista."""
    mensaje = estado_grafo["mensaje_usuario"]
    estado_entrada = estado_grafo["estado_cotizacion"]
    estado_entrada.registrar_log(
        "nodo_extraer_y_enrutar_intencion_inicio",
        {
            "mensaje_usuario": mensaje,
            "estado_antes": resumir_estado_para_log(estado_entrada),
        },
    )
    estado = preparar_turno_usuario(mensaje, estado_grafo["estado_cotizacion"])
    estado.registrar_log(
        "nodo_extraer_y_enrutar_intencion",
        {
            "intencion": estado.intencion,
            "campos_faltantes": estado.campos_faltantes,
            "estado_despues": resumir_estado_para_log(estado),
        },
    )
    return {**estado_grafo, "estado_cotizacion": estado}


# MEMORIA PERSISTENTE / NODO LANGGRAPH: consulta o retoma una cotizacion previa cuando el usuario lo solicita.
def gestionar_memoria_persistente(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Consulta memoria persistente si hay contacto o si existe una eleccion pendiente."""
    mensaje = estado_grafo["mensaje_usuario"]
    estado = estado_grafo["estado_cotizacion"]
    estado.registrar_log(
        "nodo_gestionar_memoria_persistente_inicio",
        {
            "mensaje_usuario": mensaje,
            "estado_antes": resumir_estado_para_log(estado),
        },
    )
    resultado = resolver_memoria_y_elecciones_previas(mensaje, estado)
    estado.registrar_log(
        "nodo_gestionar_memoria_persistente",
        {"resuelto_en_memoria": bool(resultado), "contacto": estado.contacto},
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


# AGENTE DECISOR / NODO LANGGRAPH: permite que create_agent elija la siguiente accion de alto nivel.
def decidir_accion_agentica(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Permite que create_agent decida la siguiente accion de alto nivel."""
    mensaje = estado_grafo["mensaje_usuario"]
    estado_entrada = estado_grafo["estado_cotizacion"]
    estado_entrada.registrar_log(
        "nodo_decidir_accion_agentica_inicio",
        {
            "mensaje_usuario": mensaje,
            "estado_antes": resumir_estado_para_log(estado_entrada),
        },
    )
    estado = decidir_accion_agentica_turno(mensaje, estado_grafo["estado_cotizacion"])
    estado.registrar_log(
        "nodo_decidir_accion_agentica",
        {
            "intent_resultante": estado.intencion,
            "estado_despues": resumir_estado_para_log(estado),
        },
    )
    return {**estado_grafo, "estado_cotizacion": estado}


# TOOLS DE NEGOCIO / NODO LANGGRAPH: ejecuta catalogo, cobertura, stock, precios y cotizacion.
def ejecutar_tools_negocio(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Ejecuta reglas de negocio y tools: catalogo, stock, cobertura y cotizacion."""
    mensaje = estado_grafo["mensaje_usuario"]
    estado_entrada = estado_grafo["estado_cotizacion"]
    estado_entrada.registrar_log(
        "nodo_ejecutar_tools_negocio_inicio",
        {
            "mensaje_usuario": mensaje,
            "estado_antes": resumir_estado_para_log(estado_entrada),
        },
    )
    respuesta, estado, etapa = ejecutar_decision_negocio(mensaje, estado_grafo["estado_cotizacion"])
    estado.registrar_log(
        "nodo_ejecutar_tools_negocio",
        {
            "etapa": etapa,
            "respuesta_base": respuesta,
            "estado_despues": resumir_estado_para_log(estado),
        },
    )
    return {
        **estado_grafo,
        "estado_cotizacion": estado,
        "respuesta_base": respuesta,
        "etapa": etapa,
        "finalizado": True,
    }


# GUARDRAIL DE SALIDA / NODO LANGGRAPH: valida la respuesta final antes de persistirla y mostrarla al usuario.
def evaluar_salida_guardrail(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Aplica evaluacion final antes de persistir y mostrar la respuesta."""
    estado = estado_grafo["estado_cotizacion"]
    respuesta = estado_grafo.get("respuesta_base") or "No pude completar el turno. Intentemos nuevamente con tu solicitud."
    etapa = estado_grafo.get("etapa") or "respuesta"
    estado.registrar_log(
        "nodo_evaluar_salida_guardrail_inicio",
        {
            "etapa": etapa,
            "respuesta_base": respuesta,
            "estado_antes": resumir_estado_para_log(estado),
        },
    )
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


# ROUTER LANGGRAPH: decide si el grafo continua al siguiente nodo o salta a la salida final.
def ruta_si_finalizado(estado_grafo: EstadoGrafoCotizador) -> str:
    """Decide si el grafo continua o pasa directo a salida."""
    return "finalizar" if estado_grafo.get("finalizado") else "continuar"


# OBSERVABILIDAD / DEBUG: resume el estado para que las trazas sean legibles en el panel tecnico.
def resumir_estado_para_log(estado: EstadoCotizacion) -> dict[str, object]:
    """Devuelve los valores clave que ayudan a seguir el flujo sin serializar todo el estado."""
    return {
        "id_sesion": estado.id_sesion,
        "etapa": estado.etapa,
        "intencion": estado.intencion,
        "tipo_evento": estado.tipo_evento,
        "asistentes": estado.asistentes,
        "fecha_evento": estado.fecha_evento,
        "fecha_parcial": estado.fecha_parcial,
        "distrito": estado.distrito,
        "nombre_cliente": estado.nombre_cliente,
        "contacto": estado.contacto,
        "productos_solicitados": estado.productos_solicitados,
        "productos_no_soportados": estado.productos_solicitados_no_soportados,
        "campos_faltantes": estado.campos_faltantes,
        "cobertura_ok": estado.cobertura_ok,
        "calendario_ok": estado.calendario_ok,
        "disponibilidad_ok": estado.disponibilidad_ok,
        "tiene_recomendacion": estado.opcion_recomendada is not None,
        "tiene_cotizacion": estado.cotizacion is not None,
        "tiene_estado_previo_pendiente": estado.estado_previo_pendiente is not None,
    }
