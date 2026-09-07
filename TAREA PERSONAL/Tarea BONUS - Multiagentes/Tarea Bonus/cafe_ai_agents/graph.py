"""Construcción del flujo multiagente con LangGraph."""

from langgraph.graph import END, START, StateGraph

from cafe_ai_agents.agents import (
    create_copywriter_node,
    create_creative_node,
    create_designer_node,
    create_router_node,
    validator_node,
)
from cafe_ai_agents.models import CampaignState, FinalCampaign


def build_graph(llm):
    """Construye y compila el grafo usando el modelo recibido."""
    builder = StateGraph(CampaignState)

    # Cada integrante del equipo se representa como un nodo independiente.
    builder.add_node("router", create_router_node(llm))
    builder.add_node("creative", create_creative_node(llm))
    builder.add_node("copywriter", create_copywriter_node(llm))
    builder.add_node("designer", create_designer_node(llm))
    builder.add_node("validator", validator_node)

    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        lambda state: state["next_agent"],
        {
            "creative": "creative",
            "copywriter": "copywriter",
            "designer": "designer",
            "validator": "validator",
            "end": END,
        },
    )

    # Los especialistas y el validador siempre devuelven el control al enrutador.
    builder.add_edge("creative", "router")
    builder.add_edge("copywriter", "router")
    builder.add_edge("designer", "router")
    builder.add_edge("validator", "router")
    return builder.compile()


def run_campaign(llm, user_request: str, verbose: bool = False) -> FinalCampaign:
    """Ejecuta una campaña completa y devuelve su resultado validado."""
    graph = build_graph(llm)
    initial_state: CampaignState = {
        "messages": [{"role": "user", "content": user_request}],
        "user_request": user_request,
        "brief": None,
        "creative_strategy": None,
        "copywriting": None,
        "visual_design": None,
        "validation_notes": [],
        "revision_count": 0,
        "next_agent": "router",
        "final_campaign": None,
        "verbose": verbose,
    }
    result = graph.invoke(initial_state, config={"recursion_limit": 20})
    return result["final_campaign"]
