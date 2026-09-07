from typing import Any, TypedDict


class InitiativeState(TypedDict, total=False):
    """Datos compartidos por los nodos del grafo."""

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
    reported_progress: float
    technical_evidence: list[dict[str, Any]]
    agent_results: list[str]
    final_response: str
    errors: list[str]
    execution_trace: list[str]
    meeting_file: str
    meeting_transcription: str
    meeting_visual_evidence: list[dict[str, Any]]
    meeting_context: dict[str, Any]
