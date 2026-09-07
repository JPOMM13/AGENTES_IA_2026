import re

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
    update_initiative_from_meeting,
)


# Interpreta la consulta con el LLM y usa reglas si el modelo no está disponible.
def supervisor(state: InitiativeState) -> dict:
    if _is_meeting_update(state):
        return _meeting_update_route(state)

    # La ruta multimodal se detecta antes del LLM para aceptar rutas de archivo libres.
    if _is_meeting_query(state):
        return _meeting_route(state)

    llm_analysis = analyze_with_llm(state["user_query"])

    if llm_analysis:
        return _supervisor_from_llm(state, llm_analysis)

    return _supervisor_with_rules(state)


def _is_meeting_update(state: InitiativeState) -> bool:
    query = normalize(state["user_query"])
    return bool(state.get("meeting_context")) and "actualiza" in query and any(
        word in query for word in ["video", "reunion", "iniciativa"]
    )


def _meeting_update_route(state: InitiativeState) -> dict:
    initiative = get_initiative(state["user_query"])
    if not initiative:
        initiative = get_initiative(state.get("initiative_name") or "")
    if not initiative:
        meeting_name = state.get("meeting_context", {}).get("initiative", "")
        initiative = get_initiative(meeting_name)
    return {
        "initiative_name": initiative["name"] if initiative else None,
        "intent": "actualizar_desde_reunion",
        "interpretation_mode": "Orden explícita del usuario",
        "required_agents": ["update"],
        "errors": [],
        "execution_trace": ["Supervisor (actualización desde reunión)"],
        "agent_results": [],
    }


def _is_meeting_query(state: InitiativeState) -> bool:
    query = normalize(state["user_query"])
    meeting_words = [
        "reunion", "video", "pantalla", "security scan", "cab", "se acordo",
        "quedo pendiente", "informacion aparecio", "ultima reunion",
    ]
    has_video = any(extension in state["user_query"].lower() for extension in [".mp4", ".mov"])
    return has_video or any(
        word in query for word in meeting_words
    )


def _meeting_route(state: InitiativeState) -> dict:
    match = re.search(
        r'(?:["\']([^"\']+\.(?:mp4|mov))["\']|(\S+\.(?:mp4|mov)))',
        state["user_query"],
        re.IGNORECASE,
    )
    meeting_file = next((group for group in match.groups() if group), "") if match else state.get("meeting_file", "")
    initiative = get_initiative(state["user_query"])
    query = normalize(state["user_query"])
    asks_combined_status = initiative and any(
        phrase in query for phrase in ["como va", "estado", "considerando"]
    )
    agents = ["initiative", "tracking", "technical", "meeting"] if asks_combined_status else ["meeting"]
    return {
        "initiative_name": initiative["name"] if initiative else None,
        "intent": "reunion_multimodal",
        "meeting_file": meeting_file,
        "interpretation_mode": "Reglas determinísticas",
        "required_agents": agents,
        "errors": [],
        "execution_trace": ["Supervisor (reunión multimodal)"],
        "agent_results": [],
    }


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
    if state.get("intent") == "actualizar_desde_reunion":
        message = update_initiative_from_meeting(
            state.get("initiative_name"), state.get("meeting_context", {})
        )
        return _next(state, "Update Agent (reunión)", update_message=message)

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
    initiative = get_initiative(state["initiative_name"] or "")
    if data and initiative:
        data = dict(data)
        data["meeting_pending"] = initiative.get("meeting_pending", [])
        data["meeting_risks"] = initiative.get("meeting_risks", [])
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
    updates = {
        "technical_progress": result["progress"],
        "technical_status": result["status"],
        "technical_evidence": result["details"],
    }
    if initiative.get("progress_percentage") is not None:
        updates["reported_progress"] = initiative["progress_percentage"]
    return _next(state, "Technical Status Agent", **updates)


def meeting_agent(state: InitiativeState) -> dict:
    """Procesa un MP4/MOV nuevo o consulta el contexto temporal ya cargado."""
    meeting_file = state.get("meeting_file", "")
    has_video = any(extension in state["user_query"].lower() for extension in [".mp4", ".mov"])
    if meeting_file and has_video:
        try:
            from src.multimodal import process_meeting

            transcription, evidence, context = process_meeting(meeting_file)
            return _next(
                state,
                "Meeting Agent (audio + video)",
                meeting_transcription=transcription,
                meeting_visual_evidence=evidence,
                meeting_context=context,
            )
        except Exception as error:
            errors = list(state.get("errors", []))
            errors.append(f"No pude procesar la reunión: {error}")
            return _next(state, "Meeting Agent", errors=errors)

    if state.get("meeting_context"):
        return _next(state, "Meeting Agent (contexto de sesión)")

    # Permite consultar una reunión confirmada incluso después de reiniciar.
    initiative = get_initiative(state.get("initiative_name") or state["user_query"])
    if initiative and initiative.get("last_meeting_update"):
        return _next(
            state,
            "Meeting Agent (actualización guardada)",
            meeting_context=initiative["last_meeting_update"],
        )
    saved = [item for item in load_json("initiatives.json") if item.get("last_meeting_update")]
    if len(saved) == 1:
        return _next(
            state,
            "Meeting Agent (actualización guardada)",
            initiative_name=saved[0]["name"],
            meeting_context=saved[0]["last_meeting_update"],
        )

    errors = list(state.get("errors", []))
    errors.append("Primero procesa una reunión indicando la ruta de un archivo MP4 o MOV.")
    return _next(state, "Meeting Agent", errors=errors)


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
            initiative_text = (
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
            if initiative.get("priority"):
                initiative_text += f"\nPrioridad: {initiative['priority']}"
            saved_meeting = initiative.get("last_meeting_update")
            if saved_meeting:
                initiative_text += (
                    "\nActualización de reunión guardada: Sí"
                    f"\nAvance reportado en reunión: {initiative.get('progress_percentage', 'No indicado')} %"
                    f"\nAcuerdos de la reunión: {_bullets(saved_meeting.get('agreements', []))}"
                    f"\nPendientes de la reunión: {_bullets(saved_meeting.get('pending', []))}"
                    f"\nRiesgos de la reunión: {_bullets(saved_meeting.get('risks', []))}"
                    f"\nResponsables mencionados: {_bullets(saved_meeting.get('responsibles', []))}"
                    f"\nEquipos mencionados: {_bullets(saved_meeting.get('actors', []))}"
                    f"\nInformación técnica de la reunión: "
                    f"{_bullets(saved_meeting.get('technical_information', []))}"
                )
            sections.append(initiative_text)

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
            if "reported_progress" in state:
                sections.append(
                    f"AVANCE REPORTADO EN LA ÚLTIMA REUNIÓN: {state['reported_progress']:.0f} %\n"
                    "Fuente: reunión guardada. Se muestra separado del cálculo técnico de los JSON."
                )

        tracking = state.get("tracking_data")
        if tracking:
            tracking_text = (
                f"SEGUIMIENTO\nPendientes: {_bullets(tracking['pending'])}\n"
                f"Bloqueos: {_bullets(tracking['blockers'])}\n"
                f"Próximo paso: {tracking['next_step']}"
            )
            if tracking.get("meeting_pending"):
                tracking_text += f"\nPendientes reportados en reunión: {_bullets(tracking['meeting_pending'])}"
            if tracking.get("meeting_risks"):
                tracking_text += f"\nRiesgos reportados en reunión: {_bullets(tracking['meeting_risks'])}"
            sections.append(tracking_text)

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

        meeting = state.get("meeting_context")
        if meeting and state.get("intent") == "reunion_multimodal":
            sections.append(_meeting_section(state))
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


def _meeting_section(state: InitiativeState) -> str:
    context = state["meeting_context"]
    lines = ["CONTEXTO DE LA REUNIÓN"]
    if context.get("initiative"):
        lines.append(f"Iniciativa: {context['initiative']}")
    labels = {
        "dates": "Fechas", "responsibles": "Responsables", "actors": "Equipos/actores",
        "agreements": "Acuerdos",
        "pending": "Pendientes", "risks": "Riesgos",
        "technical_information": "Información técnica",
    }
    for field, label in labels.items():
        if context.get(field):
            lines.append(f"{label}: {_bullets(context[field])}")

    lines.append("FUENTES")
    for source, facts in context.get("sources", {}).items():
        found = [item for field in labels for item in facts.get(field, [])]
        scalar_labels = {
            "status": "Estado", "progress_percentage": "Avance", "target_date": "Fecha objetivo",
            "next_milestone": "Próximo hito", "owner": "Responsable", "priority": "Prioridad",
            "description": "Descripción", "objective": "Objetivo", "scope": "Alcance",
            "repository": "Repositorio", "branch": "Rama", "environment": "Ambiente",
        }
        found += [
            f"{label}: {facts[field]}" for field, label in scalar_labels.items()
            if facts.get(field) not in (None, "")
        ]
        if found:
            lines.append(f"{source.capitalize()}: {_bullets(found)}")

    if state.get("meeting_transcription"):
        lines.append(f"Transcripción: {state['meeting_transcription']}")
    if state.get("meeting_visual_evidence"):
        visual = [f"Segundo {item['second']}: {item['analysis']}" for item in state["meeting_visual_evidence"]]
        lines.append(f"Frames analizados: {_bullets(visual)}")
    lines.append("Los datos de la reunión complementan los JSON; no los sobrescriben.")
    return "\n".join(lines)
