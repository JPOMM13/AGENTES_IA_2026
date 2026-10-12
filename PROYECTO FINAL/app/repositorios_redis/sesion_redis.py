from __future__ import annotations

import json

from app.estado import EstadoCotizacion
from app.repositorios_redis.conexion import obtener_cliente_redis, obtener_ttl_sesion


PREFIJO_SESION = "jpomm:sesion:"


# MEMORIA CORTA REDIS: arma la clave usada para la sesion activa.
def armar_clave_sesion(id_sesion: str) -> str:
    """Construye la key Redis a partir del id_sesion."""
    return f"{PREFIJO_SESION}{id_sesion}"


# MEMORIA CORTA REDIS: guarda el estado vivo de una conversacion con TTL.
def guardar_sesion_activa_redis(estado: EstadoCotizacion) -> None:
    """Guarda una sesion activa en Redis usando id_sesion como clave."""
    cliente = obtener_cliente_redis()
    payload = json.dumps(estado.a_diccionario_persistido(), ensure_ascii=False)
    cliente.setex(armar_clave_sesion(estado.id_sesion), obtener_ttl_sesion(), payload)


# MEMORIA CORTA REDIS: recupera el estado vivo por id_sesion.
def cargar_sesion_activa_redis(id_sesion: str) -> EstadoCotizacion | None:
    """Recupera una sesion activa desde Redis."""
    payload = obtener_cliente_redis().get(armar_clave_sesion(id_sesion))
    if not payload:
        return None
    return EstadoCotizacion.desde_diccionario_persistido(json.loads(payload))


# MEMORIA CORTA REDIS: elimina una sesion activa cuando se reinicia la conversacion.
def reiniciar_sesion_activa_redis(id_sesion: str) -> None:
    """Elimina la sesion activa desde Redis."""
    obtener_cliente_redis().delete(armar_clave_sesion(id_sesion))
