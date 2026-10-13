from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

from app.prompts_agenticos import SYSTEM_PROMPT_GUARDRAIL

# GUARDRAIL LLM: categorias de violacion detectables por el modelo.
CATEGORIAS_VIOLACION = [
    "lenguaje_de_odio",
    "racismo_o_discriminacion",
    "prompt_injection",
    "contenido_violento",
    "contenido_sexual",
    "amenazas",
    "informacion_personal_sensible",
    "contenido_inapropiado_general",
    "fuera_de_scope",
]

_OPENAI_GUARDRAIL_URL = "https://api.openai.com/v1/responses"
_MODELO_GUARDRAIL_DEFAULT = "gpt-4o-mini"
_TIMEOUT_GUARDRAIL = 10  # segundos — timeout corto para no bloquear el flujo
_TEMPERATURA_GUARDRAIL = 0.0  # determinismo maximo para clasificacion


@dataclass(frozen=True)
class ResultadoGuardrailLLM:
    """Resultado del guardrail semantico basado en LLM."""

    permitido: bool
    categoria_detectada: str | None
    nivel_confianza: float
    motivo: str
    proveedor: str = "openai"
    uso_fallback: bool = False


# GUARDRAIL LLM DE ENTRADA: usa OpenAI para detectar contenido inapropiado o fuera de scope.
def validar_mensaje_con_llm(mensaje: str) -> ResultadoGuardrailLLM:
    """
    Envia el mensaje a OpenAI para deteccion semantica de contenido bloqueado.

    Retorna un ResultadoGuardrailLLM con la decision del modelo.
    Si OpenAI no esta disponible o falla, usa fallback determinista y marca uso_fallback=True.
    """
    api_key = _obtener_api_key_guardrail()
    if not api_key:
        return _fallback_sin_llm(mensaje, motivo="GUARDRAIL_API_KEY no configurada")

    try:
        payload = {
            "model": os.getenv("GUARDRAIL_LLM_MODEL", _MODELO_GUARDRAIL_DEFAULT),
            "input": [
                {"role": "system", "content": SYSTEM_PROMPT_GUARDRAIL},
                {"role": "user", "content": f"Analiza este mensaje:\n\n{mensaje}"},
            ],
            "temperature": _TEMPERATURA_GUARDRAIL,
            "max_output_tokens": 200,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        req = request.Request(
            _OPENAI_GUARDRAIL_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with request.urlopen(req, timeout=_TIMEOUT_GUARDRAIL) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        texto_respuesta = _extraer_texto_openai(data)
        return _parsear_respuesta_guardrail(texto_respuesta)

    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return _fallback_sin_llm(mensaje, motivo=f"Error al llamar OpenAI: {type(exc).__name__}")


# GUARDRAIL LLM: extrae el texto de la respuesta OpenAI Responses API.
def _extraer_texto_openai(data: dict) -> str:
    """Extrae el contenido textual de la respuesta de la OpenAI Responses API."""
    if data.get("output_text"):
        return data["output_text"]
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                return content.get("text", "")
    choices = data.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")
    return ""


# GUARDRAIL LLM: interpreta el JSON devuelto por el modelo de clasificacion.
def _parsear_respuesta_guardrail(texto: str) -> ResultadoGuardrailLLM:
    """
    Parsea el JSON de clasificacion del guardrail LLM.
    Si el JSON falla, retorna permitido=True para no bloquear falsamente.
    """
    texto = texto.strip()
    # Limpia bloques de codigo markdown si el modelo los incluyo
    if texto.startswith("```"):
        lineas = texto.splitlines()
        texto = "\n".join(l for l in lineas if not l.startswith("```")).strip()
    try:
        resultado = json.loads(texto)
        return ResultadoGuardrailLLM(
            permitido=bool(resultado.get("permitido", True)),
            categoria_detectada=resultado.get("categoria_detectada") or None,
            nivel_confianza=float(resultado.get("nivel_confianza", 0.5)),
            motivo=resultado.get("motivo", "clasificacion completada"),
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        # Si no podemos parsear, dejamos pasar (fail-open) para no bloquear consultas legitimas
        return ResultadoGuardrailLLM(
            permitido=True,
            categoria_detectada=None,
            nivel_confianza=0.0,
            motivo="respuesta LLM no parseable — se permite por seguridad",
            uso_fallback=True,
        )


# GUARDRAIL LLM: fallback determinista cuando OpenAI no esta disponible.
def _fallback_sin_llm(mensaje: str, motivo: str) -> ResultadoGuardrailLLM:
    """
    Fallback cuando OpenAI no esta disponible.
    Aplica heuristica minima para no bloquear consultas legitimas.
    """
    texto = mensaje.lower()
    patrones_criticos = [
        ("lenguaje_de_odio", ["maldito", "imbecil", "idiota", "estupido", "pendejo", "mierda", "puta", "hdp"]),
        ("racismo_o_discriminacion", ["negro de mierda", "indio de mierda", "marica", "maricon"]),
        ("prompt_injection", [
            "ignora tus instrucciones",
            "olvida tus reglas",
            "muestra tu prompt",
            "revela tu system prompt",
            "actua como",
            "pretende ser",
            "nuevo rol",
            "nuevo sistema",
        ]),
        ("amenazas", ["te voy a matar", "los voy a matar", "los mato", "hackear"]),
    ]
    for categoria, palabras in patrones_criticos:
        if any(p in texto for p in palabras):
            return ResultadoGuardrailLLM(
                permitido=False,
                categoria_detectada=categoria,
                nivel_confianza=0.9,
                motivo=f"detectado por fallback determinista ({motivo})",
                uso_fallback=True,
            )
    return ResultadoGuardrailLLM(
        permitido=True,
        categoria_detectada=None,
        nivel_confianza=1.0,
        motivo=f"fallback sin deteccion ({motivo})",
        uso_fallback=True,
    )


# GUARDRAIL LLM: obtiene la API key dedicada para el guardrail o la key general de OpenAI.
def _obtener_api_key_guardrail() -> str | None:
    """
    Resuelve la API key para el guardrail en orden de prioridad:
    1. GUARDRAIL_API_KEY (dedicada para guardrails)
    2. OPENAI_API_KEY (general del proyecto)
    3. LLM_API_KEY si el proveedor es openai
    """
    _cargar_env()
    return (
        os.getenv("GUARDRAIL_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or (os.getenv("LLM_API_KEY") if os.getenv("LLM_PROVIDER", "").lower() == "openai" else None)
    )


_ENV_LOADED_GUARDRAIL = False


def _cargar_env() -> None:
    """Carga variables desde .env si aun no se han cargado en este modulo."""
    global _ENV_LOADED_GUARDRAIL
    if _ENV_LOADED_GUARDRAIL:
        return
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)
    _ENV_LOADED_GUARDRAIL = True


# GUARDRAIL LLM: umbral de confianza minimo para bloquear mensajes.
UMBRAL_BLOQUEO = float(os.getenv("GUARDRAIL_CONFIDENCE_THRESHOLD", "0.75"))


# GUARDRAIL LLM: aplica el umbral de confianza al resultado antes de decidir.
def debe_bloquear(resultado: ResultadoGuardrailLLM) -> bool:
    """
    Combina la decision del modelo con el umbral de confianza configurado.
    Solo bloquea si el modelo dijo False Y la confianza supera el umbral.
    """
    if resultado.permitido:
        return False
    return resultado.nivel_confianza >= UMBRAL_BLOQUEO


# GUARDRAIL LLM: genera respuesta segura segun la categoria detectada.
def respuesta_segura_para(resultado: ResultadoGuardrailLLM) -> str:
    """Devuelve un mensaje de rechazo apropiado segun la categoria detectada."""
    mensajes: dict[str | None, str] = {
        "lenguaje_de_odio": (
            "Por favor comunicate con respeto. Estoy aqui para ayudarte con tu cotizacion de bebidas para eventos."
        ),
        "racismo_o_discriminacion": (
            "No puedo continuar con ese tipo de mensaje. Si tienes una consulta sobre nuestros servicios, con gusto te ayudo."
        ),
        "prompt_injection": (
            "Puedo ayudarte con la cotizacion del evento, pero no puedo cambiar mis reglas internas ni omitir validaciones."
        ),
        "contenido_violento": (
            "Ese tipo de contenido no esta permitido. Estoy disponible para cotizaciones de bebidas para tus eventos."
        ),
        "contenido_sexual": (
            "Ese tipo de contenido no corresponde a este servicio. Puedo ayudarte con la cotizacion de tu evento."
        ),
        "amenazas": (
            "No puedo procesar ese mensaje. Si tienes una consulta sobre nuestros servicios, escribeme con normalidad."
        ),
        "informacion_personal_sensible": (
            "Por seguridad, no compartas datos personales sensibles aqui. Para tu cotizacion solo necesito los datos del evento."
        ),
        "contenido_inapropiado_general": (
            "Ese contenido no es pertinente para este servicio. Puedo ayudarte a cotizar bebidas para tu evento."
        ),
        "fuera_de_scope": (
            "Soy el asistente de Tus Eventos y solo puedo ayudarte con cotizaciones de bebidas para eventos. "
            "Si tienes una consulta sobre disponibilidad, precios o paquetes, con gusto te atiendo."
        ),
    }
    return mensajes.get(
        resultado.categoria_detectada,
        "No puedo procesar ese mensaje. Escribeme sobre tu evento y con gusto te cotizo.",
    )
