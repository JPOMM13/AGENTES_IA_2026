from __future__ import annotations

from app import redis_session_store, session_store
from app.estado import EstadoCotizacion


class RepositorioSesionActiva:
    """Repositorio de memoria corta; en produccion seria Redis."""

    # Ejecuta la responsabilidad de guardar.
    def guardar(self, estado: EstadoCotizacion) -> None:
        """Guarda la foto actual de la conversacion activa."""
        redis_session_store.guardar_sesion_activa(estado)

    # Ejecuta la responsabilidad de obtener.
    def obtener(self, id_sesion: str) -> EstadoCotizacion | None:
        """Recupera el estado activo por id_sesion."""
        return redis_session_store.cargar_sesion_activa(id_sesion)

    # Ejecuta la responsabilidad de reiniciar.
    def reiniciar(self, id_sesion: str) -> None:
        """Elimina la memoria activa de una conversacion."""
        redis_session_store.reiniciar_sesion_activa(id_sesion)


class RepositorioMemoriaCotizacion:
    """Repositorio de memoria persistente; en produccion seria PostgreSQL/NoSQL."""

    # Ejecuta la responsabilidad de guardar.
    def guardar(self, estado: EstadoCotizacion) -> None:
        """Guarda el estado persistente asociado al contacto."""
        session_store.guardar_estado_conversacion(estado)

    # Ejecuta la responsabilidad de buscar por contacto.
    def buscar_por_contacto(self, contacto: str | None) -> EstadoCotizacion | None:
        """Busca una cotizacion previa por telefono o correo."""
        return session_store.buscar_conversacion_previa(None, contacto)

    # Ejecuta la responsabilidad de hidratar.
    def hidratar(self, destino: EstadoCotizacion, origen: EstadoCotizacion) -> EstadoCotizacion:
        """Carga una memoria previa dentro de la sesion actual."""
        return session_store.hidratar_estado(destino, origen)
