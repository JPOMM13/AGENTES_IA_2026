from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.esquemas_api import SolicitudChat, SolicitudFoto, SolicitudSesion, RespuestaSesion, construir_respuesta_sesion
from app.estado import EstadoCotizacion
from app.flujo import manejar_mensaje
from app.repositorios import RepositorioSesionActiva


aplicacion = FastAPI(
    title="API workflow agentico de cotizacion de eventos",
    version="1.0.0",
    description="Expone por HTTP el workflow existente sin cambiar la logica del agente.",
)

# BACKEND / MEMORIA CORTA:
# Este repositorio es la puerta de entrada a la sesion activa.
# Si en .env SESSION_STORE=redis, repositorio_sesiones.obtener/guardar/reiniciar
# leen y escriben en Redis usando id_sesion como clave.
# Si SESSION_STORE no es redis, usa el almacenamiento local mock.
repositorio_sesiones = RepositorioSesionActiva()


@aplicacion.get("/api/salud")
def consultar_salud() -> dict[str, str]:
    """Endpoint simple para validar que el backend FastAPI esta activo."""

    # BACKEND / HEALTHCHECK:
    # No usa Redis, Postgres, LLM ni LangGraph.
    # Solo confirma que FastAPI esta levantado.
    return {"estado": "ok"}


@aplicacion.post("/api/sesiones", response_model=RespuestaSesion)
def crear_o_iniciar_sesion(solicitud: SolicitudSesion | None = None) -> RespuestaSesion:
    """Crea una sesion nueva o recupera una existente si el id_sesion existe."""

    # PASO 1:
    # El frontend puede enviar id_sesion si quiere recuperar una sesion ya creada.
    id_sesion = solicitud.id_sesion if solicitud else None

    # PASO 2 / REDIS:
    # Si existe id_sesion, se consulta la memoria corta.
    # Con SESSION_STORE=redis, esta linea busca en Redis:
    # cotizador:eventos:sesion:{id_sesion}
    # Si no existe en Redis, devuelve None y se crea una sesion nueva.
    estado = repositorio_sesiones.obtener(id_sesion) if id_sesion else None

    # PASO 3 / REDIS:
    # Si no hay estado previo, se crea EstadoCotizacion limpio y se guarda.
    # Con SESSION_STORE=redis, repositorio_sesiones.guardar persiste esa sesion activa en Redis con TTL.
    if estado is None:
        estado = EstadoCotizacion(id_sesion=id_sesion) if id_sesion else EstadoCotizacion()
        repositorio_sesiones.guardar(estado)

    # PASO 4:
    # Se devuelve una respuesta serializable para que Streamlit pueda pintar estado, mensajes y artefactos.
    return construir_respuesta_sesion(estado)


@aplicacion.get("/api/sesiones/{id_sesion}", response_model=RespuestaSesion)
def consultar_sesion(id_sesion: str) -> RespuestaSesion:
    """Consulta el estado actual de una sesion activa."""

    # PASO 1 / REDIS:
    # Recupera la sesion activa por id_sesion.
    # Con SESSION_STORE=redis, consulta Redis usando:
    # cotizador:eventos:sesion:{id_sesion}
    estado = repositorio_sesiones.obtener(id_sesion)

    # PASO 2:
    # Si Redis no tiene esa sesion, el backend responde 404.
    # Esto puede pasar si la sesion expiro por TTL o fue reiniciada.
    if estado is None:
        raise HTTPException(status_code=404, detail="Sesion no encontrada.")

    # PASO 3:
    # Devuelve la foto actual de la sesion al frontend.
    return construir_respuesta_sesion(estado)


@aplicacion.post("/api/chat", response_model=RespuestaSesion)
def conversar_con_agente(solicitud: SolicitudChat) -> RespuestaSesion:
    """Recibe un mensaje, ejecuta el workflow existente y devuelve el estado actualizado."""

    # PASO 1 / REDIS:
    # Antes de llamar al agente, el backend recupera el EstadoCotizacion activo.
    # Con SESSION_STORE=redis, esta lectura viene de Redis por id_sesion.
    estado = repositorio_sesiones.obtener(solicitud.id_sesion)

    # PASO 2:
    # Si no existe sesion en Redis, se crea un EstadoCotizacion con ese id_sesion.
    # Esto evita romper el flujo si el frontend conserva un id que ya expiro.
    if estado is None:
        estado = EstadoCotizacion(id_sesion=solicitud.id_sesion)

    # PASO 3 / LANGGRAPH:
    # manejar_mensaje ejecuta el grafo:
    # validar_entrada -> extraer_y_enrutar_intencion -> gestionar_memoria_persistente
    # -> decidir_accion_agentica -> ejecutar_tools_negocio -> evaluar_salida_guardrail.
    # Dentro del cierre del flujo se vuelve a guardar la sesion activa.
    # Con SESSION_STORE=redis, ese guardado final vuelve a Redis.
    respuesta, estado_actualizado = manejar_mensaje(solicitud.mensaje, estado)

    # PASO 4:
    # Devuelve al frontend el estado ya actualizado y la respuesta final del agente.
    return construir_respuesta_sesion(estado_actualizado, respuesta)


@aplicacion.post("/api/sesiones/{id_sesion}/reiniciar", response_model=RespuestaSesion)
def reiniciar_sesion(id_sesion: str) -> RespuestaSesion:
    """Reinicia una conversacion y devuelve una nueva sesion limpia."""

    # PASO 1 / REDIS:
    # Elimina la sesion activa anterior.
    # Con SESSION_STORE=redis, borra la key:
    # cotizador:eventos:sesion:{id_sesion}
    repositorio_sesiones.reiniciar(id_sesion)

    # PASO 2:
    # Crea un EstadoCotizacion totalmente nuevo, con nuevo id_sesion.
    estado = EstadoCotizacion()

    # PASO 3 / REDIS:
    # Guarda la nueva sesion limpia.
    # Con SESSION_STORE=redis, se persiste nuevamente en Redis con TTL.
    repositorio_sesiones.guardar(estado)

    # PASO 4:
    # Devuelve al frontend la nueva sesion vacia para iniciar conversacion.
    return construir_respuesta_sesion(estado)


# FOTO DEL LOCAL (multimodal): el cliente sube una foto de su espacio y la imagen final de la cotizacion se compone
# sobre ella con los productos cotizados. Se guarda en disco por id_sesion; solo jpg/png/webp y maximo 8 MB.
@aplicacion.post("/api/sesiones/{id_sesion}/foto", response_model=RespuestaSesion)
def subir_foto_local(id_sesion: str, solicitud: SolicitudFoto) -> RespuestaSesion:
    import base64

    from app.artefactos import guardar_foto_local

    estado = repositorio_sesiones.obtener(id_sesion)
    if estado is None:
        raise HTTPException(status_code=404, detail="Sesion no encontrada.")
    try:
        datos = base64.b64decode(solicitud.imagen_base64, validate=True)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="La imagen no esta en base64 valido.") from error
    try:
        ruta = guardar_foto_local(id_sesion, datos, solicitud.nombre)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    estado.foto_local = ruta
    estado.registrar_log("foto_local_recibida", {"bytes": len(datos)})
    repositorio_sesiones.guardar(estado)
    return construir_respuesta_sesion(estado)


# IMAGENES GENERADAS: se sirven por nombre de archivo (sin rutas) para que el frontend las muestre aunque corra en
# otro contenedor; solo se exponen las carpetas de artefactos y fotos subidas.
@aplicacion.get("/api/imagenes/{nombre}")
def descargar_imagen(nombre: str) -> FileResponse:
    from app.artefactos import ruta_imagen_publica

    ruta = ruta_imagen_publica(nombre)
    if ruta is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    return FileResponse(ruta)
