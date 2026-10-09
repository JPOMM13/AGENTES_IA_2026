from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolReadinessContract:
    """Contrato que indica que acciones puede ejecutar el agente en este turno."""
    can_answer_price: bool
    can_validate_and_recommend: bool
    can_generate_quote: bool
    can_show_image: bool

    # Ejecuta la responsabilidad de a diccionario.
    def a_diccionario(self) -> dict[str, bool]:
        """Convierte el contrato a dict para enviarlo al agente LLM."""
        return {
            "can_answer_price": self.can_answer_price,
            "can_validate_and_recommend": self.can_validate_and_recommend,
            "can_generate_quote": self.can_generate_quote,
            "can_show_image": self.can_show_image,
        }
