"""
eventos_agent.py
----------------
Adaptador entre DeepTeam y el agente "Tus Eventos".

Expone la función agent_invoke(input_text) que DeepTeam necesita
para enviar ataques y recibir respuestas del agente real.

Estrategia:
- Cada llamada crea una sesión nueva e independiente en FastAPI.
- Esto garantiza que los ataques no se contaminen entre sí (estado limpio).
- Usa directamente app.cliente_api para comunicarse con el backend,
  igual que lo hace el frontend Streamlit.

Requisito: el backend FastAPI debe estar corriendo antes de ejecutar
las pruebas. Levántalo con:
    uvicorn app.api:aplicacion --reload --port 8000
"""

from __future__ import annotations

import sys
from pathlib import Path

# Agrega la raíz del proyecto al path para importar app.*
_PROYECTO_ROOT = Path(__file__).resolve().parents[1]
if str(_PROYECTO_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROYECTO_ROOT))

from app.cliente_api import (
    ErrorApiCotizador,
    crear_sesion_api,
    enviar_mensaje_api,
)


def agent_invoke(input_text: str) -> str:
    """
    Contrato que DeepTeam necesita: recibe un string, devuelve un string.

    Internamente:
    1. Crea una sesión nueva en FastAPI (estado limpio por ataque).
    2. Envía el mensaje al endpoint /api/chat.
    3. Devuelve solo el texto de la respuesta del agente.

    Si el backend no está disponible, lanza RuntimeError con instrucciones.
    """
    try:
        sesion = crear_sesion_api()
        id_sesion = sesion["id_sesion"]
        respuesta = enviar_mensaje_api(id_sesion, input_text)
        return respuesta.get("respuesta", "")
    except ErrorApiCotizador as exc:
        raise RuntimeError(
            f"No se pudo conectar con el agente.\n"
            f"Asegúrate de que FastAPI esté corriendo:\n"
            f"  uvicorn app.api:aplicacion --reload --port 8000\n\n"
            f"Error original: {exc}"
        ) from exc


def agent_invoke_sesion(input_text: str, id_sesion: str) -> tuple[str, str]:
    """
    Variante que reutiliza una sesión existente (para conversaciones multi-turno).

    Devuelve (respuesta, id_sesion) para poder encadenar turnos.
    Útil para pruebas que simulan una conversación completa antes del ataque.
    """
    try:
        respuesta = enviar_mensaje_api(id_sesion, input_text)
        return respuesta.get("respuesta", ""), id_sesion
    except ErrorApiCotizador as exc:
        raise RuntimeError(
            f"Error al enviar mensaje a sesión {id_sesion}: {exc}"
        ) from exc


def nueva_sesion() -> str:
    """Crea una sesión limpia y devuelve su id_sesion."""
    try:
        sesion = crear_sesion_api()
        return sesion["id_sesion"]
    except ErrorApiCotizador as exc:
        raise RuntimeError(f"No se pudo crear sesión: {exc}") from exc
