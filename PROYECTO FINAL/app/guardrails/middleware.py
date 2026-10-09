from __future__ import annotations

from typing import Any

from langchain.agents.middleware import PIIMiddleware

from app.guardrails.entrada import validar_mensaje_entrada
from app.guardrails.salida import validar_salida_agente
from app.estado import EstadoCotizacion


# RESUMEN: ESTE MODULO FUNCIONA COMO MIDDLEWARE ENTRE EL WORKFLOW Y CREATE_AGENT.
# RESUMEN: VALIDA LA ENTRADA ANTES DE INVOCAR EL AGENTE Y VALIDA LA SALIDA
# DEL AGENTE ANTES DE QUE EL WORKFLOW USE SU RESULTADO. ADEMAS DEFINE
# MIDDLEWARE NATIVO DE LANGCHAIN PARA CREATE_AGENT.


# Ejecuta la responsabilidad de obtener middleware langchain guardrails.
def obtener_middleware_langchain_guardrails() -> list:
    """Devuelve middlewares nativos para pasarlos directamente a create_agent."""
    return [
        # Redacta correos antes de enviar el mensaje al modelo.
        PIIMiddleware(
            "email",
            strategy="redact",
            apply_to_input=True,
        ),
        # Enmascara tarjetas antes de enviar el mensaje al modelo.
        PIIMiddleware(
            "credit_card",
            strategy="mask",
            apply_to_input=True,
        ),
        # Bloquea posibles API keys antes de enviar el mensaje al modelo.
        PIIMiddleware(
            "api_key",
            detector=r"sk-[a-zA-Z0-9_-]{20,}",
            strategy="block",
            apply_to_input=True,
        ),
    ]


# Ejecuta la responsabilidad de invocar agente con guardrails.
def invocar_agente_con_guardrails(
    agente: Any,
    carga_agente: dict[str, Any],
    mensaje_usuario: str,
    estado: EstadoCotizacion,
    nombre_agente: str,
) -> dict[str, Any] | None:
    """Envuelve create_agent.invoke con guardrail de entrada y salida."""
    validacion_entrada = validar_mensaje_entrada(mensaje_usuario)
    if not validacion_entrada.permitido:
        estado.registrar_log(
            "guardrail_middleware_entrada_bloqueada",
            {"agente": nombre_agente, "motivo": validacion_entrada.motivo},
        )
        return None

    try:
        resultado = agente.invoke(carga_agente)
    except Exception as exc:
        estado.registrar_log(
            "guardrail_middleware_error_agente",
            {"agente": nombre_agente, "error": str(exc)},
        )
        return None

    validacion_salida = validar_salida_agente(resultado, nombre_agente)
    estado.registrar_log(
        "guardrail_middleware_salida_agente",
        {"agente": nombre_agente, "permitido": validacion_salida.permitido, "motivo": validacion_salida.motivo},
    )
    if not validacion_salida.permitido:
        return None
    return resultado
