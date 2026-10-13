from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.estado import EstadoCotizacion


class SolicitudSesion(BaseModel):
    """Contrato API para crear o reutilizar una sesion de conversacion."""

    id_sesion: str | None = None


class SolicitudChat(BaseModel):
    """Contrato API para enviar un mensaje del frontend al agente."""

    id_sesion: str = Field(..., min_length=1)
    mensaje: str = Field(..., min_length=1)


class SolicitudFoto(BaseModel):
    """Foto del local del cliente, en base64 (jpg, png o webp; maximo 8 MB)."""

    imagen_base64: str = Field(..., min_length=16)
    nombre: str = "local.jpg"


class RespuestaSesion(BaseModel):
    """Contrato API que devuelve una foto serializable del estado del agente."""

    id_sesion: str
    respuesta: str | None = None
    estado: dict[str, Any]
    estado_panel: dict[str, Any]
    mensajes: list[dict[str, str]]
    cotizacion: dict[str, Any] | None = None
    imagen_artefacto_cotizacion: str | None = None
    foto_local: str | None = None


def construir_respuesta_sesion(estado: EstadoCotizacion, respuesta: str | None = None) -> RespuestaSesion:
    """Convierte el estado interno del agente en una respuesta HTTP segura."""

    return RespuestaSesion(
        id_sesion=estado.id_sesion,
        respuesta=respuesta,
        estado=estado.a_diccionario_persistido(),
        estado_panel=estado.a_diccionario_panel(),
        mensajes=estado.mensajes,
        cotizacion=estado.cotizacion,
        imagen_artefacto_cotizacion=estado.imagen_artefacto_cotizacion,
        foto_local=estado.foto_local,
    )
