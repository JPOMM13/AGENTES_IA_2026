from langgraph.graph import END, START, StateGraph

from src.agents import (
    consolidator,
    initiative_agent,
    procedure_agent,
    supervisor,
    technical_agent,
    tracking_agent,
    update_agent,
)
from src.state import InitiativeState


# Selecciona el siguiente agente pendiente o envía el flujo al consolidador.
def route_next_agent(state: InitiativeState) -> str:
    agents = state.get("required_agents", [])
    return agents[0] if agents else "consolidator"


# Construye y compila el workflow multiagente de LangGraph.
def build_graph():
    builder = StateGraph(InitiativeState)
    builder.add_node("supervisor", supervisor)
    builder.add_node("initiative", initiative_agent)
    builder.add_node("procedure", procedure_agent)
    builder.add_node("tracking", tracking_agent)
    builder.add_node("technical", technical_agent)
    builder.add_node("consolidator", consolidator)
    builder.add_node("update", update_agent)

    builder.add_edge(START, "supervisor")
    routes = {
        "initiative": "initiative",
        "procedure": "procedure",
        "tracking": "tracking",
        "technical": "technical",
        "consolidator": "consolidator",
        "update": "update",
    }
    builder.add_conditional_edges("supervisor", route_next_agent, routes)
    for agent in ["initiative", "procedure", "tracking", "technical", "update"]:
        builder.add_conditional_edges(agent, route_next_agent, routes)
    builder.add_edge("consolidator", END)
    return builder.compile()


graph = build_graph()


# Ejecuta una pregunta en el grafo y devuelve la respuesta consolidada.
def ask(question: str, show_trace: bool = True) -> str:
    result = graph.invoke({"user_query": question})
    if show_trace:
        print(result["final_response"])
    return result["final_response"]


if __name__ == "__main__":
    print("Escribe 'salir' para terminar.")
    while True:
        question = input("\nPregunta: ").strip()
        if question.lower() == "salir":
            break
        ask(question)
