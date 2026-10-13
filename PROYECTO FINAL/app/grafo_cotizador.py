from __future__ import annotations

# RESUMEN DEL WORKFLOW:
# Este modulo define el grafo LangGraph del cotizador de eventos.
# El grafo NO contiene la logica completa de negocio; orquesta nodos pequeños
# que llaman a funciones del flujo, guardrails, memoria, LLM estructurado y tools.
#
# SECUENCIA PRINCIPAL:
# 1. validar_entrada:
#    bloquea entradas inseguras y resuelve respuestas contextuales a memoria previa.
# 2. extraer_y_enrutar_intencion:
#    guarda el mensaje, clasifica intencion y extrae campos al EstadoCotizacion.
# 3. gestionar_memoria_persistente:
#    busca o retoma cotizaciones anteriores por telefono celular.
# 4. decidir_accion_agentica:
#    usa el decisor LLM estructurado para proponer la siguiente accion.
# 5. ejecutar_tools_negocio:
#    ejecuta cobertura, calendario, catalogo, stock, RAG, cotizacion, imagen y handoff humano.
# 6. evaluar_salida_guardrail:
#    valida la respuesta, agrega memoria visible y persiste sesion/memoria.
#
# ENTRADA PRODUCTIVA:
# frontend Streamlit -> FastAPI app/api.py -> flujo.manejar_mensaje -> ejecutar_grafo_cotizador.
# Tambien existe app/main.py como Streamlit antiguo que llama el mismo flujo.

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.guardrails.entrada import validar_mensaje_entrada
from app.guardrails.salida import asegurar_respuesta_final
from app.observabilidad import configurar_langsmith
from app.estado import EstadoCotizacion
from app.flujo import (
    decidir_accion_agentica_turno,
    detectar_eleccion_previa_usuario,
    ejecutar_decision_negocio,
    finalizar_turno_cotizador,
    manejar_eleccion_previa_pendiente,
    preparar_turno_usuario,
    resolver_memoria_y_elecciones_previas,
)


class EstadoGrafoCotizador(TypedDict, total=False):
    """Estado interno del grafo; envuelve el EstadoCotizacion mas la respuesta del turno."""

    mensaje_usuario: str
    estado_cotizacion: EstadoCotizacion
    respuesta_base: str
    respuesta_final: str
    etapa: str
    finalizado: bool


# ORQUESTADOR LANGGRAPH: crea la entrada del grafo, ejecuta todos los nodos y devuelve la respuesta final.
def ejecutar_grafo_cotizador(mensaje_usuario: str, estado: EstadoCotizacion) -> tuple[str, EstadoCotizacion]:
    """Ejecuta el workflow conversacional del cotizador sobre un EstadoCotizacion existente."""
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


# DEFINICION DEL GRAFO: registra nodos, rutas condicionales y orden de ejecucion del workflow.
@lru_cache(maxsize=1)
def obtener_grafo_cotizador():
    """Compila y cachea el grafo para reutilizarlo en cada turno sin reconstruir nodos."""
    grafo = StateGraph(EstadoGrafoCotizador)

    # NODO validar_entrada:
    # - Proposito: primera defensa del flujo antes de extraer datos o ejecutar tools.
    # - Entrada: mensaje_usuario + EstadoCotizacion actual.
    # - Acciones:
    #   1. Resuelve respuestas contextuales a memoria previa como "retomar la anterior"
    #      o "seguir con esta nueva" antes del guardrail semantico.
    #   2. Aplica guardrail de entrada para bloquear mensajes inseguros o fuera de alcance.
    # - LLM/system prompt: no usa system prompt propio; el guardrail puede usar LLM si esta habilitado.
    # - BD/tools: no consulta Redis, PostgreSQL ni tools de negocio.
    # - Salida: continua al extractor o finaliza con respuesta segura.
    grafo.add_node("validar_entrada", validar_entrada)

    # NODO extraer_y_enrutar_intencion:
    # - Proposito: convertir lenguaje natural en estado operativo.
    # - Entrada: mensaje_usuario validado + EstadoCotizacion.
    # - Acciones:
    #   1. Agrega el mensaje del usuario al historial.
    #   2. Clasifica intencion con LLM estructurado cuando LLM_ENABLED=true.
    #   3. Extrae campos: evento, asistentes, fecha, distrito, nombre, telefono y productos.
    #   4. Aplica guardrails de extraccion para no inventar datos ni capturar nombres falsos.
    # - System prompts:
    #   PROMPT_SISTEMA_CLASIFICADOR_INTENCION y PROMPT_SISTEMA_EXTRACTOR.
    # - Tools: usa la tool interna registrar_campos_extraidos del extractor agentico.
    # - BD: no escribe memoria; puede leer referencias de negocio si BUSINESS_DATA_SOURCE=postgres.
    # - Salida: EstadoCotizacion actualizado con intencion y campos_faltantes.
    grafo.add_node("extraer_y_enrutar_intencion", extraer_y_enrutar_intencion)

    # NODO gestionar_memoria_persistente:
    # - Proposito: decidir si el turno debe continuar con memoria previa o con solicitud actual.
    # - Entrada: EstadoCotizacion con posible contacto o estado_previo_pendiente.
    # - Acciones:
    #   1. Si hay telefono, busca cotizacion anterior en memoria persistente.
    #   2. Si encuentra una previa util, pide elegir entre retomarla o seguir con la nueva.
    #   3. Si el usuario ya eligio, hidrata la cotizacion previa o descarta esa memoria.
    # - LLM/system prompt: no usa LLM; esta parte es deterministica para no mezclar cotizaciones.
    # - BD: con MEMORY_DATA_SOURCE=postgres consulta PostgreSQL JSONB en schema memory.
    # - Redis: no consulta Redis directamente; Redis se usa para sesion activa al final del turno.
    # - Salida: puede finalizar el turno con respuesta de memoria o continuar al decisor.
    grafo.add_node("gestionar_memoria_persistente", gestionar_memoria_persistente)

    # NODO decidir_accion_agentica:
    # - Proposito: elegir la siguiente accion de alto nivel del workflow.
    # - Entrada: mensaje_usuario + EstadoCotizacion ya extraido.
    # - Acciones:
    #   1. Usa el decisor LLM estructurado para proponer una accion: pedir datos,
    #      responder precio, validar/recomendar, generar cotizacion, mostrar imagen,
    #      derivar a humano, responder politica, cerrar, retomar previa o nueva cotizacion.
    #   2. Pasa esa accion por guardrail deterministico antes de cambiar la intencion.
    # - System prompt: PROMPT_SISTEMA_DECISOR.
    # - Tools: no ejecuta tools de negocio; solo decide la ruta.
    # - BD: no consulta Redis ni PostgreSQL.
    # - Salida: EstadoCotizacion con intencion final validada.
    grafo.add_node("decidir_accion_agentica", decidir_accion_agentica)

    # NODO ejecutar_tools_negocio:
    # - Proposito: ejecutar la accion validada usando reglas y tools reales del cotizador.
    # - Entrada: EstadoCotizacion con intencion validada.
    # - Acciones segun intencion:
    #   1. Recoleccion: pide campos faltantes.
    #   2. Cobertura: valida distrito.
    #   3. Calendario: valida fecha disponible y registra evento al cotizar.
    #   4. Catalogo/stock: busca productos, paquetes, disponibilidad y alternativas.
    #   5. Recomendacion: arma propuesta cotizable.
    #   6. Cotizacion: calcula totales, genera imagen y prepara enlace WhatsApp human-in-the-loop.
    #   7. RAG: responde politicas/recargos desde conocimiento externo.
    #   8. Derivacion: genera link mock de WhatsApp si el usuario pidio humano.
    # - LLM/system prompt: no tiene prompt propio; RAG/imagen pueden usar servicios configurados.
    # - BD: con BUSINESS_DATA_SOURCE=postgres lee/escribe tablas de negocio.
    # - Redis/memoria: no persiste sesion; eso ocurre en evaluar_salida_guardrail.
    # - Salida: respuesta_base, etapa y EstadoCotizacion actualizado.
    grafo.add_node("ejecutar_tools_negocio", ejecutar_tools_negocio)

    # NODO evaluar_salida_guardrail:
    # - Proposito: cerrar el turno con una respuesta segura, trazable y persistida.
    # - Entrada: respuesta_base + EstadoCotizacion actualizado.
    # - Acciones:
    #   1. Aplica guardrail final de salida.
    #   2. Puede pulir redaccion con LLM sin cambiar datos de negocio.
    #   3. Agrega memoria visible debajo del mensaje.
    #   4. Guarda sesion activa y memoria persistente si corresponde.
    # - System prompt: SYSTEM_PROMPT en app/llm.py para pulido controlado.
    # - Redis: con SESSION_STORE=redis guarda la sesion activa.
    # - PostgreSQL NoSQL: con MEMORY_DATA_SOURCE=postgres guarda memoria JSONB.
    # - PostgreSQL negocio: no consulta catalogo/calendario aqui.
    # - Salida: respuesta_final lista para API/Streamlit.
    grafo.add_node("evaluar_salida_guardrail", evaluar_salida_guardrail)

    # RUTA 1: todo turno empieza por validar entrada.
    # Si validar_entrada finaliza, salta directo a evaluar_salida_guardrail.
    grafo.add_edge(START, "validar_entrada")
    grafo.add_conditional_edges(
        "validar_entrada",
        ruta_si_finalizado,
        {"finalizar": "evaluar_salida_guardrail", "continuar": "extraer_y_enrutar_intencion"},
    )
    # RUTA 2: si la entrada es valida, se extrae intencion/campos y luego se revisa memoria.
    # La memoria puede detener el turno si debe pedir confirmacion o si retoma una cotizacion.
    grafo.add_edge("extraer_y_enrutar_intencion", "gestionar_memoria_persistente")
    grafo.add_conditional_edges(
        "gestionar_memoria_persistente",
        ruta_si_finalizado,
        {"finalizar": "evaluar_salida_guardrail", "continuar": "decidir_accion_agentica"},
    )
    # RUTA 3: si memoria no finaliza, el decisor propone accion, negocio la ejecuta y salida persiste.
    grafo.add_edge("decidir_accion_agentica", "ejecutar_tools_negocio")
    grafo.add_edge("ejecutar_tools_negocio", "evaluar_salida_guardrail")
    grafo.add_edge("evaluar_salida_guardrail", END)

    return grafo.compile()


# NODO 1 / GUARDRAIL DE ENTRADA:
# Protege el flujo antes de extraer datos. Tambien resuelve elecciones de memoria previa
# porque frases como "seguir con esta nueva" solo tienen sentido dentro de ese contexto.
def validar_entrada(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Valida el mensaje inicial y puede finalizar el turno con una respuesta segura."""
    mensaje = estado_grafo["mensaje_usuario"].strip()
    estado = estado_grafo["estado_cotizacion"]
    estado.registrar_log(
        "nodo_validar_entrada_inicio",
        {
            "mensaje_usuario": mensaje,
            "estado": resumir_estado_para_log(estado),
        },
    )
    # MEMORIA PERSISTENTE / GUARDRAIL CONTEXTUAL:
    # Si el usuario esta respondiendo a "retomar la anterior" vs "seguir con esta nueva",
    # esa frase depende del contexto y debe resolverse antes del guardrail semantico.
    if estado.estado_previo_pendiente and detectar_eleccion_previa_usuario(mensaje):
        resultado_memoria = manejar_eleccion_previa_pendiente(mensaje, estado)
        if resultado_memoria:
            respuesta, estado_resuelto = resultado_memoria
            estado_resuelto.registrar_log(
                "nodo_validar_entrada_eleccion_previa",
                {"eleccion_resuelta": True, "estado": resumir_estado_para_log(estado_resuelto)},
            )
            return {
                **estado_grafo,
                "estado_cotizacion": estado_resuelto,
                "respuesta_base": respuesta,
                "etapa": estado_resuelto.etapa,
                "finalizado": True,
            }
    validacion = validar_mensaje_entrada(mensaje)
    estado.registrar_log(
        "nodo_validar_entrada",
        {
            "bloqueado": not validacion.permitido,
            "motivo": validacion.motivo,
        },
    )
    if not validacion.permitido:
        # Registra el mensaje del usuario en el historial para que la UI muestre el intercambio.
        # No se ejecuta preparar_turno_usuario, asi que lo hacemos aqui de forma minima.
        estado.mensajes.append({"role": "user", "content": mensaje})
        return {
            **estado_grafo,
            "estado_cotizacion": estado,
            "respuesta_base": validacion.respuesta_segura,
            "etapa": "guardrail_entrada",
            "finalizado": True,
        }
    return {**estado_grafo, "finalizado": False}


# NODO 2 / EXTRACCION Y ROUTER:
# Interpreta el mensaje, actualiza memoria temporal y deja lista la intencion del turno.
def extraer_y_enrutar_intencion(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Extrae campos e intencion usando LLM estructurado, reglas y guardrails de extraccion."""
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


# NODO 3 / MEMORIA PERSISTENTE:
# Decide si hay cotizacion previa asociada al telefono y si debe retomarse o descartarse.
def gestionar_memoria_persistente(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Consulta memoria persistente por telefono y resuelve cotizaciones previas pendientes."""
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


# NODO 4 / DECISOR AGENTICO:
# El LLM estructurado propone una accion, pero el guardrail de decision la valida antes de ejecutarla.
def decidir_accion_agentica(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Calcula la accion del turno y la convierte en una intencion ejecutable."""
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


# NODO 5 / TOOLS DE NEGOCIO:
# Ejecuta la logica real del cotizador: validaciones, catalogo, cotizacion, imagen y handoff humano.
def ejecutar_tools_negocio(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Ejecuta la rama de negocio correspondiente a la intencion validada."""
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


# NODO 6 / GUARDRAIL DE SALIDA Y PERSISTENCIA:
# Valida, pule, agrega memoria visible y guarda la sesion/memoria despues de cada turno.
def evaluar_salida_guardrail(estado_grafo: EstadoGrafoCotizador) -> EstadoGrafoCotizador:
    """Prepara la respuesta final segura y persiste el estado actualizado."""
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


# ROUTER LANGGRAPH: decide si una ruta condicional continua o salta a salida final.
def ruta_si_finalizado(estado_grafo: EstadoGrafoCotizador) -> str:
    """Devuelve 'finalizar' cuando un nodo ya resolvio el turno; si no, devuelve 'continuar'."""
    return "finalizar" if estado_grafo.get("finalizado") else "continuar"


# OBSERVABILIDAD / DEBUG:
# Resume el estado para logs sin serializar datos enormes como mensajes, opciones completas o imagen.
def resumir_estado_para_log(estado: EstadoCotizacion) -> dict[str, object]:
    """Devuelve valores clave para entender en logs que hizo cada nodo."""
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
