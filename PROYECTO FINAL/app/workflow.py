from __future__ import annotations

from datetime import date

from app.state import QuoteState
from app.data.mock_data import CATALOG, PRODUCTS
from app.agentic_decider import decidir_siguiente_accion_con_agente, obtener_disponibilidad_tools, es_solicitud_derivacion_explicita
from app.artifacts import generar_artefacto_visual_cotizacion
from app.guardrails.decision import validar_decision_agentica
from app.llm import pulir_respuesta
from app.repositories import ActiveSessionRepository, QuoteMemoryRepository
from app.tools.availability import mock_validar_disponibilidad, mock_validar_stock_productos
from app.tools.catalog import mock_buscar_catalogo
from app.tools.coverage import mock_validar_cobertura
from app.tools.dimensioning import mock_dimensionar_evento
from app.tools.extraction import extraer_intencion_y_campos
from app.tools.handoff import mock_derivar_whatsapp
from app.tools.pricing import mock_comparar_opciones, mock_generar_cotizacion
from app.tools.rag import mock_buscar_rag


REQUIRED_FIELDS = ["event_type", "attendees", "event_date", "district", "customer_name", "contact", "requested_products"]
ACTIVE_SESSIONS = ActiveSessionRepository()
QUOTE_MEMORY = QuoteMemoryRepository()


# Ejecuta la responsabilidad de manejar mensaje.
def manejar_mensaje(user_message: str, state: QuoteState) -> tuple[str, QuoteState]:
    """Orquesta el turno usando el grafo LangGraph del cotizador."""
    from app.grafo_cotizador import ejecutar_grafo_cotizador

    return ejecutar_grafo_cotizador(user_message, state)


# Ejecuta la responsabilidad de preparar turno usuario.
def preparar_turno_usuario(user_message: str, state: QuoteState) -> QuoteState:
    """Registra el mensaje, extrae intencion/campos y actualiza memoria operativa."""
    state.messages.append({"role": "user", "content": user_message})
    extraction = extraer_intencion_y_campos(user_message, state)
    state.registrar_log("extraer_intencion_y_campos", extraction)
    fusionar_extraccion_en_estado(state, extraction)
    state.missing_fields = encontrar_campos_faltantes(state)
    state.registrar_log("tool_readiness", obtener_disponibilidad_tools(user_message, state))
    return state


# Ejecuta la responsabilidad de resolver memoria antes del negocio.
def resolver_memoria_y_elecciones_previas(user_message: str, state: QuoteState) -> tuple[str, QuoteState, str] | None:
    """Resuelve recuperacion de memoria o eleccion pendiente antes de llamar tools."""
    pending_response = manejar_eleccion_previa_pendiente(user_message, state)
    if pending_response:
        response, state = pending_response
        return response, state, state.stage

    previous_response = detectar_conversacion_previa_por_contacto(state)
    if previous_response:
        return previous_response, state, "validacion_memoria"
    return None


# Ejecuta la responsabilidad de decidir accion agentica turno.
def decidir_accion_agentica_turno(user_message: str, state: QuoteState) -> QuoteState:
    """Usa create_agent para decidir accion de alto nivel cuando corresponde."""
    agent_action = decidir_siguiente_accion_con_agente(user_message, state)
    if agent_action:
        state.registrar_log("create_agent_decision", {"action": agent_action})
    accion_validada = validar_decision_agentica(agent_action, user_message, state)
    if accion_validada:
        aplicar_accion_agente_a_intencion(accion_validada, state, user_message)
    return state


# Ejecuta la responsabilidad de ejecutar decision negocio.
def ejecutar_decision_negocio(user_message: str, state: QuoteState) -> tuple[str, QuoteState, str]:
    """Ejecuta las tools mock y reglas de negocio segun el estado/intencion."""
    if state.intent == "image_request":
        response = renderizar_respuesta_solicitud_imagen(state)
        return response, state, "imagen"

    if state.intent == "close":
        response = renderizar_respuesta_cierre(state)
        return response, state, "cierre"

    if state.intent == "memory_check":
        response = renderizar_respuesta_consulta_memoria(state)
        return response, state, "memoria"

    if state.intent == "resume_previous":
        response, state = manejar_retomar_previa(state)
        return response, state, "memoria_previa"

    if state.intent == "greeting":
        response = renderizar_respuesta_saludo(state)
        return response, state, "saludo"

    if state.intent == "review_order":
        response = renderizar_respuesta_revision_pedido(state)
        return response, state, "revision_pedido"

    if state.intent == "general_question":
        response = renderizar_respuesta_rag(user_message)
        return response, state, "politica"

    if state.intent == "price_query":
        response = renderizar_respuesta_consulta_precio(user_message, state)
        return response, state, "consulta_precio"

    if state.intent == "human_handoff":
        state.handoff_confirmed = True
        handoff = mock_derivar_whatsapp(state, reason="Solicitud explicita del usuario.")
        state.handoff_summary = handoff
        response = renderizar_respuesta_derivacion(handoff)
        return response, state, "derivacion"

    if state.intent in {"discount_request", "payment_request"}:
        state.handoff_offered = True
        response = pedir_confirmacion_derivacion(state)
        return response, state, "derivacion_ofrecida"

    if state.intent == "modify_request":
        response = renderizar_respuesta_revision_pedido(state)
        if not state.product_change_cleared_unsupported:
            return response, state, "pedido_modificado"

    if state.intent == "handoff_confirmation" and state.handoff_offered:
        state.handoff_confirmed = True
        handoff = mock_derivar_whatsapp(state, reason="Usuario acepta derivacion por WhatsApp.")
        state.handoff_summary = handoff
        response = renderizar_respuesta_derivacion(handoff)
        return response, state, "derivacion"

    state.registrar_log("encontrar_campos_faltantes", {"missing_fields": state.missing_fields})
    if state.missing_fields:
        response = pedir_campos_faltantes_para_estado(state)
        return response, state, "recoleccion"

    if state.unsupported_requested_products:
        response = renderizar_respuesta_productos_no_soportados(state)
        return response, state, "alternativas_producto"

    coverage = mock_validar_cobertura(state)
    state.coverage_ok = coverage["ok"]
    state.registrar_log("mock_validar_cobertura", coverage)
    if not coverage["ok"]:
        state.handoff_offered = True
        response = (
            f"No tengo cobertura mock confirmada para {state.district}. "
            "No voy a cotizar sin cobertura validada. Si deseas, puedo derivarte con un asesor por WhatsApp."
        )
        return response, state, "sin_cobertura"

    catalog_result = mock_buscar_catalogo(state)
    state.catalog_options = catalog_result["options"]
    state.registrar_log("mock_product_catalog", {"products": catalog_result["products"]})
    state.registrar_log("mock_buscar_catalogo", catalog_result)

    availability = mock_validar_disponibilidad(state, state.catalog_options)
    state.valid_options = availability["available_options"]
    state.discarded_options = availability["discarded_options"]
    state.availability_ok = bool(state.valid_options)
    state.registrar_log("mock_validar_disponibilidad", availability)
    state.dimensioning = mock_dimensionar_evento(state)
    state.registrar_log("mock_dimensionar_evento", state.dimensioning)

    if state.valid_options:
        comparison = mock_comparar_opciones(state)
        state.recommended_option = comparison["recommended"]
        state.recommended_option["source"] = "package"
        state.registrar_log("mock_comparar_opciones", comparison)
    else:
        stock_result = mock_validar_stock_productos(state, state.dimensioning["items"], catalog_result["all_products"])
        state.registrar_log("mock_validar_stock_productos", stock_result)
        if stock_result["missing_items"]:
            state.availability_ok = False
            state.stock_shortage_products = [item["concept"] for item in stock_result["missing_items"]]
            state.handoff_offered = True
            response = renderizar_respuesta_sin_stock(state, stock_result)
            return response, state, "sin_stock"
        state.availability_ok = True
        state.handoff_offered = False
        state.stock_shortage_products = []
        state.recommended_option = construir_opcion_basada_en_productos(state, stock_result["available_items"], catalog_result["similar_packages"])
        state.registrar_log("construir_opcion_basada_en_productos", state.recommended_option)

    if state.intent == "quote" or _parece_confirmacion_cotizacion(user_message):
        state.quote = mock_generar_cotizacion(state)
        state.registrar_log("mock_generar_cotizacion", state.quote)
        state.quote_artifact_image = generar_artefacto_visual_cotizacion(state)
        state.registrar_log("generar_artefacto_visual_cotizacion", {"path": state.quote_artifact_image})
        response = renderizar_respuesta_cotizacion(state)
        return response, state, "cotizacion"

    response = renderizar_respuesta_recomendacion(state)
    return response, state, "recomendacion"


# Ejecuta la responsabilidad de finalizar turno cotizador.
def finalizar_turno_cotizador(response: str, state: QuoteState, stage: str) -> tuple[str, QuoteState]:
    """Aplica pulido, memoria visible y persistencia despues del grafo."""
    return _finalizar(response, state, stage)


# Ejecuta la responsabilidad de fusionar extraccion en estado.
def fusionar_extraccion_en_estado(state: QuoteState, extraction: dict) -> None:
    """Actualiza el estado conversacional con los campos extraidos."""
    state.intent = extraction["intent"]
    state.product_change_cleared_unsupported = False
    fields = extraction.get("fields", {})
    if state.intent == "new_quote":
        limpiar_estado_para_nueva_cotizacion(state)
        state.intent = "recommendation"
    if fields.get("product_changes"):
        aplicar_cambios_productos(state, fields["product_changes"])

    for key in ["event_type", "attendees", "event_date", "district", "budget", "customer_name", "contact"]:
        value = fields.get(key)
        if value is not None:
            setattr(state, key, value)
            if key == "event_date":
                state.partial_date = {"day": None, "month": None, "year": None}

    if fields.get("partial_date") and not state.event_date:
        fusionar_fecha_parcial(state, fields["partial_date"])

    for preference in fields.get("preferences", []):
        if preference not in state.preferences:
            state.preferences.append(preference)

    if debe_fusionar_productos_solicitados(state.intent, fields.get("product_changes", {})):
        for product in fields.get("requested_products", []):
            if product not in state.requested_products:
                state.requested_products.append(product)
            state.unsupported_requested_products = [
                unsupported
                for unsupported in state.unsupported_requested_products
                if product not in productos_similares_para(unsupported)
            ]

    for product in fields.get("unsupported_requested_products", []):
        if product not in state.unsupported_requested_products:
            state.unsupported_requested_products.append(product)

    if state.intent == "modify_request":
        state.quote = None
        state.recommended_option = None
        state.catalog_options = []
        state.valid_options = []
        state.discarded_options = []
        state.dimensioning = None


# Ejecuta la responsabilidad de limpiar estado para nueva cotizacion.
def limpiar_estado_para_nueva_cotizacion(state: QuoteState) -> None:
    """Limpia datos de negocio para iniciar otra cotizacion en la misma sesion."""
    state.registrar_log("limpiar_estado_para_nueva_cotizacion", {"previous_contact": state.contact})
    state.stage = "recoleccion"
    state.event_type = None
    state.attendees = None
    state.event_date = None
    state.partial_date = {"day": None, "month": None, "year": None}
    state.district = None
    state.budget = None
    state.requested_products = []
    state.unsupported_requested_products = []
    state.stock_shortage_products = []
    state.preferences = []
    state.customer_name = None
    state.contact = None
    state.missing_fields = []
    state.catalog_options = []
    state.valid_options = []
    state.discarded_options = []
    state.recommended_option = None
    state.dimensioning = None
    state.quote = None
    state.coverage_ok = None
    state.availability_ok = None
    state.policy_ok = None
    state.handoff_offered = False
    state.handoff_confirmed = False
    state.handoff_summary = None
    state.image_requested = False
    state.quote_artifact_image = None
    state.product_change_cleared_unsupported = False
    state.pending_previous_state = None


# Ejecuta la responsabilidad de detectar conversacion previa por contacto.
def detectar_conversacion_previa_por_contacto(state: QuoteState) -> str | None:
    """Busca automaticamente memoria previa cuando aparece un contacto."""
    if not state.contact or state.pending_previous_state or state.intent == "resume_previous":
        return None
    # MOCK: AQUI SE CONSULTARIA POSTGRESQL/NOSQL POR TELEFONO/CORREO PARA SABER SI EXISTE UNA COTIZACION PREVIA.
    previous = QUOTE_MEMORY.buscar_por_contacto(state.contact)
    if not previous or previous.session_id == state.session_id:
        return None
    if not tiene_memoria_cotizacion_util(previous):
        return None
    state.pending_previous_state = previous.a_diccionario_persistido()
    state.intent = "previous_found"
    state.registrar_log(
        "previous_conversation_found_by_contact",
        {"contact": state.contact, "previous_session_id": previous.session_id},
    )
    return renderizar_respuesta_previa_encontrada(state, previous)


# Ejecuta la responsabilidad de manejar eleccion previa pendiente.
def manejar_eleccion_previa_pendiente(user_message: str, state: QuoteState) -> tuple[str, QuoteState] | None:
    """Resuelve si el usuario quiere retomar lo previo o seguir con lo actual."""
    if not state.pending_previous_state:
        return None
    text = user_message.lower()
    wants_previous = any(term in text for term in ["retomar", "anterior", "previa", "previo", "seguir con esa", "continua esa", "continúa esa"])
    wants_current = any(term in text for term in ["nuevo", "nueva", "actual", "seguir con esta", "continua con esta", "continúa con esta"])
    if wants_previous:
        previous = QuoteState.desde_diccionario_persistido(state.pending_previous_state)
        resumed = QUOTE_MEMORY.hidratar(state, previous)
        resumed.pending_previous_state = None
        resumed.missing_fields = encontrar_campos_faltantes(resumed)
        resumed.registrar_log("resume_previous_after_contact_match", {"contact": resumed.contact})
        return renderizar_respuesta_previa_retomada(resumed), resumed
    if wants_current:
        state.pending_previous_state = None
        state.missing_fields = encontrar_campos_faltantes(state)
        response = (
            "Perfecto, seguimos con la informacion nueva que me acabas de dar. "
            f"{pedir_campos_faltantes_para_estado(state) if state.missing_fields else renderizar_respuesta_revision_pedido(state)}"
        )
        return response, state
    response = (
        "Antes de avanzar, necesito que me confirmes una cosa: encontre una cotizacion previa asociada a ese contacto. "
        "Puedes decir `retomar la anterior` o `seguir con esta nueva`."
    )
    return response, state


# Ejecuta la responsabilidad de aplicar cambios productos.
def aplicar_cambios_productos(state: QuoteState, changes: dict[str, list[str]]) -> None:
    """Aplica cambios solicitados por el usuario sobre productos en curso."""
    had_blocking_product_issue = bool(state.stock_shortage_products or state.unsupported_requested_products)
    if had_blocking_product_issue and changes.get("replace_to") and (changes.get("remove") or changes.get("replace_from")):
        state.product_change_cleared_unsupported = True
    for product in changes.get("replace_from", []):
        if product in state.requested_products:
            state.requested_products.remove(product)
        if product in state.stock_shortage_products:
            state.stock_shortage_products.remove(product)
            state.product_change_cleared_unsupported = True
    for product in changes.get("remove", []):
        if product in state.requested_products:
            state.requested_products.remove(product)
        if product in state.stock_shortage_products:
            state.stock_shortage_products.remove(product)
            state.product_change_cleared_unsupported = True
    for product in changes.get("replace_to", []) + changes.get("add", []):
        for shortage in list(state.stock_shortage_products):
            if product in productos_similares_para(shortage) and shortage in state.requested_products:
                state.requested_products.remove(shortage)
                state.stock_shortage_products.remove(shortage)
                state.product_change_cleared_unsupported = True
        if product not in state.requested_products:
            state.requested_products.append(product)
        before = list(state.unsupported_requested_products)
        state.unsupported_requested_products = [
            unsupported
            for unsupported in state.unsupported_requested_products
            if product not in productos_similares_para(unsupported)
        ]
        if before != state.unsupported_requested_products:
            state.product_change_cleared_unsupported = True
    if any(changes.values()):
        state.quote = None
        state.recommended_option = None
        state.catalog_options = []
        state.valid_options = []
        state.discarded_options = []
        state.dimensioning = None


# Ejecuta la responsabilidad de debe fusionar productos solicitados.
def debe_fusionar_productos_solicitados(intent: str | None, changes: dict) -> bool:
    """Evita reinsertar productos cuando el usuario esta quitando o reemplazando."""
    if intent != "modify_request":
        return True
    return bool(changes.get("add")) and not any(changes.get(key) for key in ["remove", "replace_from", "replace_to"])


# Ejecuta la responsabilidad de aplicar accion agente a intencion.
def aplicar_accion_agente_a_intencion(action: str, state: QuoteState, user_message: str) -> None:
    """Convierte la decision del agente en una intencion ejecutable."""
    mapping = {
        "answer_price": "price_query",
        "generate_quote": "quote",
        "show_image": "image_request",
        "answer_policy": "general_question",
        "close": "close",
        "resume_previous": "resume_previous",
        "new_quote": "recommendation",
    }
    if action == "handoff":
        if es_solicitud_derivacion_explicita(user_message):
            state.intent = "human_handoff"
        return
    if action in mapping:
        state.intent = mapping[action]
    elif action == "pedir_campos_faltantes":
        state.intent = "recommendation"
    elif action == "validate_and_recommend":
        state.intent = "recommendation"


# Ejecuta la responsabilidad de encontrar campos faltantes.
def encontrar_campos_faltantes(state: QuoteState) -> list[str]:
    """Calcula datos minimos faltantes antes de consultar tools de negocio."""
    missing = []
    for field in REQUIRED_FIELDS:
        value = getattr(state, field)
        if value in (None, "", []):
            if field == "requested_products" and state.unsupported_requested_products:
                continue
            missing.append(field)
    return missing


# Ejecuta la responsabilidad de pedir campos faltantes.
def pedir_campos_faltantes(missing_fields: list[str]) -> str:
    """Construye una pregunta breve para pedir los campos faltantes."""
    labels = {
        "event_type": "tipo de evento",
        "attendees": "cantidad de asistentes",
        "event_date": "fecha",
        "district": "distrito",
        "customer_name": "nombre de la persona que cotiza",
        "contact": "telefono o correo para seguimiento",
        "requested_products": "productos o servicios a cotizar, por ejemplo cerveza, vino, gaseosas, hielo, bartender o bar movil",
    }
    next_fields = priorizar_campos_faltantes(missing_fields)
    readable = [labels[field] for field in next_fields]
    if len(readable) == 1:
        return f"Perfecto, voy avanzando. Para continuar solo necesito confirmar **{readable[0]}**."
    return (
        "Perfecto, voy avanzando. Para seguir sin asumir datos, dime por favor: "
        + ", ".join(readable[:-1])
        + f" y {readable[-1]}."
    )


# Ejecuta la responsabilidad de priorizar campos faltantes.
def priorizar_campos_faltantes(missing_fields: list[str]) -> list[str]:
    """Agrupa faltantes para no pedir demasiadas cosas en un solo turno."""
    priority_groups = [
        ["event_type", "attendees", "event_date", "district"],
        ["customer_name", "contact"],
        ["requested_products"],
    ]
    for group in priority_groups:
        selected = [field for field in group if field in missing_fields]
        if selected:
            return selected[:3]
    return missing_fields[:3]


# Ejecuta la responsabilidad de pedir campos faltantes para estado.
def pedir_campos_faltantes_para_estado(state: QuoteState) -> str:
    """Elige la pregunta adecuada segun el tipo de dato faltante."""
    if state.missing_fields == ["event_date"]:
        return mensaje_fecha_faltante(state)
    if priorizar_campos_faltantes(state.missing_fields) == ["requested_products"]:
        return pedir_productos_con_catalogo(state)
    response = pedir_campos_faltantes(state.missing_fields)
    if "event_date" in state.missing_fields and (state.partial_date.get("day") or state.partial_date.get("month")):
        response += f" Sobre la fecha: {mensaje_fecha_faltante(state)}"
    return response


# Ejecuta la responsabilidad de pedir productos con catalogo.
def pedir_productos_con_catalogo(state: QuoteState) -> str:
    """Muestra opciones de catalogo cuando faltan productos/servicios."""
    catalog_result = mock_buscar_catalogo(state)
    state.registrar_log(
        "mock_catalog_options_for_product_selection",
        {
            "products": catalog_result["all_products"],
            "packages": paquetes_seleccionables_para_estado(state),
        },
    )
    product_lines = "\n".join(
        f"- {product['name']} ({product['category']}): {product['currency']} {product['unit_price']:.2f} por {product['unit']}"
        for product in catalog_result["all_products"]
    )
    package_lines = "\n".join(
        f"- {package['name']} ({package['service']}): {package['currency']} {package['base_price']:.2f} base"
        for package in paquetes_seleccionables_para_estado(state)
    )
    sections = []
    if product_lines:
        sections.append(f"Productos disponibles para elegir:\n{product_lines}")
    if package_lines:
        sections.append(f"Servicios/paquetes disponibles:\n{package_lines}")
    if not sections:
        return (
            "Ya tengo los datos principales, pero necesito saber que productos o servicios quieres cotizar. "
            "Puedes pedirme bebidas, hielo, bartender o bar movil, y validare contra el catalogo mock."
        )
    return (
        "Ya tengo los datos principales. Para seguir, elige que productos o servicios quieres cotizar de este catalogo mock:\n\n"
        + "\n\n".join(sections)
        + "\n\nPuedes responder con una lista simple, por ejemplo: `cerveza, vino y hielo`."
    )


# Ejecuta la responsabilidad de paquetes seleccionables para estado.
def paquetes_seleccionables_para_estado(state: QuoteState) -> list[dict]:
    """Lista paquetes que tienen sentido para el evento y capacidad."""
    packages = []
    for package in CATALOG:
        if state.event_type and state.event_type not in package["event_types"]:
            continue
        if state.attendees and state.attendees > package["capacity_max"]:
            continue
        packages.append(package)
    return packages


# Ejecuta la responsabilidad de mensaje fecha faltante.
def mensaje_fecha_faltante(state: QuoteState) -> str:
    """Explica si falta dia, mes o toda la fecha."""
    day = state.partial_date.get("day")
    month = state.partial_date.get("month")
    if day and not month:
        return f"Ya tengo el dia {day}, pero me falta el mes del evento."
    if month and not day:
        return f"Ya tengo el mes de {nombre_mes(month)}, pero me falta el dia del evento."
    return "Para seguir necesito la fecha completa del evento, por ejemplo: `4 de diciembre`."


# Ejecuta la responsabilidad de fusionar fecha parcial.
def fusionar_fecha_parcial(state: QuoteState, partial_date: dict[str, int | None]) -> None:
    """Combina partes de fecha dadas en distintos turnos."""
    if (
        partial_date.get("month") is not None
        and partial_date.get("day") is None
        and state.partial_date.get("day") == state.attendees
    ):
        state.partial_date["day"] = None
    for key in ["day", "month", "year"]:
        if partial_date.get(key) is not None:
            state.partial_date[key] = partial_date[key]
    if state.partial_date.get("day") and state.partial_date.get("month"):
        year = state.partial_date.get("year") or 2026
        state.event_date = date(year, state.partial_date["month"], state.partial_date["day"]).isoformat()
        state.partial_date = {"day": None, "month": None, "year": None}


# Ejecuta la responsabilidad de pedir confirmacion derivacion.
def pedir_confirmacion_derivacion(state: QuoteState) -> str:
    """Ofrece derivacion humana para casos que el flujo no puede resolver."""
    if state.intent == "discount_request":
        reason = "No puedo aprobar descuentos desde el flujo automatico."
    elif state.intent == "payment_request":
        reason = "No puedo confirmar pagos ni reservas desde esta POC."
    else:
        reason = "Esta solicitud requiere revision humana."
    return f"{reason} Si te parece, puedo dejar el caso listo para que un asesor lo continue por WhatsApp."


# Ejecuta la responsabilidad de renderizar respuesta recomendacion.
def renderizar_respuesta_recomendacion(state: QuoteState) -> str:
    """Redacta la recomendacion validada antes de emitir cotizacion."""
    option = state.recommended_option or {}
    dimensioning = state.dimensioning or {}
    items = ", ".join(
        f"{item['quantity']} {item['unit']} de {item['concept']}" for item in dimensioning.get("items", [])[:4]
    )
    reasons = "\n".join(f"- {reason}" for reason in option.get("reasons", []))
    checks = renderizar_resumen_validacion(state)
    if option.get("source") == "products":
        product_lines = "\n".join(
            f"- {item['quantity']} {item['unit']} de {item['concept']} ({item['product_name']})"
            for item in option.get("items", [])
        )
        return (
            f"Listo, {state.customer_name}. Revise paquetes, fecha y stock mock. No encontre un paquete disponible que calce completo, "
            f"pero si pude armar una propuesta con productos disponibles para tu {state.event_type} de {state.attendees} personas "
            f"en {state.district} el {state.event_date}.\n\n"
            f"{checks}\n\n"
            f"Productos considerados:\n{product_lines}\n\n"
            "Si esta propuesta te parece bien, dime `genera la cotizacion` y la emito con estos productos."
        )
    return (
        f"Listo, {state.customer_name}. Ya consulte cobertura, catalogo y disponibilidad mock. "
        f"Con eso, la mejor opcion que encontre es **{option.get('name')}** para tu {state.event_type} de "
        f"{state.attendees} personas en {state.district} el {state.event_date}.\n\n"
        f"{checks}\n\n"
        f"{reasons}\n\n"
        f"Dimensionamiento mock sugerido segun productos solicitados ({', '.join(state.requested_products)}): {items}.\n\n"
        "Si quieres que la deje como cotizacion formal de la POC, dime `genera la cotizacion`."
    )


# Ejecuta la responsabilidad de renderizar respuesta cotizacion.
def renderizar_respuesta_cotizacion(state: QuoteState) -> str:
    """Redacta el detalle de la cotizacion ya generada."""
    quote = state.quote or {}
    option = state.recommended_option or {}
    conditions = "\n".join(f"- {condition}" for condition in quote.get("conditions", []))
    details = "\n".join(
        f"- {item['quantity']} {item['unit']} x {item['concept']}: {quote.get('currency')} {item['subtotal']:.2f}"
        for item in quote.get("details", [])
    )
    return (
        f"Listo, genere la Cotizacion mock **{quote.get('quote_id')}** para **{option.get('name')}**.\n"
        f"Cotizante: {state.customer_name} | Contacto seguimiento: {state.contact}\n\n"
        f"Detalle:\n{details}\n\n"
        f"- Subtotal: {quote.get('currency')} {quote.get('subtotal'):.2f}\n"
        f"- IGV: {quote.get('currency')} {quote.get('taxes'):.2f}\n"
        f"- Total: **{quote.get('currency')} {quote.get('total'):.2f}**\n"
        f"- Vigencia: {quote.get('valid_until')}\n\n"
        f"{renderizar_resumen_validacion(state)}\n\n"
        f"Condiciones:\n{conditions}"
    )


# Ejecuta la responsabilidad de renderizar respuesta consulta precio.
def renderizar_respuesta_consulta_precio(user_message: str, state: QuoteState) -> str:
    """Responde precios informativos sin generar cotizacion."""
    product_matches = buscar_coincidencias_precio(user_message)
    if product_matches:
        lines = "\n".join(
            f"- {item['name']}: {item['currency']} {item['unit_price']:.2f} por {item['unit']}"
            for item in product_matches
        )
        return (
            "Claro. Este es el precio informativo mock, sin generar cotizacion ni reservar stock:\n\n"
            f"{lines}\n\n"
            "Si quieres que lo incluya en una cotizacion, dime `genera la cotizacion` y primero validare los datos necesarios."
        )

    if state.recommended_option:
        if state.recommended_option.get("source") == "products":
            subtotal = round(sum(item["subtotal"] for item in state.recommended_option["items"]), 2)
            taxes = round(subtotal * 0.18, 2)
            total = round(subtotal + taxes, 2)
            return (
                "Claro. Este es el costo informativo mock de la propuesta por productos, sin generar cotizacion todavia:\n\n"
                f"- Subtotal: PEN {subtotal:.2f}\n"
                f"- IGV referencial: PEN {taxes:.2f}\n"
                f"- Total referencial: PEN {total:.2f}\n\n"
                "Si confirmas que quieres emitirla, dime `genera la cotizacion`."
            )
        base_price = state.recommended_option["base_price"]
        taxes = round(base_price * 0.18, 2)
        total = round(base_price + taxes, 2)
        return (
            f"Claro. Este es el costo informativo mock de **{state.recommended_option['name']}**, sin generar cotizacion todavia:\n\n"
            f"- Precio base: {state.recommended_option['currency']} {base_price:.2f}\n"
            f"- IGV referencial: {state.recommended_option['currency']} {taxes:.2f}\n"
            f"- Total referencial: {state.recommended_option['currency']} {total:.2f}\n\n"
            "Si confirmas que quieres emitirla, dime `genera la cotizacion`."
        )

    package_matches = buscar_coincidencias_precio_paquete(user_message)
    if package_matches:
        lines = "\n".join(
            f"- {item['name']}: {item['currency']} {item['base_price']:.2f} precio base"
            for item in package_matches
        )
        return (
            "Claro. Este es el precio informativo mock del paquete, sin validar disponibilidad ni generar cotizacion:\n\n"
            f"{lines}\n\n"
            "Para cotizarlo necesito validar evento, fecha, distrito, datos de contacto, preferencias y stock."
        )

    return (
        "Puedo ayudarte con el precio informativo si me dices el producto o paquete, por ejemplo cerveza, vino, gaseosa, hielo, bartender o bar movil. "
        "Para generar una cotizacion, primero validare datos, cobertura y disponibilidad."
    )


# Ejecuta la responsabilidad de renderizar resumen validacion.
def renderizar_resumen_validacion(state: QuoteState) -> str:
    """Resume cobertura, catalogo y disponibilidad consultados."""
    package_count = len(state.catalog_options)
    available_package_count = len(state.valid_options)
    if state.recommended_option and state.recommended_option.get("source") == "products":
        product_count = len(state.recommended_option.get("items", []))
        source = "cotizacion armada desde productos disponibles por falta de paquete calzante."
        availability_line = f"- Stock de productos consultado para {state.event_date}: {product_count} producto(s)/servicio(s) disponible(s)."
    else:
        source = "paquete disponible validado."
        availability_line = f"- Disponibilidad consultada para {state.event_date}: {available_package_count} paquete(s) disponible(s)."
    return (
        "Validaciones realizadas:\n"
        f"- Cobertura consultada para {state.district}: {'OK' if state.coverage_ok else 'No disponible'}.\n"
        f"- Catalogo consultado: {package_count} paquete(s) calzante(s) por ocasion/capacidad.\n"
        f"{availability_line}\n"
        f"- Fuente de propuesta: {source}"
    )


# Ejecuta la responsabilidad de buscar coincidencias precio.
def buscar_coincidencias_precio(user_message: str) -> list[dict]:
    """Busca productos mencionados para responder precio unitario."""
    text = user_message.lower()
    tokens = [token.strip(".,;:!?¿¡") for token in text.split()]
    matches = []
    for product in PRODUCTS:
        haystack = f"{product['name']} {product['category']}".lower()
        if any(token in haystack for token in tokens if len(token) > 3):
            matches.append(product)
    return matches


# Ejecuta la responsabilidad de buscar coincidencias precio paquete.
def buscar_coincidencias_precio_paquete(user_message: str) -> list[dict]:
    """Busca paquetes mencionados para responder precio base."""
    text = user_message.lower()
    tokens = [token.strip(".,;:!?¿¡") for token in text.split()]
    matches = []
    for package in CATALOG:
        haystack = f"{package['name']} {package['service']}".lower()
        if any(token in haystack for token in tokens if len(token) > 3):
            matches.append(package)
    return matches


# Ejecuta la responsabilidad de renderizar respuesta sin stock.
def renderizar_respuesta_sin_stock(state: QuoteState, stock_result: dict) -> str:
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
        "Revise cobertura, catalogo, disponibilidad y stock mock, pero no tengo todo lo necesario para cotizar con seguridad.\n\n"
        f"Faltantes:\n{missing}\n\n"
        "No voy a reemplazar productos sin tu confirmacion. Dime si quieres cambiar alguno por una alternativa disponible."
    )


# Ejecuta la responsabilidad de construir opcion basada en productos.
def construir_opcion_basada_en_productos(state: QuoteState, available_items: list[dict], similar_packages: list[dict]) -> dict:
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
        "Se usaron productos mock con stock suficiente para la fecha.",
    ]
    if similar_packages:
        reasons.append(f"Paquete parecido encontrado pero descartado: {similar_packages[0]['name']} ({similar_packages[0]['discard_reason']})")
    return {
        "id": "CUSTOM-PRODUCTS-001",
        "name": "Cotizacion por productos disponibles",
        "source": "products",
        "currency": "PEN",
        "items": quote_items,
        "reasons": reasons,
        "image": "app/data/assets/pack_celebracion_esencial.svg",
    }


# Ejecuta la responsabilidad de renderizar respuesta solicitud imagen.
def renderizar_respuesta_solicitud_imagen(state: QuoteState) -> str:
    """Permite mostrar imagen referencial solo despues de cotizar."""
    if not state.quote or not state.recommended_option:
        state.image_requested = False
        return "Puedo mostrar una imagen referencial despues de generar una cotizacion. Primero completemos la cotizacion para no mostrarte una opcion que aun no esta validada."
    state.image_requested = True
    return "Listo. Muestro una imagen referencial del paquete cotizado debajo del chat."


# Ejecuta la responsabilidad de renderizar respuesta cierre.
def renderizar_respuesta_cierre(state: QuoteState) -> str:
    """Cierra la conversacion indicando si quedo cotizacion asociada."""
    if state.quote:
        return (
            f"Perfecto, cierro la conversacion dejando la cotizacion {state.quote['quote_id']} asociada a "
            f"{state.customer_name} ({state.contact}) para seguimiento. Puedes reiniciar desde el boton lateral."
        )
    return "Perfecto, cierro la conversacion sin cotizacion generada. Puedes reiniciar desde el boton lateral para empezar otra solicitud."


# Ejecuta la responsabilidad de renderizar respuesta consulta memoria.
def renderizar_respuesta_consulta_memoria(state: QuoteState) -> str:
    """Responde reclamos o consultas sobre datos ya capturados."""
    if state.customer_name:
        state.missing_fields = encontrar_campos_faltantes(state)
        if state.missing_fields:
            return (
                f"Tienes razon, ya tengo tu nombre: **{state.customer_name}**. "
                f"Me falta esto para avanzar: {', '.join(_etiquetas_campos_faltantes(state.missing_fields))}."
            )
        return f"Tienes razon, ya tengo tu nombre: **{state.customer_name}**. Con eso ya puedo continuar."
    return (
        "Tienes razon en reclamarlo; no logre identificar el nombre en el mensaje anterior. "
        "Puedes escribirlo como: `Soy Nombre Apellido`."
    )


# Ejecuta la responsabilidad de manejar retomar previa.
def manejar_retomar_previa(state: QuoteState) -> tuple[str, QuoteState]:
    """Retoma una cotizacion previa si el usuario confirma identidad."""
    if not state.contact:
        state.missing_fields = ["contact"]
        return (
            "Claro, puedo intentar buscar lo que quedo guardado de una cotizacion anterior. "
            "Para ubicarla, dime por favor el telefono o correo que usaste en esa conversacion.",
            state,
        )

    # MOCK: AQUI SE CONSULTARIA POSTGRESQL O NOSQL PARA RECUPERAR LA SESSION/COTIZACION ANTERIOR DEL CLIENTE.
    previous = QUOTE_MEMORY.buscar_por_contacto(state.contact)
    if not previous or not tiene_memoria_cotizacion_util(previous):
        state.missing_fields = encontrar_campos_faltantes(state)
        return (
            f"No encontre una cotizacion anterior asociada al contacto **{state.contact}**. "
            "Empecemos una nueva cotizacion con ese contacto: cuentame el tipo de evento, cantidad de asistentes y fecha.",
            state,
        )

    resumed = QUOTE_MEMORY.hidratar(state, previous)
    resumed.registrar_log(
        "resume_previous_conversation",
        {"customer_name": resumed.customer_name, "contact": resumed.contact, "resumed_session_id": previous.session_id},
    )
    # MOCK: DESPUES DE RECUPERAR POR IDENTIDAD, ESTA COTIZACION SE HIDRATA EN EL SESSION_ID ACTUAL Y SE GUARDARA EN REDIS AL FINAL DEL TURNO.
    resumed.missing_fields = encontrar_campos_faltantes(resumed)
    response = (
        f"Listo, retome la ultima cotizacion que tenia para **{resumed.customer_name}** "
        f"con contacto **{resumed.contact}**.\n\n"
        f"{renderizar_respuesta_revision_pedido(resumed)}"
    )
    return response, resumed


# Ejecuta la responsabilidad de tiene memoria cotizacion util.
def tiene_memoria_cotizacion_util(state: QuoteState) -> bool:
    """Evita tratar registros vacios o solo-contacto como cotizaciones previas."""
    datos_evento = [state.event_type, state.attendees, state.event_date, state.district]
    return bool(
        state.quote
        or state.recommended_option
        or state.requested_products
        or (state.customer_name and sum(value not in (None, "", []) for value in datos_evento) >= 2)
    )


# Ejecuta la responsabilidad de renderizar respuesta previa encontrada.
def renderizar_respuesta_previa_encontrada(state: QuoteState, previous: QuoteState) -> str:
    """Compara datos actuales y previos antes de avanzar."""
    return (
        f"Encontre una cotizacion previa asociada al contacto **{state.contact}**. "
        "Antes de pedirte mas datos, confirmemos si quieres retomarla o seguir con lo nuevo.\n\n"
        f"Datos que acabas de dar:\n{renderizar_resumen_pedido_compacto(state)}\n\n"
        f"Cotizacion previa encontrada:\n{renderizar_resumen_pedido_compacto(previous)}\n\n"
        "Dime `retomar la anterior` para continuar desde lo guardado, o `seguir con esta nueva` para usar los datos actuales."
    )


# Ejecuta la responsabilidad de renderizar respuesta previa retomada.
def renderizar_respuesta_previa_retomada(state: QuoteState) -> str:
    """Confirma que se cargo la cotizacion previa en la sesion actual."""
    return (
        f"Listo, retome la cotizacion previa asociada al contacto **{state.contact}**.\n\n"
        f"{renderizar_respuesta_revision_pedido(state)}"
    )


# Ejecuta la responsabilidad de renderizar resumen pedido compacto.
def renderizar_resumen_pedido_compacto(state: QuoteState) -> str:
    """Resume una solicitud para comparar memoria previa contra datos actuales."""
    products = ", ".join(state.requested_products) if state.requested_products else "pendiente"
    return (
        f"- Evento: {state.event_type or 'pendiente'}\n"
        f"- Asistentes: {state.attendees or 'pendiente'}\n"
        f"- Fecha: {state.event_date or 'pendiente'}\n"
        f"- Distrito: {state.district or 'pendiente'}\n"
        f"- Cotizante: {state.customer_name or 'pendiente'}\n"
        f"- Contacto: {state.contact or 'pendiente'}\n"
        f"- Productos/servicios: {products}"
    )


# Ejecuta la responsabilidad de renderizar respuesta revision pedido.
def renderizar_respuesta_revision_pedido(state: QuoteState) -> str:
    """Muestra el pedido actual y ejemplos para modificarlo."""
    products = ", ".join(state.requested_products) if state.requested_products else "sin productos/servicios elegidos todavia"
    event_date_text = state.event_date
    if not event_date_text and (state.partial_date.get("day") or state.partial_date.get("month")):
        event_date_text = texto_fecha_parcial(state)
    unsupported = (
        f"\n- Pendientes/no disponibles: {', '.join(state.unsupported_requested_products)}"
        if state.unsupported_requested_products
        else ""
    )
    return (
        "Claro, revisemos el pedido actual antes de cotizar:\n\n"
        f"- Evento: {state.event_type or 'pendiente'}\n"
        f"- Asistentes: {state.attendees or 'pendiente'}\n"
        f"- Fecha: {event_date_text or 'pendiente'}\n"
        f"- Distrito: {state.district or 'pendiente'}\n"
        f"- Cotizante: {state.customer_name or 'pendiente'}\n"
        f"- Contacto: {state.contact or 'pendiente'}\n"
        f"- Productos/servicios: {products}"
        f"{unsupported}\n\n"
        "Puedes decirme, por ejemplo: `quitar vino`, `agregar hielo`, `cambiar cerveza por agua` o `genera la cotizacion` si ya esta conforme."
    )


# Ejecuta la responsabilidad de renderizar respuesta saludo.
def renderizar_respuesta_saludo(state: QuoteState) -> str:
    """Saluda y abre la recoleccion inicial de datos."""
    return (
        "Hola, estoy bien y listo para ayudarte con la cotizacion de tu evento. "
        "Para empezar sin asumir nada, cuentame que tipo de evento tienes, para cuantas personas y en que fecha seria."
    )


# Ejecuta la responsabilidad de renderizar respuesta derivacion.
def renderizar_respuesta_derivacion(handoff: dict) -> str:
    """Redacta la derivacion mock preparada para WhatsApp."""
    summary = handoff["summary"]
    return (
        "Listo, deje preparada una derivacion mock por WhatsApp.\n\n"
        f"- ID: {handoff['handoff_id']}\n"
        f"- Motivo: {summary['reason']}\n"
        f"- Link: {handoff['url']}\n\n"
        "El resumen para el asesor queda disponible en el panel lateral."
    )


# Ejecuta la responsabilidad de renderizar respuesta rag.
def renderizar_respuesta_rag(query: str) -> str:
    """Responde consultas de politica usando el RAG mock."""
    result = mock_buscar_rag(query)
    if not result["matches"]:
        return "No encontre una politica mock relacionada. Para la POC solo tengo anticipacion, feriados y descuentos."
    lines = [f"- **{doc['title']}**: {doc['text']}" for doc in result["matches"]]
    return "Segun el RAG mock:\n\n" + "\n".join(lines)


# Ejecuta logica interna para parece confirmacion cotizacion.
def _parece_confirmacion_cotizacion(message: str) -> bool:
    """Detecta confirmaciones cortas para emitir cotizacion."""
    text = message.lower()
    return any(term in text for term in ["si cotiza", "sí cotiza", "cotizalo", "cotízalo", "genera la cotizacion", "genera la cotización"])


# Ejecuta logica interna para finalizar.
def _finalizar(response: str, state: QuoteState, stage: str) -> tuple[str, QuoteState]:
    """Aplica pulido LLM, agrega memoria visible, guarda estado y retorna."""
    state.stage = stage
    polished_response = pulir_respuesta(response, state)
    response_with_memory = f"{polished_response}\n\n{renderizar_memoria_temporal(state)}"
    state.messages.append({"role": "assistant", "content": response_with_memory})
    state.registrar_log("response", {"stage": stage, "content": response_with_memory})
    if not state.pending_previous_state:
        # MOCK: AQUI SE GUARDARIA EL ESTADO DE LA SESSION EN POSTGRESQL O NOSQL PARA RETOMAR LA COTIZACION DESPUES.
        QUOTE_MEMORY.guardar(state)
    ACTIVE_SESSIONS.guardar(state)
    return response_with_memory, state


# Ejecuta la responsabilidad de renderizar memoria temporal.
def renderizar_memoria_temporal(state: QuoteState) -> str:
    """Genera el resumen sutil de memoria mostrado bajo cada respuesta."""
    captured = []
    if state.customer_name:
        captured.append(f"cotizante: {state.customer_name}")
    if state.contact:
        captured.append(f"contacto: {state.contact}")
    if state.event_type:
        captured.append(f"evento: {state.event_type}")
    if state.attendees:
        captured.append(f"asistentes: {state.attendees}")
    if state.event_date:
        captured.append(f"fecha: {state.event_date}")
    elif state.partial_date.get("day") or state.partial_date.get("month"):
        captured.append(f"fecha parcial: {texto_fecha_parcial(state)}")
    if state.district:
        captured.append(f"distrito: {state.district}")
    if state.requested_products:
        captured.append(f"productos/servicios: {', '.join(state.requested_products)}")
    if state.unsupported_requested_products:
        captured.append(f"productos no disponibles: {', '.join(state.unsupported_requested_products)}")
    if state.preferences:
        captured.append(f"preferencias: {', '.join(state.preferences)}")

    captured_text = "; ".join(captured) if captured else "sin datos capturados todavia"
    if state.intent == "resume_previous" and not state.contact:
        return f"_Tengo en memoria: {captured_text}. Siguiente por confirmar: telefono o correo para buscar la cotizacion anterior._"
    missing = encontrar_campos_faltantes(state)
    if missing:
        next_missing = priorizar_campos_faltantes(missing)
        missing_text = ", ".join(_etiquetas_campos_faltantes(next_missing))
        return f"_Tengo en memoria: {captured_text}. Siguiente por confirmar: {missing_text}._"
    return f"_Memoria temporal: {captured_text}. Datos minimos completos para continuar._"


# Ejecuta la responsabilidad de texto fecha parcial.
def texto_fecha_parcial(state: QuoteState) -> str:
    """Convierte una fecha parcial en texto legible."""
    day = state.partial_date.get("day")
    month = state.partial_date.get("month")
    if day and month:
        return f"{day} de {nombre_mes(month)}"
    if day:
        return f"dia {day}, falta mes"
    if month:
        return f"{nombre_mes(month)}, falta dia"
    return "incompleta"


# Ejecuta la responsabilidad de nombre mes.
def nombre_mes(month: int) -> str:
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
    return names.get(month, f"mes {month}")


# Ejecuta logica interna para etiquetas campos faltantes.
def _etiquetas_campos_faltantes(missing_fields: list[str]) -> list[str]:
    """Traduce nombres internos de campos a etiquetas para el usuario."""
    labels = {
        "event_type": "tipo de evento",
        "attendees": "cantidad de asistentes",
        "event_date": "fecha",
        "district": "distrito",
        "customer_name": "nombre de la persona que cotiza",
        "contact": "telefono o correo para seguimiento",
        "requested_products": "productos o servicios a cotizar",
    }
    return [labels[field] for field in missing_fields]


# Ejecuta la responsabilidad de renderizar respuesta productos no soportados.
def renderizar_respuesta_productos_no_soportados(state: QuoteState) -> str:
    """Explica productos no soportados y alternativas conocidas."""
    lines = []
    for product in state.unsupported_requested_products:
        suggestions = productos_similares_para(product)
        if suggestions:
            lines.append(f"- {product}: no lo tengo en catalogo mock. Parecido disponible: {', '.join(suggestions)}.")
        else:
            lines.append(f"- {product}: no lo tengo en catalogo mock y no encontre un sustituto parecido.")

    available_requested = ""
    if state.requested_products:
        available_requested = f"\n\nSi mantenemos lo disponible, por ahora tengo: {', '.join(state.requested_products)}."

    return (
        "Antes de cotizar, revise lo que pediste contra el catalogo mock y hay productos que no tengo exactamente:\n\n"
        + "\n".join(lines)
        + available_requested
        + "\n\nDime si quieres reemplazarlo por alguna alternativa disponible o si prefieres cambiar la lista de productos."
    )


# Ejecuta la responsabilidad de productos similares para.
def productos_similares_para(product: str) -> list[str]:
    """Devuelve alternativas simples para productos no soportados."""
    suggestions = {
        "whisky": ["ron", "vino", "cerveza"],
        "ron": ["cerveza", "vino"],
        "pisco": ["vino"],
        "champagne": ["vino"],
        "agua": ["gaseosa", "hielo"],
        "jugo": ["gaseosa"],
        "snacks": [],
    }
    return suggestions.get(product, [])
