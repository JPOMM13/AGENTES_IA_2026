from __future__ import annotations

import os
from functools import lru_cache

from app.configuracion_llm import cargar_archivo_env


class ErrorConfiguracionRedis(RuntimeError):
    """Error controlado cuando falta configurar Redis."""


# CONFIGURACION REDIS: carga .env solo si la variable solicitada no existe.
def leer_variable_entorno(nombre: str, valor_por_defecto: str | None = None) -> str | None:
    """Lee variables de Redis sin pisar valores ya exportados por pruebas o terminal."""
    if os.getenv(nombre) is None:
        cargar_archivo_env()
    return os.getenv(nombre, valor_por_defecto)


# CONFIGURACION REDIS: obtiene la URL de conexion sin hardcodear credenciales.
def obtener_url_redis() -> str:
    """Devuelve REDIS_URL o falla con un mensaje claro."""
    url_redis = leer_variable_entorno("REDIS_URL")
    if not url_redis:
        raise ErrorConfiguracionRedis("Falta REDIS_URL para usar SESSION_STORE=redis.")
    return url_redis


# CONFIGURACION REDIS: define tiempo de vida para memoria corta.
def obtener_ttl_sesion() -> int:
    """Devuelve el TTL en segundos para las sesiones activas en Redis."""
    valor = leer_variable_entorno("REDIS_SESSION_TTL_SECONDS", "86400") or "86400"
    try:
        return int(valor)
    except ValueError as error:
        raise ErrorConfiguracionRedis("REDIS_SESSION_TTL_SECONDS debe ser un numero entero.") from error


# CONEXION REDIS: crea un cliente reutilizable para guardar sesiones activas.
@lru_cache(maxsize=1)
def obtener_cliente_redis():
    """Construye el cliente Redis usando redis-py."""
    try:
        import redis
    except ImportError as error:
        raise ErrorConfiguracionRedis("Instala redis para usar SESSION_STORE=redis.") from error
    return redis.Redis.from_url(obtener_url_redis(), decode_responses=True)


# CONEXION REDIS: permite limpiar cache del cliente en pruebas o cambios de configuracion.
def reiniciar_cliente_redis() -> None:
    """Limpia el cliente cacheado para reconstruirlo con otra configuracion."""
    obtener_cliente_redis.cache_clear()
