"""Configuración del modelo local de Ollama."""

import json
import os
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import load_dotenv

DEFAULT_MODEL = "llama3.2:latest"
DEFAULT_BASE_URL = "http://127.0.0.1:11434"


def get_available_models(base_url: str) -> list[str]:
    """Consulta Ollama y devuelve los nombres de los modelos instalados."""
    try:
        # /api/tags es el endpoint local que utiliza Ollama para listar modelos.
        with urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=3) as response:
            data = json.load(response)
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "No se pudo conectar con Ollama. Inícialo y verifica `ollama list`."
        ) from exc

    return [item["name"] for item in data.get("models", []) if item.get("name")]


def select_model(base_url: str, requested_model: str | None = None) -> str:
    """Selecciona el modelo solicitado, el predeterminado o el primero disponible."""
    models = get_available_models(base_url)
    if not models:
        raise RuntimeError("Ollama está activo, pero no tiene modelos instalados.")

    selected = requested_model or os.getenv("OLLAMA_MODEL")
    if selected:
        if selected not in models:
            raise RuntimeError(
                f"El modelo '{selected}' no está instalado. Disponibles: {', '.join(models)}"
            )
        return selected

    if DEFAULT_MODEL in models:
        return DEFAULT_MODEL
    return models[0]


def create_llm(requested_model: str | None = None):
    """Crea ChatOllama usando la configuración del archivo .env o sus valores por defecto."""
    load_dotenv()
    # La importación local permite probar el resto del proyecto sin iniciar Ollama.
    from langchain_ollama import ChatOllama

    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL)
    model_name = select_model(base_url, requested_model)
    temperature = float(os.getenv("MODEL_TEMPERATURE", "0.2"))

    llm = ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=temperature,
    )
    return llm, model_name
