from __future__ import annotations

import os
from typing import Any

from app.configuracion_llm import ConfiguracionLLM


# CONFIGURACION AGENTICA: construye el modelo compartido para clasificador, extractor y decisor.
def construir_modelo_chat_agentico(config: ConfiguracionLLM) -> Any:
    """Crea el chat model con timeout y reintentos acotados para evitar turnos lentos."""
    from langchain.chat_models import init_chat_model

    parametros: dict[str, Any] = {
        "temperature": 0,
        "timeout": config.segundos_timeout,
        "max_retries": 1,
    }
    if config.clave_api:
        parametros["api_key"] = config.clave_api
    return init_chat_model(config.modelo_langchain, **parametros)


# CONFIGURACION AGENTICA: permite comparar retorno directo contra el comportamiento anterior.
def debe_usar_retorno_directo_agentico() -> bool:
    """Indica si las tools internas de create_agent deben cortar el loop al responder."""
    return os.getenv("AGENTE_RETURN_DIRECT", "true").strip().lower() in {"1", "true", "yes", "si", "sí"}


# CONFIGURACION AGENTICA: limita la recursion del grafo interno creado por create_agent.
def obtener_limite_recursion_agentica() -> int:
    """Lee el limite de recursion para create_agent y aplica un valor seguro por defecto."""
    valor = os.getenv("GUARDRAIL_LLM_RECURSION_LIMIT", "6").strip()
    return int(valor) if valor.isdigit() and int(valor) > 0 else 6


# CONFIGURACION AGENTICA: arma la configuracion que se pasa a agent.invoke.
def construir_config_invocacion_agentica() -> dict[str, int]:
    """Devuelve la configuracion de invocacion del agente LangGraph interno."""
    return {"recursion_limit": obtener_limite_recursion_agentica()}
