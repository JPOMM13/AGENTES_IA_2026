from __future__ import annotations

import os

from app import almacen_sesion, almacen_sesion_redis
from app.configuracion_llm import cargar_archivo_env
from app.estado import EstadoCotizacion
from app.repositorios_postgres.memoria_postgres import (
    buscar_conversacion_previa_postgres,
    guardar_estado_conversacion_postgres,
)
from app.repositorios_redis.sesion_redis import (
    cargar_sesion_activa_redis,
    guardar_sesion_activa_redis,
    reiniciar_sesion_activa_redis,
)


# CONFIGURACION REPOSITORIOS: carga .env como fuente principal de runtime.
def leer_variable_configuracion(nombre: str, valor_por_defecto: str) -> str:
    """Lee variables de seleccion de repositorio desde .env o entorno."""
    cargar_archivo_env()
    return os.getenv(nombre, valor_por_defecto).strip().lower()


# CONFIGURACION REPOSITORIOS: decide si la memoria corta vive en Redis o almacenamiento local.
def usar_redis_para_sesion() -> bool:
    """Indica si SESSION_STORE esta configurado en redis."""
    return leer_variable_configuracion("SESSION_STORE", "mock") == "redis"


# CONFIGURACION REPOSITORIOS: decide si la memoria persistente vive en PostgreSQL JSONB o almacenamiento local.
def usar_postgres_para_memoria() -> bool:
    """Indica si MEMORY_DATA_SOURCE esta configurado en postgres."""
    return leer_variable_configuracion("MEMORY_DATA_SOURCE", "mock") == "postgres"


class RepositorioSesionActiva:
    """Repositorio de memoria corta; en produccion seria Redis."""

    # REPOSITORIO: guarda sesion activa en Redis o almacenamiento local segun SESSION_STORE.
    def guardar(self, estado: EstadoCotizacion) -> None:
        """Guarda la foto actual de la conversacion activa."""
        if usar_redis_para_sesion():
            guardar_sesion_activa_redis(estado)
            return
        almacen_sesion_redis.guardar_sesion_activa(estado)

    # REPOSITORIO: recupera sesion activa desde Redis o almacenamiento local segun SESSION_STORE.
    def obtener(self, id_sesion: str) -> EstadoCotizacion | None:
        """Recupera el estado activo por id_sesion."""
        if usar_redis_para_sesion():
            return cargar_sesion_activa_redis(id_sesion)
        return almacen_sesion_redis.cargar_sesion_activa(id_sesion)

    # REPOSITORIO: elimina sesion activa desde Redis o almacenamiento local segun SESSION_STORE.
    def reiniciar(self, id_sesion: str) -> None:
        """Elimina la memoria activa de una conversacion."""
        if usar_redis_para_sesion():
            reiniciar_sesion_activa_redis(id_sesion)
            return
        almacen_sesion_redis.reiniciar_sesion_activa(id_sesion)


class RepositorioMemoriaCotizacion:
    """Repositorio de memoria persistente; en produccion seria PostgreSQL/NoSQL."""

    # REPOSITORIO: guarda memoria persistente en PostgreSQL JSONB o almacenamiento local segun MEMORY_DATA_SOURCE.
    def guardar(self, estado: EstadoCotizacion) -> None:
        """Guarda el estado persistente asociado al contacto."""
        if usar_postgres_para_memoria():
            guardar_estado_conversacion_postgres(estado)
            return
        almacen_sesion.guardar_estado_conversacion(estado)

    # REPOSITORIO: busca memoria persistente usando contacto como identificador.
    def buscar_por_contacto(self, contacto: str | None) -> EstadoCotizacion | None:
        """Busca una cotizacion previa por telefono o correo."""
        if usar_postgres_para_memoria():
            return buscar_conversacion_previa_postgres(contacto)
        return almacen_sesion.buscar_conversacion_previa(None, contacto)

    # REPOSITORIO: hidrata la sesion actual con datos recuperados de memoria persistente.
    def hidratar(self, destino: EstadoCotizacion, origen: EstadoCotizacion) -> EstadoCotizacion:
        """Carga una memoria previa dentro de la sesion actual."""
        return almacen_sesion.hidratar_estado(destino, origen)
