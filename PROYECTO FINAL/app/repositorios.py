from __future__ import annotations

from app import almacen_sesion, almacen_sesion_redis
from app.estado import EstadoCotizacion


class RepositorioSesionActiva:
    """Repositorio de memoria corta; en produccion seria Redis."""

    # REPOSITORIO: delega guardado al almacen mock correspondiente.
    def guardar(self, estado: EstadoCotizacion) -> None:
        """Guarda la foto actual de la conversacion activa."""
        almacen_sesion_redis.guardar_sesion_activa(estado)

    # REPOSITORIO: delega lectura de sesion activa al almacen mock correspondiente.
    def obtener(self, id_sesion: str) -> EstadoCotizacion | None:
        """Recupera el estado activo por id_sesion."""
        return almacen_sesion_redis.cargar_sesion_activa(id_sesion)

    # REPOSITORIO: delega reinicio de sesion activa al almacen mock correspondiente.
    def reiniciar(self, id_sesion: str) -> None:
        """Elimina la memoria activa de una conversacion."""
        almacen_sesion_redis.reiniciar_sesion_activa(id_sesion)


class RepositorioMemoriaCotizacion:
    """Repositorio de memoria persistente; en produccion seria PostgreSQL/NoSQL."""

    # REPOSITORIO: delega guardado al almacen mock correspondiente.
    def guardar(self, estado: EstadoCotizacion) -> None:
        """Guarda el estado persistente asociado al contacto."""
        almacen_sesion.guardar_estado_conversacion(estado)

    # REPOSITORIO: busca memoria persistente usando contacto como identificador.
    def buscar_por_contacto(self, contacto: str | None) -> EstadoCotizacion | None:
        """Busca una cotizacion previa por telefono o correo."""
        return almacen_sesion.buscar_conversacion_previa(None, contacto)

    # REPOSITORIO: hidrata la sesion actual con datos recuperados de memoria persistente.
    def hidratar(self, destino: EstadoCotizacion, origen: EstadoCotizacion) -> EstadoCotizacion:
        """Carga una memoria previa dentro de la sesion actual."""
        return almacen_sesion.hidratar_estado(destino, origen)
