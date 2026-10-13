from __future__ import annotations

from typing import Any

from langchain.agents.middleware import PIIMiddleware

from app.guardrails.entrada import validar_mensaje_entrada
from app.guardrails.salida import validar_salida_agente
from app.estado import EstadoCotizacion
from app.modelo_agentico import construir_config_invocacion_agentica

try:
    from langgraph.errors import GraphRecursionError
except ImportError:  # pragma: no cover - compatibilidad con versiones sin esta excepcion publica.
    GraphRecursionError = None  # type: ignore[assignment]


# RESUMEN: ESTE MODULO FUNCIONA COMO MIDDLEWARE ENTRE EL WORKFLOW Y CREATE_AGENT.
# RESUMEN: VALIDA LA ENTRADA ANTES DE INVOCAR EL AGENTE Y VALIDA LA SALIDA
# DEL AGENTE ANTES DE QUE EL WORKFLOW USE SU RESULTADO. ADEMAS DEFINE
# MIDDLEWARE NATIVO DE LANGCHAIN PARA CREATE_AGENT.


# GUARDRAIL MIDDLEWARE CREATE_AGENT: configura PIIMiddleware nativo para entradas del agente.
def obtener_middleware_langchain_guardrails() -> list:
    """
    Devuelve middlewares nativos para pasarlos directamente a create_agent.

    DECISION DE DISENO:
    - Telefono: PERMITIDO — es el dato de contacto requerido para la cotizacion.
    - Nombre del cliente: PERMITIDO — requerido para personalizar la cotizacion.
    - Tarjetas de credito: ENMASCARADO — no son necesarias para cotizar; protegemos al usuario.
    - API keys: BLOQUEADO — nunca deben circular por el workflow del agente.
    """
    return [
        # Enmascara numeros de tarjeta antes de enviar el mensaje al modelo.
        # Los datos de pago no son necesarios para cotizar bebidas.
        PIIMiddleware(
            "credit_card",
            strategy="mask",
            apply_to_input=True,
        ),
        # Bloquea posibles API keys antes de enviar el mensaje al modelo.
        # Una API key en el chat es siempre un error del usuario; la protegemos.
        PIIMiddleware(
            "api_key",
            detector=r"sk-[a-zA-Z0-9_-]{20,}",
            strategy="block",
            apply_to_input=True,
        ),
    ]


# GUARDRAIL MIDDLEWARE CREATE_AGENT: valida entrada, invoca el agente y valida salida estructurada.
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
        resultado = agente.invoke(carga_agente, config=construir_config_invocacion_agentica())
    except Exception as exc:
        if GraphRecursionError is not None and isinstance(exc, GraphRecursionError):
            estado.registrar_log(
                "agente_recursion_error",
                {"agente": nombre_agente, "error": str(exc)},
            )
            return None
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
