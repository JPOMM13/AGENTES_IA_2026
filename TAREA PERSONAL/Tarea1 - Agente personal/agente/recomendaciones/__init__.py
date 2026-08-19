"""Modelo de negocio utilizado por el agente de recomendaciones."""

from .catalogo import CATALOGO, COBERTURA, PESOS, calcular_utilidad
from .estado import EstadoRecomendacion, crear_estado_inicial

__all__ = [
    "CATALOGO",
    "COBERTURA",
    "PESOS",
    "calcular_utilidad",
    "EstadoRecomendacion",
    "crear_estado_inicial",
]

