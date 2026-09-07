"""Nodos que representan a los integrantes del equipo publicitario."""

import json
from collections.abc import Callable

from cafe_ai_agents.models import (
    CampaignBrief,
    CampaignState,
    CopywritingResult,
    CreativeStrategy,
    FinalCampaign,
    PublicationItem,
    VisualDesignResult,
)
from cafe_ai_agents.prompts import (
    COPYWRITER_PROMPT,
    CREATIVE_PROMPT,
    DESIGNER_PROMPT,
    ROUTER_PROMPT,
)


def _show_progress(state: CampaignState, text: str) -> None:
    """Muestra el avance solo cuando la interfaz activa el modo detallado."""
    if state.get("verbose", False):
        print(text)


def _invoke_structured(llm, schema, system_prompt: str, payload: dict):
    """Invoca el modelo y obliga a que la respuesta cumpla un modelo Pydantic."""
    structured_llm = llm.with_structured_output(schema)
    return structured_llm.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
    )


def create_router_node(llm) -> Callable[[CampaignState], dict]:
    """Crea el nodo que prepara el brief y selecciona la siguiente especialidad."""

    def router(state: CampaignState) -> dict:
        _show_progress(state, "[ENRUTADOR] Revisando el estado de la campaña...")

        # Si el validador pidió una corrección, respetamos esa ruta concreta.
        requested_revision = state.get("next_agent")
        if state.get("validation_notes") and requested_revision in {
            "creative", "copywriter", "designer"
        }:
            return {"next_agent": requested_revision}

        # El brief solo se construye una vez, a partir de la solicitud original.
        if not state.get("brief"):
            brief = _invoke_structured(
                llm,
                CampaignBrief,
                ROUTER_PROMPT,
                {"solicitud": state["user_request"]},
            )
            return {"brief": brief, "next_agent": "creative"}

        # La presencia de cada resultado determina el siguiente paso del flujo.
        if not state.get("creative_strategy"):
            return {"next_agent": "creative"}
        if not state.get("copywriting"):
            return {"next_agent": "copywriter"}
        if not state.get("visual_design"):
            return {"next_agent": "designer"}
        if state.get("final_campaign"):
            return {"next_agent": "end"}
        return {"next_agent": "validator"}

    return router


def create_creative_node(llm) -> Callable[[CampaignState], dict]:
    """Crea el nodo que define la estrategia creativa."""

    def creative_agent(state: CampaignState) -> dict:
        _show_progress(state, "[CREATIVO] Construyendo el concepto rector...")
        strategy = _invoke_structured(
            llm,
            CreativeStrategy,
            CREATIVE_PROMPT,
            {
                "brief": state["brief"].model_dump(),
                "observaciones": state.get("validation_notes", []),
            },
        )
        # Al corregir creatividad se invalidan las piezas que dependían de ella.
        is_revision = bool(state.get("validation_notes"))
        updates = {
            "creative_strategy": strategy,
            "validation_notes": [],
            "next_agent": "router",
        }
        if is_revision:
            updates.update({"copywriting": None, "visual_design": None})
        return updates

    return creative_agent


def create_copywriter_node(llm) -> Callable[[CampaignState], dict]:
    """Crea el nodo que redacta una publicación para cada canal."""

    def copywriter_agent(state: CampaignState) -> dict:
        _show_progress(state, "[REDACTOR] Escribiendo los copys para redes...")
        copywriting = _invoke_structured(
            llm,
            CopywritingResult,
            COPYWRITER_PROMPT,
            {
                "brief": state["brief"].model_dump(),
                "estrategia": state["creative_strategy"].model_dump(),
                "observaciones": state.get("validation_notes", []),
            },
        )
        # Si cambian los copys, el diseño anterior ya no es confiable.
        is_revision = bool(state.get("validation_notes"))
        updates = {
            "copywriting": copywriting,
            "validation_notes": [],
            "next_agent": "router",
        }
        if is_revision:
            updates["visual_design"] = None
        return updates

    return copywriter_agent


def create_designer_node(llm) -> Callable[[CampaignState], dict]:
    """Crea el nodo que transforma estrategia y copys en instrucciones visuales."""

    def designer_agent(state: CampaignState) -> dict:
        _show_progress(state, "[DISEÑADOR] Preparando dirección de arte y prompts...")
        design = _invoke_structured(
            llm,
            VisualDesignResult,
            DESIGNER_PROMPT,
            {
                "brief": state["brief"].model_dump(),
                "estrategia": state["creative_strategy"].model_dump(),
                "publicaciones": state["copywriting"].model_dump(),
                "observaciones": state.get("validation_notes", []),
            },
        )
        return {
            "visual_design": design,
            "validation_notes": [],
            "next_agent": "router",
        }

    return designer_agent


def _validate_campaign(state: CampaignState) -> tuple[list[str], str]:
    """Aplica reglas simples y devuelve observaciones junto con el agente corrector."""
    notes: list[str] = []
    target = "designer"
    required_channels = {"Instagram", "TikTok", "LinkedIn"}

    strategy = state.get("creative_strategy")
    copywriting = state.get("copywriting")
    design = state.get("visual_design")

    if not strategy or not strategy.slogan or not strategy.big_idea:
        notes.append("La estrategia necesita una gran idea y un eslogan claros.")
        target = "creative"
    elif any(
        term in f"{strategy.big_idea} {strategy.value_proposition}".lower()
        for term in ["evento", "sesión", "sesiones", "expertos", "mentores", "reservas"]
    ):
        # Cafe.AI no confirmó eventos ni servicios organizados en el brief base.
        notes.append(
            "La estrategia inventa eventos o servicios. Reformularla como una idea comunicacional."
        )
        target = "creative"

    post_channels = {post.channel for post in copywriting.posts} if copywriting else set()
    if not copywriting or len(copywriting.posts) != 3 or post_channels != required_channels:
        notes.append("Debe existir exactamente una publicación por canal requerido.")
        target = "copywriter"
    elif any(not post.call_to_action.strip() for post in copywriting.posts):
        notes.append("Cada publicación debe incluir un llamado a la acción.")
        target = "copywriter"
    elif any(
        term in f"{post.body} {post.call_to_action}".lower()
        for post in copywriting.posts
        for term in ["regístrate", "registrate", "reserva", "descuento", "promoción"]
    ):
        notes.append("Los copys incluyen una acción o promoción no confirmada en el brief.")
        target = "copywriter"

    visual_channels = {piece.channel for piece in design.pieces} if design else set()
    if not design or len(design.pieces) != 3 or visual_channels != required_channels:
        notes.append("Debe existir exactamente una propuesta visual por canal.")
        target = "designer"
    elif any(not piece.visual_prompt.strip() for piece in design.pieces):
        notes.append("Cada pieza debe tener un prompt visual completo.")
        target = "designer"
    elif any(not piece.accessibility_alt_text.strip() for piece in design.pieces):
        notes.append("Cada pieza debe incluir un texto alternativo accesible.")
        target = "designer"

    return notes, target


def _build_final_campaign(state: CampaignState, notes: list[str]) -> FinalCampaign:
    """Consolida todos los resultados en el contrato final."""
    schedule = [
        PublicationItem(day="Día 1", channel="Instagram", content="Presentación del concepto"),
        PublicationItem(day="Día 3", channel="TikTok", content="Experiencia Cafe.AI"),
        PublicationItem(day="Día 5", channel="LinkedIn", content="Comunidad y trabajo creativo"),
    ]
    return FinalCampaign(
        brief=state["brief"],
        creative_strategy=state["creative_strategy"],
        social_posts=state["copywriting"].posts,
        visual_pieces=state["visual_design"].pieces,
        publication_schedule=schedule,
        kpis=["Alcance", "Interacciones", "Clics", "Guardados", "Visitas al local"],
        validation_notes=notes or ["Campaña validada correctamente."],
    )


def validator_node(state: CampaignState) -> dict:
    """Valida la campaña, solicita una corrección como máximo y luego consolida."""
    _show_progress(state, "[VALIDADOR] Comprobando coherencia y campos obligatorios...")
    notes, target = _validate_campaign(state)
    revision_count = state.get("revision_count", 0)

    # Solo se permite una vuelta de corrección para impedir ciclos infinitos.
    if notes and revision_count < 1:
        return {
            "validation_notes": notes,
            "revision_count": revision_count + 1,
            "next_agent": target,
        }

    final_campaign = _build_final_campaign(state, notes)
    return {
        "validation_notes": notes,
        "final_campaign": final_campaign,
        "next_agent": "end",
    }
