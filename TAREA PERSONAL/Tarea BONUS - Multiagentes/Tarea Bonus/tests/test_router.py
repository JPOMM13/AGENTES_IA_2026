"""Pruebas de decisiones del enrutador."""

from cafe_ai_agents.agents import create_router_node
from tests.fakes import FakeLLM


def test_router_creates_brief_and_routes_to_creative():
    llm = FakeLLM()
    router = create_router_node(llm)
    result = router({"user_request": "Lanzar Cafe.AI", "brief": None})
    assert result["next_agent"] == "creative"
    assert result["brief"].objective


def test_router_respects_revision_requested_by_validator():
    llm = FakeLLM()
    router = create_router_node(llm)
    result = router(
        {
            "user_request": "Lanzar Cafe.AI",
            "validation_notes": ["Corregir CTA"],
            "next_agent": "copywriter",
        }
    )
    assert result == {"next_agent": "copywriter"}
