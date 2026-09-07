"""Modelo falso para probar el grafo sin conectarse con Ollama."""

from cafe_ai_agents.models import (
    CampaignBrief,
    CopywritingResult,
    CreativeStrategy,
    VisualDesignResult,
)


class FakeStructuredModel:
    """Devuelve una respuesta predecible según el esquema solicitado."""

    def __init__(self, parent, schema):
        self.parent = parent
        self.schema = schema

    def invoke(self, messages):
        self.parent.calls.append(self.schema.__name__)
        if self.schema is CampaignBrief:
            return CampaignBrief(
                objective="Lanzar Cafe.AI en redes sociales",
                audience=["desarrolladores", "creadores", "trabajadores remotos"],
                channels=["Instagram", "TikTok", "LinkedIn"],
                tone=["innovador", "cercano", "optimista"],
                constraints=["No inventar promociones"],
            )
        if self.schema is CreativeStrategy:
            return CreativeStrategy(
                campaign_name="Ideas recién servidas",
                insight="Las mejores ideas nacen durante una buena conversación.",
                value_proposition="Un espacio para crear con café y comunidad.",
                big_idea="Servir café e ideas en la misma mesa.",
                slogan="Ideas recién servidas",
                tone=["innovador", "cercano"],
                content_pillars=["café", "creatividad", "comunidad"],
            )
        if self.schema is CopywritingResult:
            return CopywritingResult(
                posts=[
                    self.parent.post(channel) for channel in ["Instagram", "TikTok", "LinkedIn"]
                ]
            )
        if self.schema is VisualDesignResult:
            return VisualDesignResult(
                pieces=[
                    self.parent.piece(channel) for channel in ["Instagram", "TikTok", "LinkedIn"]
                ]
            )
        raise AssertionError(f"Esquema no preparado: {self.schema}")


class FakeLLM:
    """Imita el método with_structured_output usado por ChatOllama."""

    def __init__(self):
        self.calls: list[str] = []

    def with_structured_output(self, schema):
        return FakeStructuredModel(self, schema)

    @staticmethod
    def post(channel):
        from cafe_ai_agents.models import SocialPost

        return SocialPost(
            channel=channel,
            objective="Dar a conocer Cafe.AI",
            hook="Tu próxima idea empieza con una taza.",
            body=f"Descubre Cafe.AI en {channel}.",
            call_to_action="Conoce nuestro espacio.",
            hashtags=["#CafeAI", "#IdeasConCafe"],
        )

    @staticmethod
    def piece(channel):
        from cafe_ai_agents.models import VisualPiece

        return VisualPiece(
            channel=channel,
            format="Publicación vertical",
            dimensions="1080x1350 px",
            composition="Taza en primer plano y personas colaborando al fondo.",
            color_palette=["café", "crema", "azul eléctrico"],
            typography="Sans serif moderna",
            visual_prompt="Café tecnológico acogedor, luz cálida, taza en primer plano.",
            negative_prompt="Texto ilegible, logotipos deformes, ambiente oscuro.",
            accessibility_alt_text="Taza de café frente a personas trabajando juntas.",
        )
