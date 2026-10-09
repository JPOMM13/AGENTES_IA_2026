from __future__ import annotations

import os

from app.llm_config import cargar_archivo_env


# RESUMEN: ESTE MODULO CENTRALIZA LA CONFIGURACION DE OBSERVABILIDAD.
# RESUMEN: SI LANGSMITH_TRACING=true Y EXISTE LANGSMITH_API_KEY, LANGCHAIN
# Y LANGGRAPH ENVIAN TRAZAS A LANGSMITH AUTOMATICAMENTE.


# Ejecuta la responsabilidad de configurar langsmith.
def configurar_langsmith() -> None:
    """Carga variables de entorno y habilita aliases compatibles de LangSmith."""
    cargar_archivo_env()
    tracing_enabled = os.getenv("LANGSMITH_TRACING", "false").lower() in {"1", "true", "yes"}
    api_key = os.getenv("LANGSMITH_API_KEY", "")
    project = os.getenv("LANGSMITH_PROJECT", "workflow-agentico-cotizador-eventos")

    if not tracing_enabled or not api_key:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ.setdefault("LANGSMITH_PROJECT", project)
    os.environ.setdefault("LANGCHAIN_PROJECT", project)
    os.environ.setdefault("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")


# Ejecuta la responsabilidad de langsmith activo.
def langsmith_activo() -> bool:
    """Indica si LangSmith esta configurado para enviar trazas."""
    cargar_archivo_env()
    return (
        os.getenv("LANGSMITH_TRACING", "false").lower() in {"1", "true", "yes"}
        and bool(os.getenv("LANGSMITH_API_KEY"))
    )
