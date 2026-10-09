from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
_ENV_LOADED = False
_ENV_MTIME: float | None = None


@dataclass(frozen=True)
class ConfiguracionLLM:
    habilitado: bool
    proveedor: str
    model: str
    host: str | None = None
    clave_api: str | None = None
    temperatura: float = 0.3
    max_tokens_salida: int = 350
    segundos_timeout: int = 30

    # CONFIGURACION LLM: adapta el modelo al formato que espera LangChain create_agent.
    @property
    def modelo_langchain(self) -> str:
        """Devuelve el identificador de modelo esperado por LangChain."""
        if self.proveedor == "ollama":
            return f"ollama:{self.model}"
        if self.proveedor == "openai":
            return f"openai:{self.model}"
        if self.proveedor == "anthropic":
            return f"anthropic:{self.model}"
        return self.model

    # CONFIGURACION LLM: resuelve el endpoint de chat segun proveedor configurado.
    @property
    def url_chat(self) -> str:
        """Devuelve el endpoint HTTP de chat/texto para el proveedor activo."""
        if self.proveedor == "ollama":
            return f"{(self.host or host_por_defecto_para(self.proveedor) or '').rstrip('/')}/api/chat"
        if self.proveedor == "openai":
            return "https://api.openai.com/v1/responses"
        if self.proveedor == "anthropic":
            return "https://api.anthropic.com/v1/messages"
        if self.host:
            return self.host
        raise ValueError(f"Proveedor LLM no soportado: {self.proveedor}")

    # CONFIGURACION LLM: indica si el proveedor necesita clave externa o es local.
    @property
    def requiere_api_key(self) -> bool:
        """Indica si el proveedor configurado requiere API key."""
        return self.proveedor in {"openai", "anthropic"}


@dataclass(frozen=True)
class ConfiguracionGeneracionImagen:
    """Configuracion unica para generar imagenes del evento cotizado."""
    habilitado: bool
    proveedor: str
    model: str
    clave_api: str | None = None
    size: str = "1024x1024"
    quality: str = "high"
    segundos_timeout: int = 60

    # CONFIGURACION MULTIMODAL: resuelve el endpoint de imagen segun proveedor configurado.
    @property
    def url_imagen(self) -> str:
        """Devuelve el endpoint HTTP de generacion de imagenes."""
        if self.proveedor == "openai":
            return "https://api.openai.com/v1/images/generations"
        raise ValueError(f"Proveedor de imagen no soportado: {self.proveedor}")

    # CONFIGURACION MULTIMODAL: valida que existan proveedor, modelo y credenciales necesarias.
    @property
    def listo(self) -> bool:
        """Indica si existe configuracion suficiente para llamar al modelo de imagen."""
        return self.habilitado and self.proveedor == "openai" and bool(self.clave_api)


# CONFIGURACION LLM: centraliza proveedor, modelo y parametros para cambiar entre Ollama/OpenAI/Anthropic.
def obtener_configuracion_llm() -> ConfiguracionLLM:
    """Lee variables de entorno y arma una configuracion unica de LLM."""
    cargar_archivo_env()
    proveedor = os.getenv("LLM_PROVIDER", "ollama").lower()
    return ConfiguracionLLM(
        habilitado=os.getenv("LLM_ENABLED", "true").lower() in {"1", "true", "yes"},
        proveedor=proveedor,
        model=os.getenv("LLM_MODEL", modelo_por_defecto_para(proveedor)),
        host=os.getenv("LLM_HOST", host_por_defecto_para(proveedor)),
        clave_api=os.getenv("LLM_API_KEY") or api_key_para(proveedor),
        temperatura=float(os.getenv("LLM_TEMPERATURE", "0.3")),
        max_tokens_salida=int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "350")),
        segundos_timeout=int(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
    )


# CONFIGURACION MULTIMODAL: centraliza proveedor y modelo para imagenes del evento.
def obtener_configuracion_generacion_imagen() -> ConfiguracionGeneracionImagen:
    """Lee variables de entorno para generar imagenes con un proveedor multimodal."""
    cargar_archivo_env()
    proveedor = os.getenv("IMAGE_PROVIDER", "openai").lower()
    return ConfiguracionGeneracionImagen(
        habilitado=os.getenv("IMAGE_GENERATION_ENABLED", "false").lower() in {"1", "true", "yes"},
        proveedor=proveedor,
        model=os.getenv("IMAGE_MODEL", modelo_imagen_por_defecto_para(proveedor)),
        clave_api=os.getenv("IMAGE_API_KEY") or os.getenv("LLM_API_KEY") or api_key_para(proveedor),
        size=os.getenv("IMAGE_SIZE", "1024x1024"),
        quality=os.getenv("IMAGE_QUALITY", "high"),
        segundos_timeout=int(os.getenv("IMAGE_TIMEOUT_SECONDS", "60")),
    )


# CONFIGURACION LLM: define modelo por defecto segun proveedor cuando no viene en .env.
def modelo_por_defecto_para(proveedor: str) -> str:
    """Define el modelo por defecto para cada proveedor soportado."""
    defaults = {
        "ollama": "llama3.2:latest",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-haiku-latest",
    }
    return defaults.get(proveedor, "llama3.2:latest")


# CONFIGURACION MULTIMODAL: define modelo de imagen por defecto segun proveedor.
def modelo_imagen_por_defecto_para(proveedor: str) -> str:
    """Define el modelo de imagen por defecto para cada proveedor soportado."""
    defaults = {
        "openai": "gpt-image-1",
    }
    return defaults.get(proveedor, "gpt-image-1")


# CONFIGURACION LLM: define endpoint local o remoto segun proveedor.
def host_por_defecto_para(proveedor: str) -> str | None:
    """Define host por defecto cuando el proveedor requiere endpoint local."""
    if proveedor == "ollama":
        return "http://127.0.0.1:11434"
    return None


# CONFIGURACION LLM: lee la API key solo para proveedores que la requieren.
def api_key_para(proveedor: str) -> str | None:
    """Busca la API key esperada por proveedor en variables de entorno."""
    env_by_provider = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    env_name = env_by_provider.get(proveedor)
    return os.getenv(env_name) if env_name else None


# CONFIGURACION LLM: carga variables del archivo .env sin depender de valores hardcodeados.
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
