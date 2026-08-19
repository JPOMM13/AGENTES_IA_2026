from src.state import InitiativeState
from src.llm import analyze_with_llm
from src.config import OLLAMA_MODEL
from src.tools import (
    calculate_technical_progress,
    add_actor_to_initiative,
    get_initiative,
    get_procedure,
    get_repository,
    get_spec,
    get_tracking,
    load_json,
    normalize,
)


# Interpreta la consulta con el LLM y usa reglas si el modelo no está disponible.
def supervisor(state: InitiativeState) -> dict:
    llm_analysis = analyze_with_llm(state["user_query"])

    if llm_analysis:
        return _supervisor_from_llm(state, llm_analysis)

    return _supervisor_with_rules(state)


# Clasifica la intención y selecciona agentes mediante palabras clave.
def _supervisor_with_rules(state: InitiativeState) -> dict:
    query = normalize(state["user_query"])
    initiative = get_initiative(state["user_query"])
    asks_actor_update = "agregar" in query and any(
        word in query for word in ["actor", "participante"]
    )

    asks_procedure = any(
        phrase in query
        for phrase in [
            "como hago",
            "como realizar",
            "procedimiento",
            "pase a produccion",
            "pasar a produccion",
            "conexion a teradata",
            "validacion previa a uat",
            "lanzarlo",
            "lanzar",
        ]
    )
    asks_tracking = any(
        word in query for word in ["falta", "pendiente", "bloqueo", "que cosas siguen"]
    )
    asks_technical = any(word in query for word in ["avance tecnico", "estado tecnico", "spec", "implementado"])
    asks_status = any(
        word in query for word in ["estado", "como va", "como anda", "cual es"]
    )

    # La consulta principal combina las cuatro capacidades.
    is_composite = initiative and asks_procedure and asks_tracking
    if asks_actor_update:
        agents, intent = ["update"], "actualizar_actor"
    elif is_composite:
        agents = ["initiative", "tracking", "technical", "procedure"]
        intent = "consulta_compuesta"
    elif asks_procedure and not (asks_tracking or asks_technical):
        agents, intent = ["procedure"], "procedimiento"
    elif asks_technical:
        agents, intent = ["technical"], "estado_tecnico"
    elif asks_tracking:
        agents, intent = ["tracking"], "seguimiento"
    else:
        agents, intent = ["initiative"], "iniciativa"

    errors = []
    if not initiative and intent != "procedimiento":
        names = "\n".join(f"- {item['name']}" for item in load_json("initiatives.json"))
        errors.append(f"No encontré la iniciativa solicitada.\nIniciativas disponibles:\n{names}")
        agents = []

    return {
        "initiative_name": initiative["name"] if initiative else None,
        "intent": intent,
        "actor_name": _extract_actor_name(state["user_query"]) if asks_actor_update else None,
        "interpretation_mode": "Reglas determinísticas",
        "required_agents": agents,
        "errors": errors,
        "execution_trace": ["Supervisor (reglas)"],
        "agent_results": [],
    }


# Convierte el análisis del LLM en la ruta de agentes que ejecutará el grafo.
def _supervisor_from_llm(state: InitiativeState, analysis) -> dict:
    initiatives = load_json("initiatives.json")
    initiative = next(
        (item for item in initiatives if item["name"] == analysis.initiative_name),
        None,
    )
    query = normalize(state["user_query"])
    intent = analysis.intent

    # Corrige clasificaciones evidentes del LLM con reglas de negocio simples.
    asks_procedure = any(
        phrase in query
        for phrase in [
            "como hago",
            "como realizar",
            "procedimiento",
            "pase a produccion",
            "pasar a produccion",
            "conexion a teradata",
            "validacion previa a uat",
            "lanzarlo",
            "lanzar",
        ]
    )
    asks_tracking = any(
        phrase in query
        for phrase in ["que falta", "pendiente", "bloqueo", "que cosas siguen"]
    )
    asks_technical = any(
        phrase in query
        for phrase in ["avance tecnico", "estado tecnico", "spec", "implementado"]
    )
    asks_status = any(
        phrase in query for phrase in ["estado", "como va", "como anda"]
    )

    if intent != "actualizar_actor":
        if initiative and asks_procedure and asks_tracking:
            intent = "consulta_compuesta"
        elif asks_technical:
            intent = "estado_tecnico"
        elif asks_tracking:
            intent = "seguimiento"
        elif asks_procedure:
            intent = "procedimiento"
        elif initiative and asks_status:
            intent = "iniciativa"
        elif initiative:
            # Si se menciona una iniciativa sin otra capacidad clara, se consultan sus datos.
            intent = "iniciativa"

    routes_by_intent = {
        "iniciativa": ["initiative"],
        "procedimiento": ["procedure"],
        "seguimiento": ["tracking"],
        "estado_tecnico": ["technical"],
        "consulta_compuesta": ["initiative", "tracking", "technical", "procedure"],
        "actualizar_actor": ["update"],
    }
    agents = routes_by_intent[intent]
    errors = []

    if not initiative and intent != "procedimiento":
        names = "\n".join(f"- {item['name']}" for item in initiatives)
        errors.append(f"No encontré la iniciativa solicitada.\nIniciativas disponibles:\n{names}")
        agents = []

    return {
        "initiative_name": initiative["name"] if initiative else None,
        "intent": intent,
        "actor_name": analysis.actor_name,
        "interpretation_mode": f"LLM local ({OLLAMA_MODEL})",
        "required_agents": agents,
        "errors": errors,
        "execution_trace": ["Supervisor (LLM)"],
        "agent_results": [],
    }


# Agrega el actor solicitado a la iniciativa identificada.
def update_agent(state: InitiativeState) -> dict:
    actor_name = state.get("actor_name")
    errors = list(state.get("errors", []))
    if not actor_name:
        errors.append("No pude identificar el nombre del actor que deseas agregar.")
        return _next(state, "Update Agent", errors=errors)

    message = add_actor_to_initiative(state["initiative_name"], actor_name)
    return _next(state, "Update Agent", update_message=message)


# Extrae el nombre del actor desde una orden de actualización sencilla.
def _extract_actor_name(query: str) -> str | None:
    # Forma determinística admitida: "actor ... sería Thales".
    clean_query = query.strip().rstrip(".?!")
    lowered = normalize(clean_query)
    for marker in ["seria ", "actor ", "participante "]:
        position = lowered.rfind(marker)
        if position >= 0:
            words = clean_query[position + len(marker):].strip().split()
            return words[0] if words else None
    return None


# Consulta la información general de la iniciativa identificada.
def initiative_agent(state: InitiativeState) -> dict:
    data = get_initiative(state["initiative_name"] or "")
    return _next(state, "Initiative Agent", initiative_data=data or {})


# Consulta el procedimiento relacionado con la pregunta del usuario.
def procedure_agent(state: InitiativeState) -> dict:
    data = get_procedure(state["user_query"])
    errors = list(state.get("errors", []))
    if not data:
        errors.append("No encontré un procedimiento relacionado con la consulta.")
    return _next(state, "Procedure Agent", procedure_data=data or {}, errors=errors)


# Consulta los pendientes, bloqueos y próximo paso de la iniciativa.
def tracking_agent(state: InitiativeState) -> dict:
    data = get_tracking(state["initiative_name"] or "")
    return _next(state, "Tracking Agent", tracking_data=data or {})


# Compara el Spec con el repositorio simulado para calcular el avance técnico.
def technical_agent(state: InitiativeState) -> dict:
    initiative = get_initiative(state["initiative_name"] or "")
    errors = list(state.get("errors", []))
    if not initiative:
        return _next(state, "Technical Status Agent", errors=errors)

    spec = get_spec(initiative["spec_id"])
    if not spec:
        errors.append("No es posible calcular el avance técnico porque no existe el Spec asociado.")
        return _next(state, "Technical Status Agent", errors=errors)

    repository = get_repository(initiative["repository"], initiative["branch"])
    if not repository:
        errors.append("La iniciativa está registrada, pero no existe información simulada de la rama asociada.")
        return _next(state, "Technical Status Agent", errors=errors)

    result = calculate_technical_progress(spec, repository)
    return _next(
        state,
        "Technical Status Agent",
        technical_progress=result["progress"],
        technical_status=result["status"],
        technical_evidence=result["details"],
    )


# Retira el agente ejecutado de la cola y actualiza la traza del flujo.
def _next(state: InitiativeState, trace_name: str, **updates) -> dict:
    remaining = list(state.get("required_agents", []))
    if remaining:
        remaining.pop(0)
    updates["required_agents"] = remaining
    updates["execution_trace"] = state.get("execution_trace", []) + [trace_name]
    return updates


# Combina los resultados de los agentes en una sola respuesta final.
def consolidator(state: InitiativeState) -> dict:
    if state.get("errors"):
        response = "\n\n".join(state["errors"])
    else:
        sections = []
        initiative = state.get("initiative_data")
        if initiative:
            sections.append(
                f"INICIATIVA: {initiative['name']}\n"
                f"Descripción: {initiative['description']}\n"
                f"Objetivo: {initiative['objective']}\n"
                f"Alcance: {initiative['scope']}\n"
                f"Estado: {initiative['status']}\n"
                f"Ambiente: {initiative['environment']}\n"
                f"Próximo hito: {initiative['next_milestone']}\n"
                f"Responsable: {initiative['owner']}\n"
                f"Actores: {', '.join(initiative.get('actors', []))}\n"
                f"Fecha objetivo: {initiative['target_date']}"
            )

        if state.get("update_message"):
            sections.append(f"ACTUALIZACIÓN\n{state['update_message']}")

        if "technical_progress" in state:
            status = state["technical_status"]
            formula = " + ".join(
                f"{item['weight']}×{ {'completed': '1', 'partial': '0.5', 'pending': '0'}[item['status']] }"
                for item in state["technical_evidence"]
            )
            sections.append(
                f"AVANCE TÉCNICO ESTIMADO: {state['technical_progress']:.0f} %\n"
                f"Cálculo: ({formula}) / 100\n"
                f"Implementado: {_bullets(status['completed'])}\n"
                f"Parcial: {_bullets(status['partial'])}\n"
                f"Pendiente: {_bullets(status['pending'])}"
            )

        tracking = state.get("tracking_data")
        if tracking:
            sections.append(
                f"SEGUIMIENTO\nPendientes: {_bullets(tracking['pending'])}\n"
                f"Bloqueos: {_bullets(tracking['blockers'])}\n"
                f"Próximo paso: {tracking['next_step']}"
            )

        procedure = state.get("procedure_data")
        if procedure:
            sections.append(
                f"PROCEDIMIENTO: {procedure['name']}\n"
                f"Objetivo: {procedure['objective']}\n"
                f"Precondiciones: {_bullets(procedure['preconditions'])}\n"
                f"Pasos: {_numbered(procedure['steps'])}\n"
                f"Evidencias: {_bullets(procedure['evidence'])}\n"
                f"Responsable: {procedure['owner']}\n"
                f"Resultado esperado: {procedure['expected_result']}"
            )
        response = "\n\n".join(sections)

    trace = state.get("execution_trace", []) + ["Consolidator", "END"]
    mode = state.get("interpretation_mode", "Reglas determinísticas")
    response += f"\n\nMODO DE INTERPRETACIÓN\n{mode}"
    response += "\n\nRUTA LANGGRAPH\n" + " → ".join(trace)
    return {"final_response": response, "execution_trace": trace}


# Convierte una lista de textos en una lista con viñetas.
def _bullets(items: list[str]) -> str:
    return "\n" + "\n".join(f"- {item}" for item in items) if items else " Ninguno"


# Convierte una lista de textos en una lista numerada.
def _numbered(items: list[str]) -> str:
    return "\n" + "\n".join(f"{index}. {item}" for index, item in enumerate(items, 1))
