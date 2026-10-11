from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE_URL = os.getenv("COTIZADOR_API_URL", "http://127.0.0.1:8000").rstrip("/")


class ErrorApiCotizador(RuntimeError):
    """Error controlado cuando Streamlit no puede comunicarse con FastAPI."""


def crear_sesion_api(id_sesion: str | None = None) -> dict[str, Any]:
    """Pide al backend crear o recuperar una sesion de conversacion."""

    cuerpo = {"id_sesion": id_sesion} if id_sesion else {}
    return _enviar_json("POST", "/api/sesiones", cuerpo)


def consultar_sesion_api(id_sesion: str) -> dict[str, Any]:
    """Consulta al backend el estado de una sesion existente."""

    return _enviar_json("GET", f"/api/sesiones/{id_sesion}")


def enviar_mensaje_api(id_sesion: str, mensaje: str) -> dict[str, Any]:
    """Envia un mensaje del usuario al backend agentico."""

    return _enviar_json("POST", "/api/chat", {"id_sesion": id_sesion, "mensaje": mensaje})


def reiniciar_sesion_api(id_sesion: str) -> dict[str, Any]:
    """Solicita al backend reiniciar la conversacion actual."""

    return _enviar_json("POST", f"/api/sesiones/{id_sesion}/reiniciar")


def _enviar_json(metodo: str, ruta: str, cuerpo: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ejecuta una llamada HTTP JSON usando solo libreria estandar de Python."""

    datos = None
    cabeceras = {"Content-Type": "application/json"}
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
    solicitud = Request(f"{API_BASE_URL}{ruta}", data=datos, headers=cabeceras, method=metodo)
    try:
        with urlopen(solicitud, timeout=120) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except HTTPError as error:
        detalle = error.read().decode("utf-8")
        raise ErrorApiCotizador(f"Error HTTP {error.code}: {detalle}") from error
    except URLError as error:
        raise ErrorApiCotizador(f"No se pudo conectar con FastAPI en {API_BASE_URL}.") from error
    except TimeoutError as error:
        raise ErrorApiCotizador("La llamada al backend tardo demasiado.") from error
