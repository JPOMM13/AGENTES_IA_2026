from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContratoDisponibilidadHerramientas:
    """Contrato que indica que acciones puede ejecutar el agente en este turno."""
    puede_responder_precio: bool
    puede_validar_y_recomendar: bool
    puede_generar_cotizacion: bool
    puede_mostrar_imagen: bool

    # CONTRATO DE TOOLS: expone prerequisitos en formato dict para que el agente decisor los consuma.
    def a_diccionario(self) -> dict[str, bool]:
        """Convierte el contrato a dict para enviarlo al agente LLM."""
        return {
            "puede_responder_precio": self.puede_responder_precio,
            "puede_validar_y_recomendar": self.puede_validar_y_recomendar,
            "puede_generar_cotizacion": self.puede_generar_cotizacion,
            "puede_mostrar_imagen": self.puede_mostrar_imagen,
        }
