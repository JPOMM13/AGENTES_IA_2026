"""Contratos de datos compartidos por los agentes."""

from typing import Annotated, Literal

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class CampaignBrief(BaseModel):
    """Brief que el enrutador extrae de la solicitud."""

    objective: str
    audience: list[str]
    channels: list[str] = Field(default_factory=lambda: ["Instagram", "TikTok", "LinkedIn"])
    tone: list[str] = Field(default_factory=lambda: ["innovador", "cercano", "optimista"])
    constraints: list[str] = Field(default_factory=list)


class CreativeStrategy(BaseModel):
    """Concepto rector producido por el agente creativo."""

    campaign_name: str
    insight: str
    value_proposition: str
    big_idea: str
    slogan: str
    tone: list[str]
    content_pillars: list[str]


class SocialPost(BaseModel):
    """Copy completo para una red social."""

    channel: Literal["Instagram", "TikTok", "LinkedIn"]
    objective: str
    hook: str
    body: str
    call_to_action: str
    hashtags: list[str]


class CopywritingResult(BaseModel):
    """Agrupa las tres publicaciones de la campaña."""

    posts: list[SocialPost]


class VisualPiece(BaseModel):
    """Instrucciones para producir una pieza visual, sin crear la imagen."""

    channel: Literal["Instagram", "TikTok", "LinkedIn"]
    format: str
    dimensions: str
    composition: str
    color_palette: list[str]
    typography: str
    visual_prompt: str
    negative_prompt: str
    accessibility_alt_text: str


class VisualDesignResult(BaseModel):
    """Agrupa las tres propuestas visuales."""

    pieces: list[VisualPiece]


class PublicationItem(BaseModel):
    """Momento sugerido para publicar una pieza."""

    day: str
    channel: str
    content: str


class FinalCampaign(BaseModel):
    """Entrega consolidada que recibe el usuario."""

    brief: CampaignBrief
    creative_strategy: CreativeStrategy
    social_posts: list[SocialPost]
    visual_pieces: list[VisualPiece]
    publication_schedule: list[PublicationItem]
    kpis: list[str]
    validation_notes: list[str]


class CampaignState(TypedDict, total=False):
    """Memoria compartida que LangGraph pasa de nodo en nodo."""

    messages: Annotated[list, add_messages]
    user_request: str
    brief: CampaignBrief | None
    creative_strategy: CreativeStrategy | None
    copywriting: CopywritingResult | None
    visual_design: VisualDesignResult | None
    validation_notes: list[str]
    revision_count: int
    next_agent: str
    final_campaign: FinalCampaign | None
    verbose: bool
