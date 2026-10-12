from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from app.configuracion_llm import obtener_configuracion_llm
from app.estado import EstadoCotizacion
from app.prompts_agenticos import PROMPT_SISTEMA_CLASIFICADOR_INTENCION


IntencionClasificada = Literal[
    "saludo",
    "nueva_cotizacion",
    "retomar_previa",
    "consulta_memoria",
    "solicitud_imagen",
    "cierre",
    "derivacion_humana",
    "solicitud_descuento",
    "solicitud_pago",
    "cotizacion",
    "consulta_precio",
    "confirmacion_derivacion",
    "revisar_pedido",
    "modificar_pedido",
    "consulta_general",
    "recomendacion",
]


class ResultadoClasificacionIntencion(BaseModel):
    """Salida estructurada del router de intencion basado en LLM."""

    intencion: IntencionClasificada = Field(description="Etiqueta unica que representa la intencion principal del usuario.")
    confianza: float = Field(default=0.0, ge=0.0, le=1.0, description="Confianza de la clasificacion entre 0 y 1.")
    evidencia: str = Field(default="", description="Fragmento o resumen breve que justifica la intencion elegida.")


# CLASIFICADOR AGENTICO: interpreta lenguaje natural y devuelve una etiqueta estructurada, como en los routers del curso.
def clasificar_intencion_con_llm(mensaje_usuario: str, estado: EstadoCotizacion) -> ResultadoClasificacionIntencion | None:
    """Clasifica la intencion con salida estructurada; si falla, permite caer a reglas deterministicas."""
    if not debe_usar_clasificador_intencion():
        return None
    try:
        clasificador = obtener_clasificador_intencion()
        resultado = clasificador.invoke(
            [
                {"role": "system", "content": PROMPT_SISTEMA_CLASIFICADOR_INTENCION},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "mensaje_usuario": mensaje_usuario,
                            "estado": estado.a_diccionario_panel(),
                            "campos_faltantes": estado.campos_faltantes,
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        )
    except Exception as exc:
        estado.registrar_log("clasificador_intencion_error", {"error": str(exc)})
        return None
    estado.registrar_log(
        "clasificador_intencion_llm",
        {
            "intencion": resultado.intencion,
            "confianza": resultado.confianza,
            "evidencia": resultado.evidencia,
        },
    )
    return resultado


# CONFIGURACION AGENTICA: permite apagar la clasificacion LLM sin tocar el resto del agente.
def debe_usar_clasificador_intencion() -> bool:
    """Indica si la clasificacion estructurada por LLM esta habilitada."""
    return obtener_configuracion_llm().habilitado


# CACHE AGENTICO: reutiliza el modelo estructurado de clasificacion entre turnos.
@lru_cache(maxsize=1)
def obtener_clasificador_intencion():
    """Crea el LLM con salida estructurada para clasificar intenciones."""
    from langchain.chat_models import init_chat_model

    config = obtener_configuracion_llm()
    modelo = init_chat_model(config.modelo_langchain, temperature=0)
    return modelo.with_structured_output(ResultadoClasificacionIntencion)
