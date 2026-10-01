from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
_ENV_LOADED = False
_ENV_MTIME: float | None = None


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool
    provider: str
    model: str
    host: str | None = None
    api_key: str | None = None
    temperature: float = 0.3
    max_output_tokens: int = 350
    timeout_seconds: int = 30

    # Ejecuta la responsabilidad de modelo langchain.
    @property
    def modelo_langchain(self) -> str:
        """Devuelve el identificador de modelo esperado por LangChain."""
        if self.provider == "ollama":
            return f"ollama:{self.model}"
        if self.provider == "openai":
            return f"openai:{self.model}"
        if self.provider == "anthropic":
            return f"anthropic:{self.model}"
        return self.model

    # Ejecuta la responsabilidad de url chat.
    @property
    def url_chat(self) -> str:
        """Devuelve el endpoint HTTP de chat/texto para el proveedor activo."""
        if self.provider == "ollama":
            return f"{(self.host or host_por_defecto_para(self.provider) or '').rstrip('/')}/api/chat"
        if self.provider == "openai":
            return "https://api.openai.com/v1/responses"
        if self.provider == "anthropic":
            return "https://api.anthropic.com/v1/messages"
        if self.host:
            return self.host
        raise ValueError(f"Proveedor LLM no soportado: {self.provider}")

    # Ejecuta la responsabilidad de requiere api key.
    @property
    def requiere_api_key(self) -> bool:
        """Indica si el proveedor configurado requiere API key."""
        return self.provider in {"openai", "anthropic"}


@dataclass(frozen=True)
class ImageGenerationConfig:
    """Configuracion unica para generar imagenes del evento cotizado."""
    enabled: bool
    provider: str
    model: str
    api_key: str | None = None
    size: str = "1024x1024"
    quality: str = "high"
    timeout_seconds: int = 60

    # Ejecuta la responsabilidad de url imagen.
    @property
    def url_imagen(self) -> str:
        """Devuelve el endpoint HTTP de generacion de imagenes."""
        if self.provider == "openai":
            return "https://api.openai.com/v1/images/generations"
        raise ValueError(f"Proveedor de imagen no soportado: {self.provider}")

    # Ejecuta la responsabilidad de listo.
    @property
    def listo(self) -> bool:
        """Indica si existe configuracion suficiente para llamar al modelo de imagen."""
        return self.enabled and self.provider == "openai" and bool(self.api_key)


# Ejecuta la responsabilidad de obtener configuracion llm.
def obtener_configuracion_llm() -> LLMConfig:
    """Lee variables de entorno y arma una configuracion unica de LLM."""
    cargar_archivo_env()
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    return LLMConfig(
        enabled=os.getenv("LLM_ENABLED", "true").lower() in {"1", "true", "yes"},
        provider=provider,
        model=os.getenv("LLM_MODEL", modelo_por_defecto_para(provider)),
        host=os.getenv("LLM_HOST", host_por_defecto_para(provider)),
        api_key=os.getenv("LLM_API_KEY") or api_key_para(provider),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
        max_output_tokens=int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "350")),
        timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
    )


# Ejecuta la responsabilidad de obtener configuracion generacion imagen.
def obtener_configuracion_generacion_imagen() -> ImageGenerationConfig:
    """Lee variables de entorno para generar imagenes con un proveedor multimodal."""
    cargar_archivo_env()
    provider = os.getenv("IMAGE_PROVIDER", "openai").lower()
    return ImageGenerationConfig(
        enabled=os.getenv("IMAGE_GENERATION_ENABLED", "false").lower() in {"1", "true", "yes"},
        provider=provider,
        model=os.getenv("IMAGE_MODEL", modelo_imagen_por_defecto_para(provider)),
        api_key=os.getenv("IMAGE_API_KEY") or os.getenv("LLM_API_KEY") or api_key_para(provider),
        size=os.getenv("IMAGE_SIZE", "1024x1024"),
        quality=os.getenv("IMAGE_QUALITY", "high"),
        timeout_seconds=int(os.getenv("IMAGE_TIMEOUT_SECONDS", "60")),
    )


# Ejecuta la responsabilidad de modelo por defecto para.
def modelo_por_defecto_para(provider: str) -> str:
    """Define el modelo por defecto para cada proveedor soportado."""
    defaults = {
        "ollama": "llama3.2:latest",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-haiku-latest",
    }
    return defaults.get(provider, "llama3.2:latest")


# Ejecuta la responsabilidad de modelo imagen por defecto para.
def modelo_imagen_por_defecto_para(provider: str) -> str:
    """Define el modelo de imagen por defecto para cada proveedor soportado."""
    defaults = {
        "openai": "gpt-image-1",
    }
    return defaults.get(provider, "gpt-image-1")


# Ejecuta la responsabilidad de host por defecto para.
def host_por_defecto_para(provider: str) -> str | None:
    """Define host por defecto cuando el proveedor requiere endpoint local."""
    if provider == "ollama":
        return "http://127.0.0.1:11434"
    return None


# Ejecuta la responsabilidad de api key para.
def api_key_para(provider: str) -> str | None:
    """Busca la API key esperada por proveedor en variables de entorno."""
    env_by_provider = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    env_name = env_by_provider.get(provider)
    return os.getenv(env_name) if env_name else None


# Ejecuta la responsabilidad de cargar archivo env.
def cargar_archivo_env(path: Path = ENV_PATH) -> None:
    """Carga variables desde .env y relee cambios hechos con la app viva."""
    global _ENV_LOADED, _ENV_MTIME
    if _ENV_LOADED or not path.exists():
        if not path.exists():
            return
        current_mtime = path.stat().st_mtime
        if _ENV_MTIME == current_mtime:
            return
    current_mtime = path.stat().st_mtime
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ[key] = value
    _ENV_LOADED = True
    _ENV_MTIME = current_mtime
