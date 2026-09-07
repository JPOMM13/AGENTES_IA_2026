"""Conversión de la campaña estructurada a Markdown."""

from cafe_ai_agents.models import FinalCampaign


def campaign_to_markdown(campaign: FinalCampaign) -> str:
    """Genera un documento Markdown fácil de leer y compartir."""
    strategy = campaign.creative_strategy
    lines = [
        f"# Campaña: {strategy.campaign_name}",
        "",
        "## Estrategia",
        "",
        f"- **Objetivo:** {campaign.brief.objective}",
        f"- **Público:** {', '.join(campaign.brief.audience)}",
        f"- **Gran idea:** {strategy.big_idea}",
        f"- **Eslogan:** {strategy.slogan}",
        f"- **Propuesta de valor:** {strategy.value_proposition}",
        f"- **Tono:** {', '.join(strategy.tone)}",
        "",
        "## Publicaciones y diseño",
    ]

    # Se emparejan copy y diseño por canal para facilitar la producción.
    designs = {piece.channel: piece for piece in campaign.visual_pieces}
    for post in campaign.social_posts:
        piece = designs.get(post.channel)
        lines.extend(
            [
                "",
                f"### {post.channel}",
                "",
                f"- **Objetivo:** {post.objective}",
                f"- **Gancho:** {post.hook}",
                f"- **Copy:** {post.body}",
                f"- **CTA:** {post.call_to_action}",
                f"- **Hashtags:** {' '.join(post.hashtags)}",
            ]
        )
        if piece:
            lines.extend(
                [
                    f"- **Formato:** {piece.format} ({piece.dimensions})",
                    f"- **Composición:** {piece.composition}",
                    f"- **Paleta:** {', '.join(piece.color_palette)}",
                    f"- **Tipografía:** {piece.typography}",
                    f"- **Prompt visual:** {piece.visual_prompt}",
                    f"- **Prompt negativo:** {piece.negative_prompt}",
                    f"- **Texto alternativo:** {piece.accessibility_alt_text}",
                ]
            )

    lines.extend(["", "## Calendario sugerido", ""])
    for item in campaign.publication_schedule:
        lines.append(f"- **{item.day} — {item.channel}:** {item.content}")

    lines.extend(
        [
            "",
            "## Indicadores",
            "",
            *[f"- {kpi}" for kpi in campaign.kpis],
            "",
            "## Validación",
            "",
            *[f"- {note}" for note in campaign.validation_notes],
        ]
    )
    return "\n".join(lines) + "\n"
