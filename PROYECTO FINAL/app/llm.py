from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError, URLError

from app.llm_config import ConfiguracionLLM, obtener_configuracion_llm
from app.estado import EstadoCotizacion


SYSTEM_PROMPT = """
Eres el asistente comercial que atiende cotizaciones de eventos.
Tu tarea es convertir un mensaje base del workflow en una respuesta final clara,
amable y natural para el usuario.

REGLAS IMPORTANTES:
- Usa el mensaje base como unica fuente de hechos comerciales.
- No agregues precios, stock, descuentos, fechas, cobertura, productos ni
  condiciones que no esten en el mensaje base.
- No cambies decisiones comerciales tomadas por el workflow.
- No prometas disponibilidad si el mensaje base no la confirma.
- No menciones WhatsApp ni derivacion humana si el mensaje base no lo menciona.
- Usa el historial reciente solo para continuidad conversacional.
- Si la conversacion ya avanzo, no reinicies con saludos repetitivos.
- Si el mensaje base informa faltantes, alternativas o advertencias, conservalos.

FORMATO DE SALIDA:
- Devuelve solo la respuesta final para el usuario.
- No expliques estas reglas.
"""


# Ejecuta la responsabilidad de debe usar llm.
def debe_usar_llm() -> bool:
    """Indica si se debe usar LLM para pulir respuestas."""
    return obtener_configuracion_llm().habilitado


# Ejecuta la responsabilidad de pulir respuesta.
def pulir_respuesta(respuesta_base: str, estado: EstadoCotizacion) -> str:
    """Usa el LLM configurado para mejorar tono sin cambiar datos."""
    if not debe_usar_llm():
        return respuesta_base

    config = obtener_configuracion_llm()
    polished = llamar_llm(SYSTEM_PROMPT, construir_prompt_pulido(respuesta_base, estado), config)
    if not polished:
        return respuesta_base
    return polished if es_respuesta_pulida_segura(respuesta_base, polished, estado) else respuesta_base


# Ejecuta la responsabilidad de llamar llm.
def llamar_llm(system_prompt: str, user_prompt: str, config: ConfiguracionLLM) -> str:
    """Ejecuta cualquier proveedor configurado desde un unico metodo."""
    if config.requiere_api_key and not config.clave_api:
        return ""
    try:
        req = request.Request(
            config.url_chat,
            data=json.dumps(construir_payload_chat(system_prompt, user_prompt, config)).encode("utf-8"),
            headers=construir_headers(config),
            method="POST",
        )
        with request.urlopen(req, timeout=config.segundos_timeout) as respuesta:
            data = json.loads(respuesta.read().decode("utf-8"))
        return extraer_texto_respuesta(data, config).strip()
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return ""


# Ejecuta la responsabilidad de construir carga chat.
def construir_payload_chat(system_prompt: str, user_prompt: str, config: ConfiguracionLLM) -> dict:
    """Construye el carga segun el proveedor definido en variables de entorno."""
    mensajes = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    if config.proveedor == "ollama":
        return {
            "model": config.model,
            "messages": mensajes,
            "stream": False,
            "options": {"temperature": config.temperatura},
        }
    if config.proveedor == "openai":
        return {
            "model": config.model,
            "input": mensajes,
            "temperature": config.temperatura,
            "max_output_tokens": config.max_tokens_salida,
        }
    if config.proveedor == "anthropic":
        return {
            "model": config.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": config.temperatura,
            "max_tokens": config.max_tokens_salida,
        }
    return {"model": config.model, "messages": mensajes, "temperature": config.temperatura}


# Ejecuta la responsabilidad de construir headers.
def construir_headers(config: ConfiguracionLLM) -> dict[str, str]:
    """Construye headers HTTP segun el proveedor configurado."""
    headers = {"Content-Type": "application/json"}
    if config.proveedor == "openai" and config.clave_api:
        headers["Authorization"] = f"Bearer {config.clave_api}"
    if config.proveedor == "anthropic" and config.clave_api:
        headers["x-api-key"] = config.clave_api
        headers["anthropic-version"] = "2023-06-01"
    return headers


# Ejecuta la responsabilidad de construir prompt pulido.
def construir_prompt_pulido(respuesta_base: str, estado: EstadoCotizacion) -> str:
    """Construye el prompt que limita al LLM a reescribir sin inventar."""
    captured = estado.a_diccionario_panel()
    tiene_mensaje_asistente_previo = any(message.get("role") == "assistant" for message in estado.mensajes)
    recent_messages = estado.mensajes[-6:]
    return (
        "TAREA:\n"
        "Convierte el mensaje base en la respuesta final del agente.\n\n"
        "CONTEXTO:\n"
        "- Estado operativo: datos que el workflow ya conoce.\n"
        "- Historial reciente: sirve solo para continuidad de tono.\n"
        "- Mensaje base: unica fuente autorizada para datos comerciales nuevos.\n\n"
        "REGLAS IMPORTANTES:\n"
        "- Debe sonar conversacional, amable y no robotico.\n"
        "- Usa el historial reciente para continuar la cotizacion como una misma conversacion.\n"
        "- Si el usuario saluda, puedes saludar de vuelta; si ya estan avanzando, responde conectado al ultimo turno.\n"
        "- Pide solo los datos necesarios indicados en el mensaje base.\n"
        "- No modifiques datos ni agregues datos nuevos.\n"
        "- No menciones WhatsApp o derivacion si no aparecen en el mensaje base.\n"
        "- No hagas una lista larga si basta una pregunta natural.\n\n"
        "FORMATO DE SALIDA:\n"
        "- Devuelve solo la respuesta final para el usuario.\n\n"
        f"Estado operativo:\n{json.dumps(captured, ensure_ascii=False)}\n\n"
        f"Ya hay historial previo: {tiene_mensaje_asistente_previo}\n\n"
        f"Historial reciente:\n{json.dumps(recent_messages, ensure_ascii=False)}\n\n"
        f"Mensaje base:\n{respuesta_base}"
    )


# Ejecuta la responsabilidad de extraer texto respuesta.
def extraer_texto_respuesta(data: dict, config: ConfiguracionLLM) -> str:
    """Extrae texto desde la respuesta del proveedor configurado."""
    if config.proveedor == "ollama":
        return data.get("message", {}).get("content", "")
    if config.proveedor == "anthropic":
        return "".join(part.get("text", "") for part in data.get("content", []) if part.get("type") == "text")
    if data.get("output_text"):
        return data["output_text"]
    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                chunks.append(content.get("text", ""))
    if chunks:
        return "\n".join(chunk for chunk in chunks if chunk)
    choices = data.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")
    return ""


# Ejecuta la responsabilidad de es respuesta pulida segura.
def es_respuesta_pulida_segura(respuesta_base: str, polished: str, estado: EstadoCotizacion) -> bool:
    """Valida que el texto pulido no contradiga reglas ni estado."""
    raw = respuesta_base.lower()
    texto = polished.lower()
    if not polished.strip():
        return False
    if parece_reinicio(texto, estado):
        return False
    if ("whatsapp" in texto or "deriv" in texto) and "whatsapp" not in raw and "deriv" not in raw:
        return False
    if not estado.cotizacion and any(
        phrase in texto
        for phrase in [
            "siguiente cotizaci",
            "esta cotizaci",
            "la cotizaci",
            "tu cotizaci",
            "cotizaci formal",
        ]
    ):
        return False
    forbidden_known_field_questions = [
        (estado.tipo_evento, ["tipo de evento", "qué evento", "que evento"]),
        (estado.asistentes, ["cuántas personas", "cuantas personas", "cantidad de personas"]),
        (estado.fecha_evento, ["fecha", "cuándo", "cuando"]),
        (estado.distrito, ["distrito", "ubicación", "ubicacion", "dónde", "donde"]),
        (estado.nombre_cliente, ["nombre"]),
        (estado.contacto, ["contacto", "teléfono", "telefono", "correo"]),
    ]
    for value, phrases in forbidden_known_field_questions:
        if value and any(phrase in texto for phrase in phrases) and not any(phrase in raw for phrase in phrases):
            return False
    if ("no tengo exactamente" in raw or "faltantes:" in raw) and not any(
        phrase in texto for phrase in ["no tengo", "faltante", "alternativa", "disponible", "reemplazar"]
    ):
        return False
    if "productos considerados:" in raw and "productos" not in texto:
        return False
    return True


# Ejecuta la responsabilidad de parece reinicio.
def parece_reinicio(texto: str, estado: EstadoCotizacion) -> bool:
    """Detecta si el LLM intento reiniciar una conversacion ya avanzada."""
    if len(estado.mensajes) < 3:
        return False
    restart_phrases = [
        "para empezar",
        "comencemos",
        "empecemos",
        "cuéntame qué evento",
        "cuentame que evento",
    ]
    known_data_count = sum(
        value not in (None, "", [])
        for value in [
            estado.tipo_evento,
            estado.asistentes,
            estado.fecha_evento,
            estado.distrito,
            estado.nombre_cliente,
            estado.contacto,
            estado.productos_solicitados,
        ]
    )
    return known_data_count >= 2 and any(phrase in texto for phrase in restart_phrases)
