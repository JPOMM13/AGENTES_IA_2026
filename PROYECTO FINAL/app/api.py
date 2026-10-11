from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.esquemas_api import SolicitudChat, SolicitudSesion, RespuestaSesion, construir_respuesta_sesion
from app.estado import EstadoCotizacion
from app.flujo import manejar_mensaje
from app.repositorios import RepositorioSesionActiva


aplicacion = FastAPI(
    title="API workflow agentico de cotizacion de eventos",
    version="1.0.0",
    description="Expone por HTTP el workflow existente sin cambiar la logica del agente.",
)

repositorio_sesiones = RepositorioSesionActiva()


@aplicacion.get("/api/salud")
def consultar_salud() -> dict[str, str]:
    """Endpoint simple para validar que el backend FastAPI esta activo."""

    return {"estado": "ok"}


@aplicacion.post("/api/sesiones", response_model=RespuestaSesion)
def crear_o_iniciar_sesion(solicitud: SolicitudSesion | None = None) -> RespuestaSesion:
    """Crea una sesion nueva o recupera una existente si el id_sesion existe."""

    id_sesion = solicitud.id_sesion if solicitud else None
    estado = repositorio_sesiones.obtener(id_sesion) if id_sesion else None
    if estado is None:
        estado = EstadoCotizacion(id_sesion=id_sesion) if id_sesion else EstadoCotizacion()
        repositorio_sesiones.guardar(estado)
    return construir_respuesta_sesion(estado)


@aplicacion.get("/api/sesiones/{id_sesion}", response_model=RespuestaSesion)
def consultar_sesion(id_sesion: str) -> RespuestaSesion:
    """Consulta el estado actual de una sesion activa."""

    estado = repositorio_sesiones.obtener(id_sesion)
    if estado is None:
        raise HTTPException(status_code=404, detail="Sesion no encontrada.")
    return construir_respuesta_sesion(estado)


@aplicacion.post("/api/chat", response_model=RespuestaSesion)
def conversar_con_agente(solicitud: SolicitudChat) -> RespuestaSesion:
    """Recibe un mensaje, ejecuta el workflow existente y devuelve el estado actualizado."""

    estado = repositorio_sesiones.obtener(solicitud.id_sesion)
    if estado is None:
        estado = EstadoCotizacion(id_sesion=solicitud.id_sesion)
    respuesta, estado_actualizado = manejar_mensaje(solicitud.mensaje, estado)
    return construir_respuesta_sesion(estado_actualizado, respuesta)


@aplicacion.post("/api/sesiones/{id_sesion}/reiniciar", response_model=RespuestaSesion)
def reiniciar_sesion(id_sesion: str) -> RespuestaSesion:
    """Reinicia una conversacion y devuelve una nueva sesion limpia."""

    repositorio_sesiones.reiniciar(id_sesion)
    estado = EstadoCotizacion()
    repositorio_sesiones.guardar(estado)
    return construir_respuesta_sesion(estado)
