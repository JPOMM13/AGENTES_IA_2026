from typing import Any, TypedDict


# Define los datos compartidos y actualizados por todos los nodos del grafo.
class InitiativeState(TypedDict, total=False):
    user_query: str
    initiative_name: str | None
    intent: str
    interpretation_mode: str
    actor_name: str | None
    update_message: str
    required_agents: list[str]
    initiative_data: dict[str, Any]
    procedure_data: dict[str, Any]
    tracking_data: dict[str, Any]
    technical_status: dict[str, list[str]]
    technical_progress: float
    technical_evidence: list[dict[str, Any]]
    agent_results: list[str]
    final_response: str
    errors: list[str]
    execution_trace: list[str]
