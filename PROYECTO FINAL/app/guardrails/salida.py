from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.estado import EstadoCotizacion


@dataclass(frozen=True)
class ResultadoGuardrailSalida:
    """Resultado estandar para validar salidas del agente o respuesta final."""

    permitido: bool
    motivo: str
    respuesta_segura: str = ""


# Ejecuta la responsabilidad de validar salida agente.
def validar_salida_agente(resultado: Any, nombre_agente: str) -> ResultadoGuardrailSalida:
    """Valida que create_agent devuelva una estructura minima consumible."""
    if not isinstance(resultado, dict):
        return ResultadoGuardrailSalida(False, f"{nombre_agente}: salida no es diccionario")
    mensajes = resultado.get("messages")
    if not isinstance(mensajes, list) or not mensajes:
        return ResultadoGuardrailSalida(False, f"{nombre_agente}: salida sin mensajes")
    return ResultadoGuardrailSalida(True, f"{nombre_agente}: salida valida")


# Ejecuta la responsabilidad de asegurar respuesta final.
def asegurar_respuesta_final(respuesta: str, estado: EstadoCotizacion) -> str:
    """Evita respuestas vacias y refuerza reglas criticas antes de responder."""
    if not respuesta.strip():
        return "No pude generar una respuesta segura para este turno. Repiteme el dato y lo reviso sin asumir informacion."
    if estado.intencion != "human_handoff" and estado.derivacion_confirmada and "whatsapp" in respuesta.lower():
        return "Para derivarte por WhatsApp necesito que lo solicites explicitamente. Mientras tanto puedo continuar con la cotizacion."
    return respuesta
