from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from app.contratos import ContratoDisponibilidadHerramientas
from app.guardrails.decision import (
    es_derivacion_humana_explicita,
    es_solicitud_generar_cotizacion,
    es_solicitud_nueva_cotizacion,
    es_solicitud_recuperar_memoria,
)
from app.configuracion_llm import obtener_configuracion_llm
from app.estado import EstadoCotizacion
from app.modelo_agentico import construir_modelo_chat_agentico
from app.prompts_agenticos import PROMPT_SISTEMA_DECISOR


DecisionAgente = Literal[
    "pedir_campos_faltantes",
    "responder_precio",
    "validar_y_recomendar",
    "generar_cotizacion",
    "mostrar_imagen",
    "derivacion",
    "responder_politica",
    "cierre",
    "retomar_previa",
    "nueva_cotizacion",
]


class ResultadoDecisionAgentica(BaseModel):
    """Salida estructurada del decisor LLM."""

    accion: DecisionAgente = Field(description="Accion de alto nivel que debe ejecutar el workflow.")
    confianza: float = Field(default=0.0, ge=0.0, le=1.0, description="Confianza de la decision entre 0 y 1.")
    motivo: str = Field(default="", description="Motivo breve de la accion elegida.")


# CONFIGURACION AGENTICA: valida si el decisor LLM estructurado debe activarse segun el .env.
def debe_usar_decisor_estructurado() -> bool:
    """Indica si la decision estructurada por LLM esta habilitada."""
    return obtener_configuracion_llm().habilitado


# COMPATIBILIDAD INTERNA: mantiene el nombre usado por el extractor sin cambiar su comportamiento.
def debe_usar_create_agent() -> bool:
    """Indica si la capa LLM agentica esta habilitada."""
    return debe_usar_decisor_estructurado()


# DECISOR LLM ESTRUCTURADO: interpreta la intencion del usuario y propone una accion, sin ejecutar negocio directamente.
def decidir_siguiente_accion_con_agente(mensaje_usuario: str, estado: EstadoCotizacion) -> DecisionAgente | None:
    """Usa salida estructurada del LLM para decidir accion; si falla, permite fallback deterministico."""
    if not debe_usar_decisor_estructurado():
        return None
    try:
        disponibilidad = obtener_disponibilidad_tools(mensaje_usuario, estado)
        decisor = obtener_decisor_estructurado()
        resultado = decisor.invoke(
            [
                {"role": "system", "content": PROMPT_SISTEMA_DECISOR},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "mensaje_usuario": mensaje_usuario,
                            "estado": estado.a_diccionario_panel(),
                            "campos_faltantes": estado.campos_faltantes,
                            "disponibilidad_herramientas": disponibilidad,
                            "solicito_derivar": es_solicitud_derivacion_explicita(mensaje_usuario),
                            "solicito_recuperar_memoria": es_solicitud_recuperar_memoria(mensaje_usuario.lower()),
                            "solicito_empezar_otro_pedido": es_solicitud_nueva_cotizacion(mensaje_usuario.lower()),
                            "solicito_emitir_propuesta": es_solicitud_generar_cotizacion(mensaje_usuario.lower(), estado),
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        )
    except Exception as exc:
        estado.registrar_log("decision_agentica_error", {"agente": "decisor_estructurado", "error": str(exc)})
        return None
    estado.registrar_log(
        "decision_agentica_llm",
        {
            "accion": resultado.accion,
            "confianza": resultado.confianza,
            "motivo": resultado.motivo,
        },
    )
    return resultado.accion


# CACHE AGENTICO: reutiliza el modelo estructurado del decisor para no recrearlo en cada interaccion.
@lru_cache(maxsize=1)
def obtener_decisor_estructurado():
    """Crea el LLM con salida estructurada para decidir la siguiente accion."""
    config = obtener_configuracion_llm()
    modelo = construir_modelo_chat_agentico(config)
    return modelo.with_structured_output(ResultadoDecisionAgentica)


# CONTRATO DE TOOLS / VALIDACION PREVIA: informa al agente que herramientas puede pedir segun datos ya capturados.
def obtener_disponibilidad_tools(mensaje_usuario: str, estado: EstadoCotizacion) -> dict[str, bool]:
    """Calcula prerequisitos para que el agente sepa que tools puede usar."""
    texto = mensaje_usuario.lower()
    tiene_referencia_producto_o_paquete = any(
        term in texto
        for term in [
            "cerveza",
            "vino",
            "gaseosa",
            "hielo",
            "bartender",
            "bar movil",
            "bar móvil",
            "paquete",
        ]
    )
    tiene_minimo_para_recomendacion = not estado.campos_faltantes
    tiene_recomendacion = estado.opcion_recomendada is not None
    tiene_cotizacion = estado.cotizacion is not None
    return ContratoDisponibilidadHerramientas(
        puede_responder_precio=tiene_referencia_producto_o_paquete or tiene_recomendacion,
        puede_validar_y_recomendar=tiene_minimo_para_recomendacion,
        puede_generar_cotizacion=tiene_minimo_para_recomendacion and tiene_recomendacion,
        puede_mostrar_imagen=tiene_cotizacion,
    ).a_diccionario()


# VALIDACION DE DERIVACION HUMANA: confirma que la derivacion fue solicitada explicitamente por el usuario.
def es_solicitud_derivacion_explicita(message: str) -> bool:
    """Detecta si el usuario pidio de forma explicita derivacion humana."""
    return es_derivacion_humana_explicita(message.lower())
