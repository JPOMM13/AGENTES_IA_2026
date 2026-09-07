"""Pruebas de los contratos de datos."""

import pytest
from pydantic import ValidationError

from cafe_ai_agents.models import CampaignBrief, SocialPost


def test_brief_uses_default_channels_and_tone():
    # Los valores por defecto mantienen útil un brief mínimo.
    brief = CampaignBrief(objective="Lanzar Cafe.AI", audience=["creadores"])
    assert brief.channels == ["Instagram", "TikTok", "LinkedIn"]
    assert brief.tone == ["innovador", "cercano", "optimista"]


def test_social_post_rejects_unknown_channel():
    # Literal evita que el modelo entregue canales fuera del alcance acordado.
    with pytest.raises(ValidationError):
        SocialPost(
            channel="Facebook",
            objective="Prueba",
            hook="Gancho",
            body="Texto",
            call_to_action="Visítanos",
            hashtags=[],
        )
