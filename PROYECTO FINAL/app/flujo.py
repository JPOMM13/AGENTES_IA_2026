from __future__ import annotations

import re
from datetime import date

from app.estado import EstadoCotizacion
from app.data.datos_mock import CATALOG, PRODUCTS
from app.decisor_agentico import decidir_siguiente_accion_con_agente, obtener_disponibilidad_tools, es_solicitud_derivacion_explicita
from app.artefactos import generar_artefacto_visual_cotizacion
from app.guardrails.decision import validar_decision_agentica
from app.llm import pulir_respuesta
from app.repositorios import RepositorioSesionActiva, RepositorioMemoriaCotizacion
from app.tools.disponibilidad import validar_disponibilidad, validar_stock_productos
from app.tools.catalogo import buscar_catalogo
from app.tools.calendario import registrar_evento_cotizado, validar_calendario_eventos
from app.tools.cobertura import validar_cobertura
from app.tools.dimensionamiento import dimensionar_evento
from app.tools.extraccion import extraer_intencion_y_campos, extraer_productos_mencionados
from app.tools.derivacion import derivar_whatsapp
from app.tools.precios import comparar_opciones, generar_cotizacion
from app.tools.consulta_rag import buscar_rag


REQUIRED_FIELDS = ["tipo_evento", "asistentes", "fecha_evento", "distrito", "nombre_cliente", "contacto", "productos_solicitados"]
ACTIVE_SESSIONS = RepositorioSesionActiva()
QUOTE_MEMORY = RepositorioMemoriaCotizacion()
# RUTEO RAG / PISOS: el acceso por pisos (recargos, ascensor, derivacion) solo lo explica la base de conocimiento.
PATRON_CONSULTA_PISOS = re.compile(r"\b(?:piso|pisos|ascensor|ascensores|escalera|escaleras)\b", re.IGNORECASE)


# WORKFLOW PRINCIPAL: recibe el mensaje del usuario y coordina extraccion, decision, negocio y respuesta.
def manejar_mensaje(mensaje_usuario: str, estado: EstadoCotizacion) -> tuple[str, EstadoCotizacion]:
    """Orquesta el turno usando el grafo LangGraph del cotizador."""
    from app.grafo_cotizador import ejecutar_grafo_cotizador

    return ejecutar_grafo_cotizador(mensaje_usuario, estado)


# WORKFLOW/EXTRACCION: agrega el mensaje al historial y fusiona campos extraidos en memoria temporal.
def preparar_turno_usuario(mensaje_usuario: str, estado: EstadoCotizacion) -> EstadoCotizacion:
    """Registra el mensaje, extrae intencion/campos y actualiza memoria operativa."""
    estado.mensajes.append({"role": "user", "content": mensaje_usuario})
    campos_faltantes_antes = list(estado.campos_faltantes)
    extraction = extraer_intencion_y_campos(mensaje_usuario, estado)
    estado.registrar_log("extraer_intencion_y_campos", extraction)
    fusionar_extraccion_en_estado(estado, extraction)
    asegurar_productos_mencionados_si_eran_faltantes(mensaje_usuario, estado, campos_faltantes_antes)
    estado.campos_faltantes = encontrar_campos_faltantes(estado)
    estado.registrar_log("tool_readiness", obtener_disponibilidad_tools(mensaje_usuario, estado))
    return estado


# MEMORIA PERSISTENTE: resuelve recuperacion de cotizacion previa o elecciones pendientes antes de ejecutar negocio.
def resolver_memoria_y_elecciones_previas(mensaje_usuario: str, estado: EstadoCotizacion) -> tuple[str, EstadoCotizacion, str] | None:
    """Resuelve recuperacion de memoria o eleccion pendiente antes de llamar tools."""
    pending_response = manejar_eleccion_previa_pendiente(mensaje_usuario, estado)
    if pending_response:
        respuesta, estado = pending_response
        return respuesta, estado, estado.etapa

    previous_response = detectar_conversacion_previa_por_contacto(estado)
    if previous_response:
        return previous_response, estado, "validacion_memoria"
    return None


# DECISOR AGENTICO: pide al LLM estructurado una accion y luego la pasa por guardrails de decision.
def decidir_accion_agentica_turno(mensaje_usuario: str, estado: EstadoCotizacion) -> EstadoCotizacion:
    """Usa el decisor LLM estructurado para decidir accion de alto nivel cuando corresponde."""
    if PATRON_CONSULTA_PISOS.search(mensaje_usuario):
        estado.intencion = "consulta_general"
        estado.registrar_log("ruteo_rag_pisos", {"motivo": "consulta_acceso_por_pisos"})
        return estado
    agent_action = decidir_siguiente_accion_con_agente(mensaje_usuario, estado)
    if agent_action:
        estado.registrar_log("decision_llm_estructurada", {"accion": agent_action})
    accion_validada = validar_decision_agentica(agent_action, mensaje_usuario, estado)
    if accion_validada:
        aplicar_accion_agente_a_intencion(accion_validada, estado, mensaje_usuario)
    return estado


# WORKFLOW DE NEGOCIO: ejecuta la rama correspondiente segun la intencion validada del turno.
def ejecutar_decision_negocio(mensaje_usuario: str, estado: EstadoCotizacion) -> tuple[str, EstadoCotizacion, str]:
    """Ejecuta las tools de negocio segun el estado/intencion."""
    if estado.errores_validacion_campos:
        respuesta = renderizar_respuesta_validacion_campos(estado)
        return respuesta, estado, "validacion_campos"

    if estado.intencion == "solicitud_imagen":
        respuesta = renderizar_respuesta_solicitud_imagen(estado)
        return respuesta, estado, "imagen"

    if estado.intencion == "cierre":
        respuesta = renderizar_respuesta_cierre(estado)
        return respuesta, estado, "cierre"

    if estado.intencion == "consulta_memoria":
        respuesta = renderizar_respuesta_consulta_memoria(estado)
        return respuesta, estado, "memoria"

    if estado.intencion == "retomar_previa":
        respuesta, estado = manejar_retomar_previa(estado)
        return respuesta, estado, "memoria_previa"

    if estado.intencion == "saludo":
        respuesta = renderizar_respuesta_saludo(estado)
        return respuesta, estado, "saludo"

    if estado.intencion == "revisar_pedido":
        respuesta = renderizar_respuesta_revision_pedido(estado)
        return respuesta, estado, "revision_pedido"

    if estado.intencion == "consulta_general":
        respuesta = renderizar_respuesta_rag(mensaje_usuario, estado)
        return respuesta, estado, "politica"

    if estado.intencion == "consulta_precio":
        respuesta = renderizar_respuesta_consulta_precio(mensaje_usuario, estado)
        return respuesta, estado, "consulta_precio"

    if estado.intencion == "derivacion_humana":
        estado.derivacion_confirmada = True
        handoff = preparar_derivacion_humana(estado, "Solicitud explicita del usuario.")
        respuesta = renderizar_respuesta_derivacion(handoff)
        return respuesta, estado, "derivacion"

    if estado.intencion in {"solicitud_descuento", "solicitud_pago"}:
        estado.derivacion_ofrecida = True
        respuesta = pedir_confirmacion_derivacion(estado)
        return respuesta, estado, "derivacion_ofrecida"

    if estado.intencion == "modificar_pedido":
        respuesta = renderizar_respuesta_revision_pedido(estado)
        if not estado.cambio_producto_limpio_no_soportados:
            return respuesta, estado, "pedido_modificado"

    if estado.intencion == "confirmacion_derivacion" and estado.derivacion_ofrecida:
        estado.derivacion_confirmada = True
        handoff = preparar_derivacion_humana(estado, "Usuario acepta derivacion por WhatsApp.")
        respuesta = renderizar_respuesta_derivacion(handoff)
        return respuesta, estado, "derivacion"

    estado.registrar_log("encontrar_campos_faltantes", {"campos_faltantes": estado.campos_faltantes})
    if estado.distrito and "distrito" not in estado.campos_faltantes and estado.cobertura_ok is not True:
        coverage = validar_cobertura(estado)
        estado.cobertura_ok = coverage["ok"]
        estado.registrar_log("validar_cobertura_temprana", coverage)
        if not coverage["ok"]:
            respuesta = renderizar_respuesta_sin_cobertura(estado, coverage)
            return respuesta, estado, "sin_cobertura"

    if estado.campos_faltantes:
        respuesta = pedir_campos_faltantes_para_estado(estado)
        return respuesta, estado, "recoleccion"

    if estado.productos_solicitados_no_soportados:
        respuesta = renderizar_respuesta_productos_no_soportados(estado)
        return respuesta, estado, "alternativas_producto"

    coverage = validar_cobertura(estado)
    estado.cobertura_ok = coverage["ok"]
    estado.registrar_log("validar_cobertura", coverage)
    if not coverage["ok"]:
        respuesta = renderizar_respuesta_sin_cobertura(estado, coverage)
        return respuesta, estado, "sin_cobertura"

    calendario = validar_calendario_eventos(estado)
    estado.calendario_ok = calendario["ok"]
    estado.registrar_log("validar_calendario_eventos", calendario)
    if not calendario["ok"]:
        respuesta = renderizar_respuesta_fecha_ocupada(estado, calendario)
        return respuesta, estado, "fecha_ocupada"

    catalog_result = buscar_catalogo(estado)
    estado.opciones_catalogo = catalog_result["options"]
    estado.registrar_log("catalogo_productos", {"products": catalog_result["products"]})
    estado.registrar_log("buscar_catalogo", catalog_result)

    availability = validar_disponibilidad(estado, estado.opciones_catalogo)
    estado.opciones_validas = availability["available_options"]
    estado.opciones_descartadas = availability["opciones_descartadas"]
    estado.disponibilidad_ok = bool(estado.opciones_validas)
    estado.registrar_log("validar_disponibilidad", availability)
    estado.dimensionamiento = dimensionar_evento(estado)
    estado.registrar_log("dimensionar_evento", estado.dimensionamiento)

    if estado.opciones_validas:
        comparison = comparar_opciones(estado)
        estado.opcion_recomendada = comparison["recommended"]
        estado.opcion_recomendada["origen"] = "package"
        estado.registrar_log("comparar_opciones", comparison)
    else:
        stock_result = validar_stock_productos(estado, estado.dimensionamiento["items"], catalog_result["all_products"])
        estado.registrar_log("validar_stock_productos", stock_result)
        if stock_result["missing_items"]:
            estado.disponibilidad_ok = False
            estado.productos_sin_stock = [item["concept"] for item in stock_result["missing_items"]]
            estado.derivacion_ofrecida = True
            respuesta = renderizar_respuesta_sin_stock(estado, stock_result)
            return respuesta, estado, "sin_stock"
        estado.disponibilidad_ok = True
        estado.derivacion_ofrecida = False
        estado.productos_sin_stock = []
        estado.opcion_recomendada = construir_opcion_basada_en_productos(estado, stock_result["available_items"], catalog_result["similar_packages"])
        estado.registrar_log("construir_opcion_basada_en_productos", estado.opcion_recomendada)

    if estado.intencion == "cotizacion" or _parece_confirmacion_cotizacion(mensaje_usuario):
        estado.cotizacion = generar_cotizacion(estado)
        estado.registrar_log("generar_cotizacion", estado.cotizacion)
        reserva_evento = registrar_evento_cotizado(estado)
        estado.registrar_log("registrar_evento_cotizado", reserva_evento)
        estado.imagen_artefacto_cotizacion = generar_artefacto_visual_cotizacion(estado)
        estado.registrar_log("generar_artefacto_visual_cotizacion", {"path": estado.imagen_artefacto_cotizacion})
        # HUMAN-IN-THE-LOOP: al emitir cotizacion se prepara un enlace simulado para continuar la venta con un asesor.
        preparar_derivacion_humana(estado, "Cotizacion generada; continuar cierre comercial con asesor humano.")
        respuesta = renderizar_respuesta_cotizacion(estado)
        return respuesta, estado, "cotizacion"

    respuesta = renderizar_respuesta_recomendacion(estado)
    return respuesta, estado, "recomendacion"


# PERSISTENCIA/SALIDA: guarda memoria y pule la respuesta antes de devolverla a Streamlit.
def finalizar_turno_cotizador(respuesta: str, estado: EstadoCotizacion, etapa: str) -> tuple[str, EstadoCotizacion]:
    """Aplica pulido, memoria visible y persistencia despues del grafo."""
    return _finalizar(respuesta, estado, etapa)


# MEMORIA TEMPORAL: actualiza el estado de cotizacion solo con campos extraidos y validados.
def fusionar_extraccion_en_estado(estado: EstadoCotizacion, extraction: dict) -> None:
    """Actualiza el estado conversacional con los campos extraidos."""
    estado.intencion = extraction["intencion"]
    estado.cambio_producto_limpio_no_soportados = False
    estado.errores_validacion_campos = []
    fields = extraction.get("fields", {})
    estado.errores_validacion_campos = list(fields.get("errores_validacion_campos", []))
    if estado.intencion == "nueva_cotizacion":
        limpiar_estado_para_nueva_cotizacion(estado)
        estado.intencion = "recomendacion"
    if fields.get("product_changes"):
        aplicar_cambios_productos(estado, fields["product_changes"])

    for key in ["tipo_evento", "asistentes", "fecha_evento", "distrito", "presupuesto", "nombre_cliente", "contacto"]:
        value = fields.get(key)
        if value is not None:
            if key == "fecha_evento" and not fecha_evento_es_valida(value):
                estado.errores_validacion_campos.append(f"La fecha indicada no es valida: {value}.")
                continue
            setattr(estado, key, value)
            if key == "fecha_evento":
                estado.fecha_parcial = {"dia": None, "mes": None, "anio": None}

    if fields.get("fecha_parcial") and not estado.fecha_evento:
        fusionar_fecha_parcial(estado, fields["fecha_parcial"])

    for preference in fields.get("preferencias", []):
        if preference not in estado.preferencias:
            estado.preferencias.append(preference)

    if debe_fusionar_productos_solicitados(estado.intencion, fields.get("product_changes", {})):
        for product in fields.get("productos_solicitados", []):
            if product not in estado.productos_solicitados:
                estado.productos_solicitados.append(product)
            estado.productos_solicitados_no_soportados = [
                unsupported
                for unsupported in estado.productos_solicitados_no_soportados
                if product not in productos_similares_para(unsupported)
            ]

    for product in fields.get("productos_solicitados_no_soportados", []):
        if product not in estado.productos_solicitados_no_soportados:
            estado.productos_solicitados_no_soportados.append(product)

    if estado.intencion == "modificar_pedido":
        estado.cotizacion = None
        estado.opcion_recomendada = None
        estado.opciones_catalogo = []
        estado.opciones_validas = []
        estado.opciones_descartadas = []
        estado.dimensionamiento = None


# GUARDRAIL DE PRODUCTOS: si el flujo pidio productos y el usuario los dio, no deja que el LLM los ignore.
def asegurar_productos_mencionados_si_eran_faltantes(
    mensaje_usuario: str,
    estado: EstadoCotizacion,
    campos_faltantes_antes: list[str],
) -> None:
    """Guarda productos concretos dados como respuesta directa al pedido de productos."""
    if "productos_solicitados" not in campos_faltantes_antes:
        return
    productos_mencionados = extraer_productos_mencionados(mensaje_usuario)
    if not productos_mencionados:
        return
    for producto in productos_mencionados:
        if producto not in estado.productos_solicitados:
            estado.productos_solicitados.append(producto)
    if estado.intencion in {"revisar_pedido", "modificar_pedido"}:
        estado.intencion = "recomendacion"
    estado.registrar_log(
        "guardrail_productos_mencionados",
        {"productos_agregados": productos_mencionados, "motivo": "respuesta_a_productos_faltantes"},
    )


# MEMORIA TEMPORAL: reinicia datos de cotizacion cuando el usuario pide una nueva solicitud.
def limpiar_estado_para_nueva_cotizacion(estado: EstadoCotizacion) -> None:
    """Limpia datos de negocio para iniciar otra cotizacion en la misma sesion."""
    estado.registrar_log("limpiar_estado_para_nueva_cotizacion", {"previous_contact": estado.contacto})
    estado.etapa = "recoleccion"
    estado.tipo_evento = None
    estado.asistentes = None
    estado.fecha_evento = None
    estado.fecha_parcial = {"dia": None, "mes": None, "anio": None}
    estado.distrito = None
    estado.presupuesto = None
    estado.productos_solicitados = []
    estado.productos_solicitados_no_soportados = []
    estado.productos_sin_stock = []
    estado.preferencias = []
    estado.nombre_cliente = None
    estado.contacto = None
    estado.campos_faltantes = []
    estado.opciones_catalogo = []
    estado.opciones_validas = []
    estado.opciones_descartadas = []
    estado.opcion_recomendada = None
    estado.dimensionamiento = None
    estado.cotizacion = None
    estado.cobertura_ok = None
    estado.calendario_ok = None
    estado.disponibilidad_ok = None
    estado.politica_ok = None
    estado.derivacion_ofrecida = False
    estado.derivacion_confirmada = False
    estado.resumen_derivacion = None
    estado.imagen_solicitada = False
    estado.imagen_artefacto_cotizacion = None
    estado.cambio_producto_limpio_no_soportados = False
    estado.estado_previo_pendiente = None
    estado.errores_validacion_campos = []


# MEMORIA PERSISTENTE: busca una cotizacion previa usando el contacto como identificador principal.
def detectar_conversacion_previa_por_contacto(estado: EstadoCotizacion) -> str | None:
    """Busca automaticamente memoria previa cuando aparece un contacto."""
    if not estado.contacto or estado.estado_previo_pendiente or estado.intencion == "retomar_previa":
        return None
    # MEMORIA PERSISTENTE: consulta por telefono para saber si existe una cotizacion previa.
    previo = QUOTE_MEMORY.buscar_por_contacto(estado.contacto)
    if not previo or previo.id_sesion == estado.id_sesion:
        return None
    if not tiene_memoria_cotizacion_util(previo):
        return None
    estado.estado_previo_pendiente = previo.a_diccionario_persistido()
    estado.intencion = "previa_encontrada"
    estado.registrar_log(
        "previous_conversation_found_by_contact",
        {"contacto": estado.contacto, "previous_session_id": previo.id_sesion},
    )
    return renderizar_respuesta_previa_encontrada(estado, previo)


# MEMORIA PERSISTENTE: maneja si el usuario quiere retomar o descartar una cotizacion recuperada.
def manejar_eleccion_previa_pendiente(mensaje_usuario: str, estado: EstadoCotizacion) -> tuple[str, EstadoCotizacion] | None:
    """Resuelve si el usuario quiere retomar lo previo o seguir con lo actual."""
    if not estado.estado_previo_pendiente:
        return None
    if contacto_actual_cambio_frente_a_previo_pendiente(estado):
        estado.registrar_log(
            "previous_conversation_discarded_by_new_contact",
            {
                "contacto_actual": estado.contacto,
                "contacto_previo": estado.estado_previo_pendiente.get("contacto"),
            },
        )
        estado.estado_previo_pendiente = None
        return None
    eleccion = detectar_eleccion_previa_usuario(mensaje_usuario)
    if eleccion == "retomar_previa":
        previo = EstadoCotizacion.desde_diccionario_persistido(estado.estado_previo_pendiente)
        retomado = QUOTE_MEMORY.hidratar(estado, previo)
        retomado.estado_previo_pendiente = None
        invalidar_cotizacion_recuperada_para_revalidar(retomado)
        retomado.campos_faltantes = encontrar_campos_faltantes(retomado)
        retomado.registrar_log("retomar_previa_despues_coincidencia_contacto", {"contacto": retomado.contacto})
        return renderizar_respuesta_previa_retomada(retomado), retomado
    if eleccion == "seguir_actual":
        estado.estado_previo_pendiente = None
        estado.campos_faltantes = encontrar_campos_faltantes(estado)
        respuesta = (
            "Perfecto, seguimos con la informacion nueva que me acabas de dar. "
            f"{pedir_campos_faltantes_para_estado(estado) if estado.campos_faltantes else renderizar_respuesta_revision_pedido(estado)}"
        )
        return respuesta, estado
    # Una pregunta de politica no es una respuesta a "retomar o seguir": se contesta con el RAG (ejecutar_decision_negocio)
    # y ahi mismo se recuerda que la eleccion sigue pendiente. Antes la compuerta repetia la pregunta y bloqueaba todo.
    if estado.intencion == "consulta_general":
        return None
    respuesta = (
        "Antes de avanzar, necesito que me confirmes una cosa: encontre una cotizacion previa asociada a ese contacto. "
        "Puedes decir `retomar la anterior` o `seguir con esta nueva`."
    )
    return respuesta, estado


# MEMORIA PERSISTENTE / GUARDRAIL CONTEXTUAL: detecta respuestas validas a la pregunta retomar vs continuar.
def detectar_eleccion_previa_usuario(mensaje_usuario: str) -> str | None:
    """Devuelve la eleccion del usuario cuando responde a una cotizacion previa pendiente."""
    texto = mensaje_usuario.lower()
    quiere_previa = any(
        termino in texto
        for termino in [
            "retomar",
            "anterior",
            "previa",
            "previo",
            "seguir con esa",
            "continua esa",
            "continúa esa",
        ]
    )
    quiere_actual = any(
        termino in texto
        for termino in [
            "nuevo",
            "nueva",
            "actual",
            "seguir con esta",
            "continua con esta",
            "continúa con esta",
        ]
    )
    if quiere_previa:
        return "retomar_previa"
    if quiere_actual:
        return "seguir_actual"
    return None


# GUARDRAIL DE MEMORIA: si cambia el telefono, se descarta la previa pendiente y se busca con el nuevo identificador.
def contacto_actual_cambio_frente_a_previo_pendiente(estado: EstadoCotizacion) -> bool:
    """Evita retener una cotizacion previa cuando el usuario entrega otro contacto."""
    if not estado.contacto or not estado.estado_previo_pendiente:
        return False
    contacto_previo = estado.estado_previo_pendiente.get("contacto")
    return bool(contacto_previo and contacto_previo != estado.contacto)


# MEMORIA TEMPORAL/PRODUCTOS: aplica agregar, quitar o reemplazar productos solicitados.
def aplicar_cambios_productos(estado: EstadoCotizacion, changes: dict[str, list[str]]) -> None:
    """Aplica cambios solicitados por el usuario sobre productos en curso."""
    had_blocking_product_issue = bool(estado.productos_sin_stock or estado.productos_solicitados_no_soportados)
    if had_blocking_product_issue and changes.get("replace_to") and (changes.get("remove") or changes.get("replace_from")):
        estado.cambio_producto_limpio_no_soportados = True
    for product in changes.get("replace_from", []):
        if product in estado.productos_solicitados:
            estado.productos_solicitados.remove(product)
        if product in estado.productos_sin_stock:
            estado.productos_sin_stock.remove(product)
            estado.cambio_producto_limpio_no_soportados = True
    for product in changes.get("remove", []):
        if product in estado.productos_solicitados:
            estado.productos_solicitados.remove(product)
        if product in estado.productos_sin_stock:
            estado.productos_sin_stock.remove(product)
            estado.cambio_producto_limpio_no_soportados = True
    for product in changes.get("replace_to", []) + changes.get("add", []):
        for shortage in list(estado.productos_sin_stock):
            if product in productos_similares_para(shortage) and shortage in estado.productos_solicitados:
                estado.productos_solicitados.remove(shortage)
                estado.productos_sin_stock.remove(shortage)
                estado.cambio_producto_limpio_no_soportados = True
        if product not in estado.productos_solicitados:
            estado.productos_solicitados.append(product)
        before = list(estado.productos_solicitados_no_soportados)
        estado.productos_solicitados_no_soportados = [
            unsupported
            for unsupported in estado.productos_solicitados_no_soportados
            if product not in productos_similares_para(unsupported)
        ]
        if before != estado.productos_solicitados_no_soportados:
            estado.cambio_producto_limpio_no_soportados = True
    if any(changes.values()):
        estado.cotizacion = None
        estado.opcion_recomendada = None
        estado.opciones_catalogo = []
        estado.opciones_validas = []
        estado.opciones_descartadas = []
        estado.dimensionamiento = None


# VALIDACION DE PRODUCTOS: decide si los productos nuevos deben sumarse al pedido actual.
def debe_fusionar_productos_solicitados(intencion: str | None, changes: dict) -> bool:
    """Evita reinsertar productos cuando el usuario esta quitando o reemplazando."""
    if intencion != "modificar_pedido":
        return True
    return bool(changes.get("add")) and not any(changes.get(key) for key in ["remove", "replace_from", "replace_to"])


# GUARDRAIL DE DECISION: aplica la accion validada del agente sobre la intencion del estado.
def aplicar_accion_agente_a_intencion(accion: str, estado: EstadoCotizacion, mensaje_usuario: str) -> None:
    """Convierte la decision del agente en una intencion ejecutable."""
    mapping = {
        "responder_precio": "consulta_precio",
        "generar_cotizacion": "cotizacion",
        "mostrar_imagen": "solicitud_imagen",
        "responder_politica": "consulta_general",
        "cierre": "cierre",
        "retomar_previa": "retomar_previa",
        "nueva_cotizacion": "recomendacion",
    }
    if accion == "derivacion":
        if es_solicitud_derivacion_explicita(mensaje_usuario):
            estado.intencion = "derivacion_humana"
        return
    if accion in mapping:
        estado.intencion = mapping[accion]
    elif accion == "pedir_campos_faltantes":
        estado.intencion = "recomendacion"
    elif accion == "validar_y_recomendar":
        estado.intencion = "recomendacion"


# VALIDACION DE MINIMOS: calcula que datos faltan antes de consultar tools de negocio.
def encontrar_campos_faltantes(estado: EstadoCotizacion) -> list[str]:
    """Calcula datos minimos faltantes antes de consultar tools de negocio."""
    missing = []
    for field in REQUIRED_FIELDS:
        value = getattr(estado, field)
        if value in (None, "", []):
            if field == "productos_solicitados" and estado.productos_solicitados_no_soportados:
                continue
            missing.append(field)
    return missing


# RESPUESTA GUIADA: genera una pregunta clara para completar los datos minimos faltantes.
def pedir_campos_faltantes(campos_faltantes: list[str]) -> str:
    """Construye una pregunta breve para pedir los campos faltantes."""
    labels = {
        "tipo_evento": "tipo de evento",
        "asistentes": "cantidad de asistentes",
        "fecha_evento": "fecha",
        "distrito": "distrito",
        "nombre_cliente": "nombre de la persona que cotiza",
        "contacto": "telefono celular para seguimiento",
        "productos_solicitados": "productos o servicios a cotizar, por ejemplo cerveza, vino, gaseosas, hielo, bartender o bar movil",
    }
    next_fields = priorizar_campos_faltantes(campos_faltantes)
    readable = [labels[field] for field in next_fields]
    if len(readable) == 1:
        return f"Perfecto, voy avanzando. Para continuar solo necesito confirmar **{readable[0]}**."
    return (
        "Perfecto, voy avanzando. Para seguir sin asumir datos, dime por favor: "
        + ", ".join(readable[:-1])
        + f" y {readable[-1]}."
    )


# VALIDACION DE MINIMOS: ordena los faltantes para pedir primero lo indispensable.
def priorizar_campos_faltantes(campos_faltantes: list[str]) -> list[str]:
    """Agrupa faltantes para no pedir demasiadas cosas en un solo turno."""
    priority_groups = [
        ["tipo_evento", "asistentes", "fecha_evento", "distrito"],
        ["nombre_cliente", "contacto"],
        ["productos_solicitados"],
    ]
    for group in priority_groups:
        selected = [field for field in group if field in campos_faltantes]
        if selected:
            return selected[:3]
    return campos_faltantes[:3]


# RESPUESTA GUIADA: decide si pedir datos generales o productos segun el estado actual.
def pedir_campos_faltantes_para_estado(estado: EstadoCotizacion) -> str:
    """Elige la pregunta adecuada segun el tipo de dato faltante."""
    if estado.campos_faltantes == ["fecha_evento"]:
        return mensaje_fecha_faltante(estado)
    if priorizar_campos_faltantes(estado.campos_faltantes) == ["productos_solicitados"]:
        return pedir_productos_con_catalogo(estado)
    respuesta = pedir_campos_faltantes(estado.campos_faltantes)
    if "fecha_evento" in estado.campos_faltantes and (estado.fecha_parcial.get("dia") or estado.fecha_parcial.get("mes")):
        respuesta += f" Sobre la fecha: {mensaje_fecha_faltante(estado)}"
    return respuesta


# TOOL CATALOGO: lista productos y servicios disponibles para que el usuario elija.
def pedir_productos_con_catalogo(estado: EstadoCotizacion) -> str:
    """Muestra opciones de catalogo cuando faltan productos/servicios."""
    catalog_result = buscar_catalogo(estado)
    estado.registrar_log(
        "catalog_options_for_product_selection",
        {
            "products": catalog_result["all_products"],
            "packages": paquetes_seleccionables_para_estado(estado),
        },
    )
    product_lines = "\n".join(
        f"- {product['name']} ({product['category']}): {product['currency']} {product['unit_price']:.2f} por {product['unit']}"
        for product in catalog_result["all_products"]
    )
    package_lines = "\n".join(
        f"- {package['name']} ({package['service']}): {package['currency']} {package['base_price']:.2f} base"
        for package in paquetes_seleccionables_para_estado(estado)
    )
    sections = []
    if product_lines:
        sections.append(f"Productos disponibles para elegir:\n{product_lines}")
    if package_lines:
        sections.append(f"Servicios/paquetes disponibles:\n{package_lines}")
    if not sections:
        return (
            "Ya tengo los datos principales, pero necesito saber que productos o servicios quieres cotizar. "
            "Puedes pedirme bebidas, hielo, bartender o bar movil, y validare contra el catalogo disponible."
        )
    return (
        "Ya tengo los datos principales. Para seguir, elige que productos o servicios quieres cotizar de este catalogo:\n\n"
        + "\n\n".join(sections)
        + "\n\nPuedes responder con una lista simple, por ejemplo: `cerveza, vino y hielo`."
    )


# TOOL CATALOGO: filtra paquetes compatibles con el estado de la cotizacion.
def paquetes_seleccionables_para_estado(estado: EstadoCotizacion) -> list[dict]:
    """Lista paquetes que tienen sentido para el evento y capacidad."""
    packages = []
    for package in CATALOG:
        if estado.tipo_evento and estado.tipo_evento not in package["event_types"]:
            continue
        if estado.asistentes and estado.asistentes > package["capacity_max"]:
            continue
        packages.append(package)
    return packages


# VALIDACION DE FECHA: explica si falta dia, mes o anio cuando la fecha esta incompleta.
def mensaje_fecha_faltante(estado: EstadoCotizacion) -> str:
    """Explica si falta dia, mes o toda la fecha."""
    dia = estado.fecha_parcial.get("dia")
    mes = estado.fecha_parcial.get("mes")
    if dia and not mes:
        return f"Ya tengo el dia {dia}, pero me falta el mes del evento."
    if mes and not dia:
        return f"Ya tengo el mes de {nombre_mes(mes)}, pero me falta el dia del evento."
    return "Para seguir necesito la fecha completa del evento, por ejemplo: `4 de diciembre`."


# VALIDACION DE FECHA: completa la fecha solo cuando hay dia, mes y anio suficientes.
def fusionar_fecha_parcial(estado: EstadoCotizacion, fecha_parcial: dict[str, int | None]) -> None:
    """Combina partes de fecha dadas en distintos turnos."""
    if (
        fecha_parcial.get("mes") is not None
        and fecha_parcial.get("dia") is None
        and estado.fecha_parcial.get("dia") == estado.asistentes
    ):
        estado.fecha_parcial["dia"] = None
    for key in ["dia", "mes", "anio"]:
        if fecha_parcial.get(key) is not None:
            estado.fecha_parcial[key] = fecha_parcial[key]
    if estado.fecha_parcial.get("dia") and estado.fecha_parcial.get("mes"):
        anio = estado.fecha_parcial.get("anio") or 2026
        dia = estado.fecha_parcial["dia"]
        mes = estado.fecha_parcial["mes"]
        try:
            estado.fecha_evento = date(anio, mes, dia).isoformat()
            estado.fecha_parcial = {"dia": None, "mes": None, "anio": None}
        except ValueError:
            estado.fecha_evento = None
            estado.errores_validacion_campos.append(f"La fecha indicada no es valida: {dia:02d}/{mes:02d}/{anio}.")


# GUARDRAIL DE FECHA: valida fechas ISO entregadas por reglas o por el extractor LLM antes de persistirlas.
def fecha_evento_es_valida(value: str) -> bool:
    """Confirma que la fecha venga en formato ISO y exista en el calendario."""
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


# DERIVACION HUMANA: ofrece WhatsApp solo como opcion, sin derivar hasta que el usuario lo pida.
def pedir_confirmacion_derivacion(estado: EstadoCotizacion) -> str:
    """Ofrece derivacion humana para casos que el flujo no puede resolver."""
    if estado.intencion == "solicitud_descuento":
        reason = "No puedo aprobar descuentos desde el flujo automatico."
    elif estado.intencion == "solicitud_pago":
        reason = "No puedo confirmar pagos ni reservas desde el flujo automatico."
    else:
        reason = "Esta solicitud requiere revision humana."
    return f"{reason} Si te parece, puedo dejar el caso listo para que un asesor lo continue por WhatsApp."


# HUMAN-IN-THE-LOOP: prepara el enlace WhatsApp simulado y lo guarda en el estado para seguimiento.
def preparar_derivacion_humana(estado: EstadoCotizacion, motivo: str) -> dict:
    """Crea un handoff simulado hacia un asesor humano por WhatsApp."""
    handoff = derivar_whatsapp(estado, reason=motivo)
    estado.derivacion_ofrecida = True
    estado.resumen_derivacion = handoff
    estado.registrar_log(
        "preparar_derivacion_humana",
        {"handoff_id": handoff["handoff_id"], "assigned_to": handoff["assigned_to"], "motivo": motivo},
    )
    return handoff


# RESPUESTA DE NEGOCIO: muestra recomendacion basada en catalogo, cobertura, stock y precios.
def renderizar_respuesta_recomendacion(estado: EstadoCotizacion) -> str:
    """Redacta la recomendacion validada antes de emitir cotizacion."""
    option = estado.opcion_recomendada or {}
    dimensionamiento = estado.dimensionamiento or {}
    items = ", ".join(
        f"{item['quantity']} {item['unit']} de {item['concept']}" for item in dimensionamiento.get("items", [])[:4]
    )
    reasons = "\n".join(f"- {reason}" for reason in option.get("reasons", []))
    checks = renderizar_resumen_validacion(estado)
    if option.get("origen") == "products":
        product_lines = "\n".join(
            f"- {item['quantity']} {item['unit']} de {item['concept']} ({item['product_name']})"
            for item in option.get("items", [])
        )
        return (
            f"Listo, {estado.nombre_cliente}. Revise paquetes, fecha y stock. No encontre un paquete disponible que calce completo, "
            f"pero si pude armar una propuesta con productos disponibles para tu {estado.tipo_evento} de {estado.asistentes} personas "
            f"en {estado.distrito} el {estado.fecha_evento}.\n\n"
            f"{checks}\n\n"
            f"Productos considerados:\n{product_lines}\n\n"
            "Si esta propuesta te parece bien, dime `genera la cotizacion` y la emito con estos productos."
        )
    return (
        f"Listo, {estado.nombre_cliente}. Ya consulte cobertura, catalogo y disponibilidad. "
        f"Con eso, la mejor opcion que encontre es **{option.get('name')}** para tu {estado.tipo_evento} de "
        f"{estado.asistentes} personas en {estado.distrito} el {estado.fecha_evento}.\n\n"
        f"{checks}\n\n"
        f"{reasons}\n\n"
        f"Dimensionamiento sugerido segun productos solicitados ({', '.join(estado.productos_solicitados)}): {items}.\n\n"
        "Si quieres que la deje como cotizacion formal, dime `genera la cotizacion`."
    )


# RESPUESTA DE COTIZACION: muestra el artefacto final y resumen economico de la cotizacion.
def renderizar_respuesta_cotizacion(estado: EstadoCotizacion) -> str:
    """Redacta el detalle de la cotizacion ya generada."""
    cotizacion = estado.cotizacion or {}
    option = estado.opcion_recomendada or {}
    handoff = estado.resumen_derivacion or {}
    conditions = "\n".join(f"- {condition}" for condition in cotizacion.get("conditions", []))
    details = "\n".join(
        f"- {item['quantity']} {item['unit']} x {item['concept']}: {cotizacion.get('currency')} {item['subtotal']:.2f}"
        for item in cotizacion.get("details", [])
    )
    bloque_asesor = ""
    if handoff.get("url"):
        bloque_asesor = (
            "\n\nContinuar venta con asesor humano:\n"
            f"- Canal: WhatsApp simulado\n"
            f"- Asesor: {handoff.get('assigned_to', 'Asesor humano 1')}\n"
            f"- Link: {handoff['url']}"
        )
    return (
        f"Listo, genere la cotizacion **{cotizacion.get('quote_id')}** para **{option.get('name')}**.\n"
        f"Cotizante: {estado.nombre_cliente} | Contacto seguimiento: {estado.contacto}\n\n"
        f"Detalle:\n{details}\n\n"
        f"- Subtotal: {cotizacion.get('currency')} {cotizacion.get('subtotal'):.2f}\n"
        f"- IGV: {cotizacion.get('currency')} {cotizacion.get('taxes'):.2f}\n"
        f"- Total: **{cotizacion.get('currency')} {cotizacion.get('total'):.2f}**\n"
        f"- Vigencia: {cotizacion.get('valid_until')}\n\n"
        f"{renderizar_resumen_validacion(estado)}\n\n"
        f"Condiciones:\n{conditions}"
        f"{bloque_asesor}"
    )


# RESPUESTA INFORMATIVA: responde precios puntuales sin modificar la cotizacion en curso.
def renderizar_respuesta_consulta_precio(mensaje_usuario: str, estado: EstadoCotizacion) -> str:
    """Responde precios informativos sin generar cotizacion."""
    product_matches = buscar_coincidencias_precio(mensaje_usuario)
    if product_matches:
        lines = "\n".join(
            f"- {item['name']}: {item['currency']} {item['unit_price']:.2f} por {item['unit']}"
            for item in product_matches
        )
        return (
            "Claro. Este es el precio informativo, sin generar cotizacion ni reservar stock:\n\n"
            f"{lines}\n\n"
            "Si quieres que lo incluya en una cotizacion, dime `genera la cotizacion` y primero validare los datos necesarios."
        )

    if estado.opcion_recomendada:
        if estado.opcion_recomendada.get("origen") == "products":
            subtotal = round(sum(item["subtotal"] for item in estado.opcion_recomendada["items"]), 2)
            taxes = round(subtotal * 0.18, 2)
            total = round(subtotal + taxes, 2)
            return (
                "Claro. Este es el costo informativo de la propuesta por productos, sin generar cotizacion todavia:\n\n"
                f"- Subtotal: PEN {subtotal:.2f}\n"
                f"- IGV referencial: PEN {taxes:.2f}\n"
                f"- Total referencial: PEN {total:.2f}\n\n"
                "Si confirmas que quieres emitirla, dime `genera la cotizacion`."
            )
        base_price = estado.opcion_recomendada["base_price"]
        taxes = round(base_price * 0.18, 2)
        total = round(base_price + taxes, 2)
        return (
            f"Claro. Este es el costo informativo de **{estado.opcion_recomendada['name']}**, sin generar cotizacion todavia:\n\n"
            f"- Precio base: {estado.opcion_recomendada['currency']} {base_price:.2f}\n"
            f"- IGV referencial: {estado.opcion_recomendada['currency']} {taxes:.2f}\n"
            f"- Total referencial: {estado.opcion_recomendada['currency']} {total:.2f}\n\n"
            "Si confirmas que quieres emitirla, dime `genera la cotizacion`."
        )

    package_matches = buscar_coincidencias_precio_paquete(mensaje_usuario)
    if package_matches:
        lines = "\n".join(
            f"- {item['name']}: {item['currency']} {item['base_price']:.2f} precio base"
            for item in package_matches
        )
        return (
            "Claro. Este es el precio informativo del paquete, sin validar disponibilidad ni generar cotizacion:\n\n"
            f"{lines}\n\n"
            "Para cotizarlo necesito validar evento, fecha, distrito, datos de contacto, preferencias y stock."
        )

    return (
        "Puedo ayudarte con el precio informativo si me dices el producto o paquete, por ejemplo cerveza, vino, gaseosa, hielo, bartender o bar movil. "
        "Para generar una cotizacion, primero validare datos, cobertura y disponibilidad."
    )


# RESPUESTA DE VALIDACION: resume que tools de negocio fueron consultadas y que resultado dieron.
def renderizar_resumen_validacion(estado: EstadoCotizacion) -> str:
    """Resume cobertura, catalogo y disponibilidad consultados."""
    package_count = len(estado.opciones_catalogo)
    available_package_count = len(estado.opciones_validas)
    if estado.opcion_recomendada and estado.opcion_recomendada.get("origen") == "products":
        product_count = len(estado.opcion_recomendada.get("items", []))
        origen = "cotizacion armada desde productos disponibles por falta de paquete calzante."
        availability_line = f"- Stock de productos consultado para {estado.fecha_evento}: {product_count} producto(s)/servicio(s) disponible(s)."
    else:
        origen = "paquete disponible validado."
        availability_line = f"- Disponibilidad consultada para {estado.fecha_evento}: {available_package_count} paquete(s) disponible(s)."
    return (
        "Validaciones realizadas:\n"
        f"- Cobertura consultada para {estado.distrito}: {'OK' if estado.cobertura_ok else 'No disponible'}.\n"
        f"- Catalogo consultado: {package_count} paquete(s) calzante(s) por ocasion/capacidad.\n"
        f"{availability_line}\n"
        f"- Fuente de propuesta: {origen}"
    )


# TOOL PRECIOS: encuentra productos del catalogo mencionados en una consulta de precio.
def buscar_coincidencias_precio(mensaje_usuario: str) -> list[dict]:
    """Busca productos mencionados para responder precio unitario."""
    texto = mensaje_usuario.lower()
    tokens = [token.strip(".,;:!?¿¡") for token in texto.split()]
    matches = []
    for product in PRODUCTS:
        haystack = f"{product['name']} {product['category']}".lower()
        if any(token in haystack for token in tokens if len(token) > 3):
            matches.append(product)
    return matches


# TOOL PRECIOS: encuentra paquetes del catalogo mencionados en una consulta de precio.
def buscar_coincidencias_precio_paquete(mensaje_usuario: str) -> list[dict]:
    """Busca paquetes mencionados para responder precio base."""
    texto = mensaje_usuario.lower()
    tokens = [token.strip(".,;:!?¿¡") for token in texto.split()]
    matches = []
    for package in CATALOG:
        haystack = f"{package['name']} {package['service']}".lower()
        if any(token in haystack for token in tokens if len(token) > 3):
            matches.append(package)
    return matches


# RESPUESTA DE STOCK: informa faltantes y alternativas sin reemplazar productos automaticamente.
def renderizar_respuesta_sin_stock(estado: EstadoCotizacion, stock_result: dict) -> str:
    """Informa faltantes de stock y alternativas sin reemplazar automaticamente."""
    missing_lines = []
    for item in stock_result["missing_items"]:
        line = f"- {item['concept']}: solicitado {item['quantity']} {item['unit']}, stock {item.get('stock', 0)}"
        alternatives = item.get("alternatives", [])
        if alternatives:
            alternative_text = ", ".join(
                f"{alternative['product']['name']} ({alternative['stock']} disponibles)"
                for alternative in alternatives
            )
            line += f". Alternativas parecidas con stock: {alternative_text}"
        else:
            line += ". No encontre alternativa parecida con stock."
        missing_lines.append(line)
    missing = "\n".join(missing_lines)
    return (
        "Revise cobertura, catalogo, disponibilidad y stock, pero no tengo todo lo necesario para cotizar con seguridad.\n\n"
        f"Faltantes:\n{missing}\n\n"
        "No voy a reemplazar productos sin tu confirmacion. Dime si quieres cambiar alguno por una alternativa disponible."
    )


# RESPUESTA DE COBERTURA: informa que el distrito esta fuera de alcance y lista distritos disponibles.
def renderizar_respuesta_sin_cobertura(estado: EstadoCotizacion, coverage: dict) -> str:
    """Explica la falta de cobertura sin seguir pidiendo el mismo distrito."""
    estado.derivacion_ofrecida = False
    distritos_cubiertos = ", ".join(coverage.get("distritos_cubiertos", []))
    return (
        f"No tengo cobertura para **{estado.distrito}**. "
        f"El distrito **{estado.distrito}** no esta dentro del alcance de cobertura, "
        "por eso no puedo generar la cotizacion con ese distrito. "
        f"Por ahora puedo cubrir: {distritos_cubiertos}. "
        "Si quieres, dime uno de esos distritos y continuo con la cotizacion."
    )


# RESPUESTA DE CALENDARIO: informa cruce de agenda antes de consultar catalogo o cotizar.
def renderizar_respuesta_fecha_ocupada(estado: EstadoCotizacion, calendario: dict) -> str:
    """Explica que la fecha/distrito ya tiene una reserva registrada."""
    estado.derivacion_ofrecida = False
    return (
        f"La fecha **{estado.fecha_evento}** para **{estado.distrito}** ya tiene una reserva registrada, "
        "por eso no puedo avanzar con una cotizacion que cruce agenda. "
        "Dime otra fecha o cambia el distrito y vuelvo a validar disponibilidad."
    )


# GUARDRAIL DE CAMPOS: informa datos invalidos antes de pedir faltantes o consultar tools de negocio.
def renderizar_respuesta_validacion_campos(estado: EstadoCotizacion) -> str:
    """Explica errores de campos como fechas imposibles sin avanzar con datos invalidos."""
    errores = "\n".join(f"- {error}" for error in estado.errores_validacion_campos)
    if any("fecha" in error.lower() for error in estado.errores_validacion_campos):
        return (
            "Necesito corregir un dato antes de avanzar:\n\n"
            f"{errores}\n\n"
            "Por favor indicame una fecha real del evento, por ejemplo `15 de diciembre de 2026`."
        )
    return (
        "Necesito corregir un dato antes de avanzar:\n\n"
        f"{errores}\n\n"
        "Enviame el dato corregido y continuo con la cotizacion."
    )


# TOOL RECOMENDACION: arma una opcion cotizable usando productos disponibles validados.
def construir_opcion_basada_en_productos(estado: EstadoCotizacion, available_items: list[dict], similar_packages: list[dict]) -> dict:
    """Construye una opcion personalizada usando productos con stock."""
    quote_items = []
    for item in available_items:
        product = item["product"]
        subtotal = round(item["quantity"] * product["unit_price"], 2)
        quote_items.append(
            {
                "concept": item["concept"],
                "product_id": product["id"],
                "product_name": product["name"],
                "quantity": item["quantity"],
                "unit": item["unit"],
                "unit_price": product["unit_price"],
                "subtotal": subtotal,
            }
    )
    reasons = [
        "No habia paquete disponible que calce completo para la solicitud.",
        "Se usaron productos con stock suficiente para la fecha.",
    ]
    if similar_packages:
        reasons.append(f"Paquete parecido encontrado pero descartado: {similar_packages[0]['name']} ({similar_packages[0]['discard_reason']})")
    return {
        "id": "CUSTOM-PRODUCTS-001",
        "name": "Cotizacion por productos disponibles",
        "origen": "products",
        "currency": "PEN",
        "items": quote_items,
        "reasons": reasons,
        "image": "app/data/assets/pack_celebracion_esencial.svg",
    }


# RESPUESTA MULTIMODAL: muestra imagen solo si ya existe cotizacion y el usuario la solicita.
def renderizar_respuesta_solicitud_imagen(estado: EstadoCotizacion) -> str:
    """Permite mostrar imagen referencial solo despues de cotizar."""
    if not estado.cotizacion or not estado.opcion_recomendada:
        estado.imagen_solicitada = False
        return "Puedo mostrar una imagen referencial despues de generar una cotizacion. Primero completemos la cotizacion para no mostrarte una opcion que aun no esta validada."
    estado.imagen_solicitada = True
    return "Listo. Muestro una imagen referencial del paquete cotizado debajo del chat."


# RESPUESTA DE CIERRE: cierra la conversacion cuando el usuario ya no requiere mas acciones.
def renderizar_respuesta_cierre(estado: EstadoCotizacion) -> str:
    """Cierra la conversacion indicando si quedo cotizacion asociada."""
    if estado.cotizacion:
        return (
            f"Perfecto, cierro la conversacion dejando la cotizacion {estado.cotizacion['quote_id']} asociada a "
            f"{estado.nombre_cliente} ({estado.contacto}) para seguimiento. Puedes reiniciar desde el boton lateral."
        )
    return "Perfecto, cierro la conversacion sin cotizacion generada. Puedes reiniciar desde el boton lateral para empezar otra solicitud."


# RESPUESTA DE MEMORIA: muestra al usuario que datos estan guardados en memoria temporal.
def renderizar_respuesta_consulta_memoria(estado: EstadoCotizacion) -> str:
    """Responde reclamos o consultas sobre datos ya capturados."""
    if estado.nombre_cliente:
        estado.campos_faltantes = encontrar_campos_faltantes(estado)
        if estado.campos_faltantes:
            return (
                f"Tienes razon, ya tengo tu nombre: **{estado.nombre_cliente}**. "
                f"Me falta esto para avanzar: {', '.join(_etiquetas_campos_faltantes(estado.campos_faltantes))}."
            )
        return f"Tienes razon, ya tengo tu nombre: **{estado.nombre_cliente}**. Con eso ya puedo continuar."
    return (
        "Tienes razon en reclamarlo; no logre identificar el nombre en el mensaje anterior. "
        "Puedes escribirlo como: `Soy Nombre Apellido`."
    )


# MEMORIA PERSISTENTE: solicita contacto o recupera cotizacion anterior segun identificador disponible.
def manejar_retomar_previa(estado: EstadoCotizacion) -> tuple[str, EstadoCotizacion]:
    """Retoma una cotizacion previa si el usuario confirma identidad."""
    if not estado.contacto:
        estado.campos_faltantes = ["contacto"]
        return (
            "Claro, puedo intentar buscar lo que quedo guardado de una cotizacion anterior. "
            "Para ubicarla, dime por favor el telefono celular que usaste en esa conversacion.",
            estado,
        )

    # MEMORIA PERSISTENTE: consulta PostgreSQL/NoSQL para recuperar la cotizacion anterior del cliente.
    previo = QUOTE_MEMORY.buscar_por_contacto(estado.contacto)
    if not previo or not tiene_memoria_cotizacion_util(previo):
        estado.campos_faltantes = encontrar_campos_faltantes(estado)
        return (
            f"No encontre una cotizacion anterior asociada al contacto **{estado.contacto}**. "
            "Empecemos una nueva cotizacion con ese contacto: cuentame el tipo de evento, cantidad de asistentes y fecha.",
            estado,
        )

    retomado = QUOTE_MEMORY.hidratar(estado, previo)
    invalidar_cotizacion_recuperada_para_revalidar(retomado)
    retomado.registrar_log(
        "retomar_conversacion_previa",
        {"nombre_cliente": retomado.nombre_cliente, "contacto": retomado.contacto, "id_sesion_retomada": previo.id_sesion},
    )
    # MEMORIA PERSISTENTE: despues de recuperar por identidad, esta cotizacion se hidrata en el session_id actual.
    retomado.campos_faltantes = encontrar_campos_faltantes(retomado)
    respuesta = (
        f"Listo, retome la ultima cotizacion que tenia para **{retomado.nombre_cliente}** "
        f"con contacto **{retomado.contacto}**.\n\n"
        f"{renderizar_respuesta_revision_pedido(retomado)}"
    )
    return respuesta, retomado


# GUARDRAIL DE CALENDARIO: al retomar una cotizacion previa, obliga a recalcular antes de mostrar totales.
def invalidar_cotizacion_recuperada_para_revalidar(estado: EstadoCotizacion) -> None:
    """Conserva datos retomados, pero borra cotizacion/imagen para revalidar calendario y disponibilidad."""
    if not estado.cotizacion and not estado.imagen_artefacto_cotizacion:
        return
    estado.registrar_log(
        "cotizacion_recuperada_invalidada_para_revalidar",
        {
            "quote_id_previo": (estado.cotizacion or {}).get("quote_id"),
            "fecha_evento": estado.fecha_evento,
            "distrito": estado.distrito,
        },
    )
    estado.cotizacion = None
    estado.imagen_artefacto_cotizacion = None
    estado.calendario_ok = None
    estado.disponibilidad_ok = None


# VALIDACION DE MEMORIA: verifica si una cotizacion recuperada tiene datos suficientes para retomarse.
def tiene_memoria_cotizacion_util(estado: EstadoCotizacion) -> bool:
    """Evita tratar registros vacios o solo-contacto como cotizaciones previas."""
    datos_evento = [estado.tipo_evento, estado.asistentes, estado.fecha_evento, estado.distrito]
    return bool(
        estado.cotizacion
        or estado.opcion_recomendada
        or estado.productos_solicitados
        or (estado.nombre_cliente and sum(value not in (None, "", []) for value in datos_evento) >= 2)
    )


# RESPUESTA DE MEMORIA: presenta una cotizacion previa encontrada antes de retomarla.
def renderizar_respuesta_previa_encontrada(estado: EstadoCotizacion, previo: EstadoCotizacion) -> str:
    """Compara datos actuales y previos antes de avanzar."""
    return (
        f"Encontre una cotizacion previa asociada al contacto **{estado.contacto}**. "
        "Antes de pedirte mas datos, confirmemos si quieres retomarla o seguir con lo nuevo.\n\n"
        f"Datos que acabas de dar:\n{renderizar_resumen_pedido_compacto(estado)}\n\n"
        f"Cotizacion previa encontrada:\n{renderizar_resumen_pedido_compacto(previo)}\n\n"
        "Dime `retomar la anterior` para continuar desde lo guardado, o `seguir con esta nueva` para usar los datos actuales."
    )


# RESPUESTA DE MEMORIA: confirma que la cotizacion previa fue cargada al estado actual.
def renderizar_respuesta_previa_retomada(estado: EstadoCotizacion) -> str:
    """Confirma que se cargo la cotizacion previa en la sesion actual."""
    return (
        f"Listo, retome los datos de la cotizacion previa asociada al contacto **{estado.contacto}**. "
        "Antes de emitir una nueva cotizacion voy a volver a validar calendario, cobertura, catalogo y stock.\n\n"
        f"{renderizar_respuesta_revision_pedido(estado)}"
    )


# RESPUESTA DE MEMORIA: resume datos principales del pedido en formato corto.
def renderizar_resumen_pedido_compacto(estado: EstadoCotizacion) -> str:
    """Resume una solicitud para comparar memoria previa contra datos actuales."""
    products = ", ".join(estado.productos_solicitados) if estado.productos_solicitados else "pendiente"
    return (
        f"- Evento: {estado.tipo_evento or 'pendiente'}\n"
        f"- Asistentes: {estado.asistentes or 'pendiente'}\n"
        f"- Fecha: {estado.fecha_evento or 'pendiente'}\n"
        f"- Distrito: {estado.distrito or 'pendiente'}\n"
        f"- Cotizante: {estado.nombre_cliente or 'pendiente'}\n"
        f"- Contacto: {estado.contacto or 'pendiente'}\n"
        f"- Productos/servicios: {products}"
    )


# RESPUESTA DE REVISION: permite revisar o modificar el pedido antes de cotizar.
def renderizar_respuesta_revision_pedido(estado: EstadoCotizacion) -> str:
    """Muestra el pedido actual y ejemplos para modificarlo."""
    products = ", ".join(estado.productos_solicitados) if estado.productos_solicitados else "sin productos/servicios elegidos todavia"
    event_date_text = estado.fecha_evento
    if not event_date_text and (estado.fecha_parcial.get("dia") or estado.fecha_parcial.get("mes")):
        event_date_text = texto_fecha_parcial(estado)
    unsupported = (
        f"\n- Pendientes/no disponibles: {', '.join(estado.productos_solicitados_no_soportados)}"
        if estado.productos_solicitados_no_soportados
        else ""
    )
    return (
        "Claro, revisemos el pedido actual antes de cotizar:\n\n"
        f"- Evento: {estado.tipo_evento or 'pendiente'}\n"
        f"- Asistentes: {estado.asistentes or 'pendiente'}\n"
        f"- Fecha: {event_date_text or 'pendiente'}\n"
        f"- Distrito: {estado.distrito or 'pendiente'}\n"
        f"- Cotizante: {estado.nombre_cliente or 'pendiente'}\n"
        f"- Contacto: {estado.contacto or 'pendiente'}\n"
        f"- Productos/servicios: {products}"
        f"{unsupported}\n\n"
        "Puedes decirme, por ejemplo: `quitar vino`, `agregar hielo`, `cambiar cerveza por agua` o `genera la cotizacion` si ya esta conforme."
    )


# RESPUESTA CONVERSACIONAL: saluda y orienta sin asumir datos de cotizacion.
def renderizar_respuesta_saludo(estado: EstadoCotizacion) -> str:
    """Saluda y abre la recoleccion inicial de datos."""
    return (
        "Hola, estoy bien y listo para ayudarte con la cotizacion de tu evento. "
        "Para empezar sin asumir nada, cuentame que tipo de evento tienes, para cuantas personas y en que fecha seria."
    )


# RESPUESTA DERIVACION HUMANA: arma enlace de WhatsApp cuando el usuario lo solicito.
def renderizar_respuesta_derivacion(handoff: dict) -> str:
    """Redacta la derivacion preparada para WhatsApp."""
    summary = handoff["summary"]
    return (
        "Listo, deje preparada una derivacion por WhatsApp.\n\n"
        f"- ID: {handoff['handoff_id']}\n"
        f"- Canal: WhatsApp simulado\n"
        f"- Asesor: {handoff.get('assigned_to', 'Asesor humano 1')}\n"
        f"- Motivo: {summary['reason']}\n"
        f"- Link: {handoff['url']}\n\n"
        "El resumen para el asesor queda disponible en el panel lateral."
    )


# TOOL RAG: responde politicas o conocimiento de negocio desde el RAG real en Supabase.
def renderizar_respuesta_rag(query: str, estado: EstadoCotizacion | None = None) -> str:
    """Responde consultas de politica con el RAG (con respaldo local) sin perder el hilo de la cotizacion."""
    respuesta = buscar_rag(query)
    if estado is not None:
        estado.registrar_log("rag_consulta_politica", {"pregunta": query[:120]})
        if estado.estado_previo_pendiente:
            respuesta += (
                "\n\nSigue pendiente: encontre una cotizacion previa con ese contacto. "
                "Dime `retomar la anterior` o `seguir con esta nueva`."
            )
    return respuesta

    # RAG LOCAL (desactivado):
    # resultado = buscar_rag(query)
    # if not resultado["matches"]:
    #     return "No encontre una politica relacionada. Solo tengo anticipacion, feriados y descuentos."
    # lines = [f"- **{doc['title']}**: {doc['texto']}" for doc in resultado["matches"]]
    # return "Segun el RAG local:\n\n" + "\n".join(lines)


# VALIDACION DE INTENCION: detecta confirmaciones explicitas para generar cotizacion.
def _parece_confirmacion_cotizacion(message: str) -> bool:
    """Detecta confirmaciones cortas para emitir cotizacion."""
    texto = message.lower()
    return any(term in texto for term in ["si cotiza", "sí cotiza", "cotizalo", "cotízalo", "genera la cotizacion", "genera la cotización"])


# SALIDA DEL WORKFLOW: centraliza el retorno de respuesta, estado y etapa.
def _finalizar(respuesta: str, estado: EstadoCotizacion, etapa: str) -> tuple[str, EstadoCotizacion]:
    """Aplica pulido LLM, agrega memoria visible, guarda estado y retorna."""
    estado.etapa = etapa
    respuesta_pulida = pulir_respuesta(respuesta, estado)
    respuesta_con_memoria = f"{respuesta_pulida}\n\n{renderizar_memoria_temporal(estado)}"
    estado.mensajes.append({"role": "assistant", "content": respuesta_con_memoria})
    estado.registrar_log("respuesta", {"etapa": etapa, "content": respuesta_con_memoria})
    if not estado.estado_previo_pendiente:
        # MEMORIA PERSISTENTE: guarda el estado para retomar la cotizacion despues.
        QUOTE_MEMORY.guardar(estado)
    ACTIVE_SESSIONS.guardar(estado)
    return respuesta_con_memoria, estado


# UI/MEMORIA TEMPORAL: muestra sutilmente que datos entiende y conserva el agente.
def renderizar_memoria_temporal(estado: EstadoCotizacion) -> str:
    """Genera el resumen sutil de memoria mostrado bajo cada respuesta."""
    captured = []
    if estado.nombre_cliente:
        captured.append(f"cotizante: {estado.nombre_cliente}")
    if estado.contacto:
        captured.append(f"contacto: {estado.contacto}")
    if estado.tipo_evento:
        captured.append(f"evento: {estado.tipo_evento}")
    if estado.asistentes:
        captured.append(f"asistentes: {estado.asistentes}")
    if estado.fecha_evento:
        captured.append(f"fecha: {estado.fecha_evento}")
    elif estado.fecha_parcial.get("dia") or estado.fecha_parcial.get("mes"):
        captured.append(f"fecha parcial: {texto_fecha_parcial(estado)}")
    if estado.distrito:
        captured.append(f"distrito: {estado.distrito}")
    if estado.productos_solicitados:
        captured.append(f"productos/servicios: {', '.join(estado.productos_solicitados)}")
    if estado.productos_solicitados_no_soportados:
        captured.append(f"productos no disponibles: {', '.join(estado.productos_solicitados_no_soportados)}")
    if estado.preferencias:
        captured.append(f"preferencias: {', '.join(estado.preferencias)}")

    captured_text = "; ".join(captured) if captured else "sin datos capturados todavia"
    if estado.intencion == "derivacion_humana":
        return f"_Tengo en memoria: {captured_text}. Derivacion humana preparada por WhatsApp._"
    if estado.intencion == "retomar_previa" and not estado.contacto:
        return f"_Tengo en memoria: {captured_text}. Siguiente por confirmar: telefono celular para buscar la cotizacion anterior._"
    missing = encontrar_campos_faltantes(estado)
    if missing:
        next_missing = priorizar_campos_faltantes(missing)
        missing_text = ", ".join(_etiquetas_campos_faltantes(next_missing))
        return f"_Tengo en memoria: {captured_text}. Siguiente por confirmar: {missing_text}._"
    return f"_Memoria temporal: {captured_text}. Datos minimos completos para continuar._"


# UI/VALIDACION DE FECHA: convierte fecha incompleta en texto entendible para el usuario.
def texto_fecha_parcial(estado: EstadoCotizacion) -> str:
    """Convierte una fecha parcial en texto legible."""
    dia = estado.fecha_parcial.get("dia")
    mes = estado.fecha_parcial.get("mes")
    if dia and mes:
        return f"{dia} de {nombre_mes(mes)}"
    if dia:
        return f"dia {dia}, falta mes"
    if mes:
        return f"{nombre_mes(mes)}, falta dia"
    return "incompleta"


# UTILIDAD DE FECHA: traduce numero de mes a nombre en espanol.
def nombre_mes(mes: int) -> str:
    """Devuelve el nombre en espanol de un numero de mes."""
    names = {
        1: "enero",
        2: "febrero",
        3: "marzo",
        4: "abril",
        5: "mayo",
        6: "junio",
        7: "julio",
        8: "agosto",
        9: "septiembre",
        10: "octubre",
        11: "noviembre",
        12: "diciembre",
    }
    return names.get(mes, f"mes {mes}")


# UI/VALIDACION DE MINIMOS: convierte campos internos faltantes en etiquetas legibles.
def _etiquetas_campos_faltantes(campos_faltantes: list[str]) -> list[str]:
    """Traduce nombres internos de campos a etiquetas para el usuario."""
    labels = {
        "tipo_evento": "tipo de evento",
        "asistentes": "cantidad de asistentes",
        "fecha_evento": "fecha",
        "distrito": "distrito",
        "nombre_cliente": "nombre de la persona que cotiza",
        "contacto": "telefono celular para seguimiento",
        "productos_solicitados": "productos o servicios a cotizar",
    }
    return [labels[field] for field in campos_faltantes]


# RESPUESTA DE CATALOGO: informa productos no encontrados y sugiere alternativas parecidas.
def renderizar_respuesta_productos_no_soportados(estado: EstadoCotizacion) -> str:
    """Explica productos no soportados y alternativas conocidas."""
    lines = []
    for product in estado.productos_solicitados_no_soportados:
        suggestions = productos_similares_para(product)
        if suggestions:
            lines.append(f"- {product}: no lo tengo en catalogo. Parecido disponible: {', '.join(suggestions)}.")
        else:
            lines.append(f"- {product}: no lo tengo en catalogo y no encontre un sustituto parecido.")

    available_requested = ""
    if estado.productos_solicitados:
        available_requested = f"\n\nSi mantenemos lo disponible, por ahora tengo: {', '.join(estado.productos_solicitados)}."

    return (
        "Antes de cotizar, revise lo que pediste contra el catalogo y hay productos que no tengo exactamente:\n\n"
        + "\n".join(lines)
        + available_requested
        + "\n\nDime si quieres reemplazarlo por alguna alternativa disponible o si prefieres cambiar la lista de productos."
    )


# TOOL CATALOGO: busca productos alternativos por categoria cuando no existe el pedido exacto.
def productos_similares_para(product: str) -> list[str]:
    """Devuelve alternativas simples para productos no soportados."""
    suggestions = {
        "whisky": ["ron", "vino", "cerveza"],
        "ron": ["cerveza", "vino"],
        "pisco": ["vino"],
        "champagne": ["vino"],
        "tequila": ["ron", "vino", "cerveza"],
        "vodka": ["ron", "vino", "cerveza"],
        "gin": ["ron", "vino", "cerveza"],
        "agua": ["gaseosa", "hielo"],
        "jugo": ["gaseosa"],
        "torta": [],
        "comida": [],
        "snacks": [],
    }
    return suggestions.get(product, [])
