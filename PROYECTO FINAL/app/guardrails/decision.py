from __future__ import annotations

import re
from typing import Literal

from app.estado import EstadoCotizacion


AccionAgente = Literal[
    "pedir_campos_faltantes",
    "answer_price",
    "validate_and_recommend",
    "generate_quote",
    "show_image",
    "handoff",
    "answer_policy",
    "close",
    "resume_previous",
    "new_quote",
]


# Ejecuta la responsabilidad de validar decision agentica.
def validar_decision_agentica(accion: str | None, mensaje_usuario: str, estado: EstadoCotizacion) -> AccionAgente | None:
    """Corrige decisiones del LLM antes de permitir que cambien el flujo."""
    texto = mensaje_usuario.lower()

    if estado.intencion == "new_quote" or es_solicitud_nueva_cotizacion(texto):
        estado.registrar_log(
            "guardrail_decision_agentica",
            {"decision_original": accion, "decision_validada": "new_quote", "motivo": "nueva_cotizacion"},
        )
        return "new_quote"

    if estado.intencion == "resume_previous" or es_solicitud_recuperar_memoria(texto):
        estado.registrar_log(
            "guardrail_decision_agentica",
            {"decision_original": accion, "decision_validada": "resume_previous", "motivo": "recuperacion_memoria"},
        )
        return "resume_previous"

    if accion == "handoff" and not es_derivacion_humana_explicita(texto):
        estado.registrar_log(
            "guardrail_decision_agentica",
            {"decision_original": accion, "decision_validada": None, "motivo": "derivacion_no_explicita"},
        )
        return None

    if accion == "generate_quote" and (estado.campos_faltantes or not estado.opcion_recomendada):
        estado.registrar_log(
            "guardrail_decision_agentica",
            {"decision_original": accion, "decision_validada": "pedir_campos_faltantes", "motivo": "cotizacion_sin_prerequisitos"},
        )
        return "pedir_campos_faltantes"

    if accion == "show_image" and not estado.cotizacion:
        estado.registrar_log(
            "guardrail_decision_agentica",
            {"decision_original": accion, "decision_validada": "pedir_campos_faltantes", "motivo": "imagen_sin_cotizacion"},
        )
        return "pedir_campos_faltantes"

    if accion == "validate_and_recommend" and estado.campos_faltantes:
        estado.registrar_log(
            "guardrail_decision_agentica",
            {"decision_original": accion, "decision_validada": "pedir_campos_faltantes", "motivo": "recomendacion_sin_minimos"},
        )
        return "pedir_campos_faltantes"

    if accion in {
        "pedir_campos_faltantes",
        "answer_price",
        "validate_and_recommend",
        "generate_quote",
        "show_image",
        "handoff",
        "answer_policy",
        "close",
        "resume_previous",
        "new_quote",
    }:
        estado.registrar_log(
            "guardrail_decision_agentica",
            {"decision_original": accion, "decision_validada": accion, "motivo": "permitida"},
        )
        return accion  # type: ignore[return-value]

    return None


# Ejecuta la responsabilidad de es solicitud nueva cotizacion.
def es_solicitud_nueva_cotizacion(texto: str) -> bool:
    """Detecta si el usuario quiere abandonar la cotizacion actual y crear otra."""
    texto = texto.lower()
    if any(termino in texto for termino in ["anterior", "previa", "previo", "retomar", "recuperar"]):
        return False
    frases = [
        "otra cotizacion",
        "otra cotización",
        "nueva cotizacion",
        "nueva cotización",
        "nuevo pedido",
        "nueva solicitud",
        "otra solicitud",
        "otra persona",
        "otro cliente",
        "otro numero",
        "otro número",
        "otro contacto",
    ]
    if any(frase in texto for frase in frases):
        return True
    patrones = [
        r"\b(?:hacer|crear|empezar|iniciar)\s+otra\s+(?:cotizacion|cotización|solicitud)\b",
        r"\b(?:hacer|crear|empezar|iniciar)\s+una\s+nueva\s+(?:cotizacion|cotización|solicitud)\b",
    ]
    return any(re.search(patron, texto) for patron in patrones)


# Ejecuta la responsabilidad de es solicitud recuperar memoria.
def es_solicitud_recuperar_memoria(texto: str) -> bool:
    """Detecta si el usuario quiere retomar informacion de una sesion anterior."""
    frases = [
        "datos anteriormente",
        "datos enteriormente",
        "datos anterior mente",
        "otra session",
        "otra sesión",
        "session antes",
        "sesion antes",
        "sesión antes",
        "sesion anterior",
        "sesión anterior",
        "interaccion anterior",
        "interacción anterior",
        "conversacion que tuvimos",
        "conversación que tuvimos",
        "conversacion anterior",
        "conversación anterior",
        "ya tuvimos una session",
        "ya tuvimos una sesion",
        "ya tuvimos una sesión",
        "tuvimos una session",
        "tuvimos una sesion",
        "tuvimos una sesión",
        "seguir con la conversacion",
        "seguir con la conversación",
        "seguir con mi conversacion",
        "seguir con mi conversación",
        "deje algun dato",
        "dejé algún dato",
        "sabes cuales son",
        "sabes cuáles son",
    ]
    if any(frase in texto for frase in frases):
        return True

    patrones = [
        r"\bya\s+te\s+(?:di|dije|dire|dir[eé]|deje|dej[eé])\s+(?:(?:todos|toda)\s+)?(?:mis|los|esos|estos)?\s*datos\b",
        r"\bya\s+(?:di|dije|dire|dir[eé]|deje|dej[eé])\s+(?:(?:todos|toda)\s+)?(?:mis|los|esos|estos)?\s*datos\b",
        r"\bte\s+(?:di|dije|dire|dir[eé]|deje|dej[eé])\s+(?:(?:todos|toda)\s+)?(?:mis|los|esos|estos)?\s*datos\b",
        r"\b(?:di|dije|dire|dir[eé]|deje|dej[eé])\s+(?:(?:todos|toda)\s+)?(?:mis|los|esos|estos)?\s*datos\s+(?:anteriormente|enteriormente)\b",
        r"\bdatos\b.*\b(?:anteriormente|enteriormente|antes)\b",
        r"\bya\s+tuve\s+.*\b(?:session|sesion|sesión|interaccion|interacción|conversacion|conversación)\b",
        r"\b(?:ya\s+)?tuvimos\s+.*\b(?:session|sesion|sesión|interaccion|interacción|conversacion|conversación)\b",
        r"\b(?:session|sesion|sesión)\s+contigo\b",
        r"\bquiero\s+continuarla\b",
    ]
    return any(re.search(patron, texto) for patron in patrones)


# Ejecuta la responsabilidad de es derivacion humana explicita.
def es_derivacion_humana_explicita(texto: str) -> bool:
    """Valida que la derivacion humana haya sido pedida por el usuario."""
    return any(
        termino in texto
        for termino in [
            "asesor",
            "humano",
            "whatsapp",
            "derivame",
            "derívame",
            "pasame con alguien",
            "pásame con alguien",
            "hablar con alguien",
            "atencion humana",
            "atención humana",
        ]
    )
