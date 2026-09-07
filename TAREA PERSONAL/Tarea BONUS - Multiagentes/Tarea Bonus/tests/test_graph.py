"""Pruebas del recorrido completo del grafo."""

from cafe_ai_agents.formatter import campaign_to_markdown
from cafe_ai_agents.graph import run_campaign
from cafe_ai_agents.agents import validator_node
from tests.fakes import FakeLLM


def test_complete_graph_follows_expected_agent_order():
    llm = FakeLLM()
    campaign = run_campaign(llm, "Crear la campaña inicial de Cafe.AI")
    assert llm.calls == [
        "CampaignBrief",
        "CreativeStrategy",
        "CopywritingResult",
        "VisualDesignResult",
    ]
    assert len(campaign.social_posts) == 3
    assert len(campaign.visual_pieces) == 3


def test_final_markdown_contains_copy_and_visual_prompt():
    campaign = run_campaign(FakeLLM(), "Crear campaña")
    markdown = campaign_to_markdown(campaign)
    assert "# Campaña: Ideas recién servidas" in markdown
    assert "### Instagram" in markdown
    assert "**Prompt visual:**" in markdown


def test_validator_requests_only_one_correction_for_unsupported_event():
    # Construimos primero una campaña válida con el modelo falso.
    campaign = run_campaign(FakeLLM(), "Crear campaña")
    state = {
        "brief": campaign.brief,
        "creative_strategy": campaign.creative_strategy.model_copy(
            update={"big_idea": "Organizar sesiones con expertos"}
        ),
        "copywriting": type("Copy", (), {"posts": campaign.social_posts})(),
        "visual_design": type("Design", (), {"pieces": campaign.visual_pieces})(),
        "validation_notes": [],
        "revision_count": 0,
    }
    result = validator_node(state)
    assert result["next_agent"] == "creative"
    assert result["revision_count"] == 1
