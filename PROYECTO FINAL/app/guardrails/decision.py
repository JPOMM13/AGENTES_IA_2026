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


# GUARDRAIL DE DECISION: valida y corrige la accion propuesta por el LLM antes de tocar el workflow.
def validar_decision_agentica(accion: str | None, mensaje_usuario: str, estado: EstadoCotizacion) -> AccionAgente | None:
    """Corrige decisiones del LLM antes de permitir que cambien el flujo."""
    texto = mensaje_usuario.lower()

    if es_solicitud_generar_cotizacion(texto, estado):
        decision_validada = "pedir_campos_faltantes"
        motivo = "cotizacion_sin_minimos"
        if not estado.campos_faltantes:
            decision_validada = "generate_quote" if estado.opcion_recomendada else "validate_and_recommend"
            motivo = "cotizacion_explicita"
        estado.registrar_log(
            "guardrail_decision_agentica",
            {"decision_original": accion, "decision_validada": decision_validada, "motivo": motivo},
        )
        return decision_validada  # type: ignore[return-value]

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

    if estado.intencion == "greeting":
        estado.registrar_log(
            "guardrail_decision_agentica",
            {"decision_original": accion, "decision_validada": None, "motivo": "saludo_simple"},
        )
        return None

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


# VALIDACION DE INTENCION: detecta si el usuario quiere iniciar una cotizacion distinta.
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


# VALIDACION DE INTENCION: acepta un override del extractor solo si tiene evidencia real en el mensaje.
def validar_override_intencion(intent_override: str | None, texto: str, estado: EstadoCotizacion) -> str | None:
    """Valida que la intencion propuesta por el LLM extractor no contradiga el texto."""
    intent = (intent_override or "").strip().lower()
    if intent == "new_quote" and es_solicitud_nueva_cotizacion(texto):
        return "new_quote"
    if intent == "resume_previous" and es_solicitud_recuperar_memoria(texto):
        return "resume_previous"
    if intent == "generate_quote" and es_solicitud_generar_cotizacion(texto, estado):
        return "cotizacion"
    if intent == "modify_request" and es_solicitud_modificar_pedido(texto):
        return "modify_request"
    if intent == "review_order" and es_solicitud_revisar_pedido(texto):
        return "review_order"
    return None


# VALIDACION DE INTENCION: detecta frases para retomar una cotizacion previa desde memoria.
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


# VALIDACION DE INTENCION: detecta una orden explicita o contextual de emitir la cotizacion.
def es_solicitud_generar_cotizacion(texto: str, estado: EstadoCotizacion | None = None) -> bool:
    """Detecta si el usuario ya confirmo que quiere generar la cotizacion."""
    texto = texto.lower()
    frases = [
        "genera la cotizacion",
        "genera la cotización",
        "generame la cotizacion",
        "genérame la cotización",
        "cotizalo",
        "cotízalo",
        "emitir cotizacion",
        "emitir cotización",
        "genera mi cotizacion",
        "genera mi cotización",
        "haz la cotizacion",
        "haz la cotización",
        "hazme la cotizacion",
        "hazme la cotización",
        "hacer la cotizacion",
        "hacer la cotización",
        "emite la cotizacion",
        "emite la cotización",
        "emitela",
        "emítela",
        "emiteme la cotizacion",
        "emíteme la cotización",
        "procedamos",
        "procede con la cotizacion",
        "procede con la cotización",
        "procede con eso",
        "saca la cotizacion",
        "saca la cotización",
        "crea la cotizacion",
        "crea la cotización",
        "prepara la cotizacion",
        "prepara la cotización",
        "mandame la cotizacion",
        "mándame la cotización",
        "haz la proforma",
        "hacer la proforma",
        "emite la proforma",
        "genera la proforma",
        "generame la proforma",
        "genérame la proforma",
    ]
    if any(frase in texto for frase in frases):
        return True

    patrones = [
        r"\b(?:genera|generame|gen[eé]rame|emite|emitir|emiteme|em[ií]teme|haz|hazme|prepara|crea|saca)\b.*\b(?:cotizacion|cotización|proforma)\b",
        r"\b(?:cotizalo|cotízalo|cotizarlo|proformalo|profórmalo)\b",
    ]
    if any(re.search(patron, texto) for patron in patrones):
        return True

    if not estado or estado.campos_faltantes:
        return False
    if not (estado.productos_solicitados or estado.opcion_recomendada):
        return False
    confirmaciones_contextuales = [
        "dale",
        "ok",
        "okay",
        "si",
        "sí",
        "procede",
        "adelante",
        "hazlo",
        "listo",
        "esta bien",
        "está bien",
        "con eso",
        "cerramos",
        "confirmo",
        "confirmado",
    ]
    return any(re.search(rf"\b{re.escape(frase)}\b", texto) for frase in confirmaciones_contextuales)


# VALIDACION DE INTENCION: detecta si el usuario quiere modificar productos o datos del pedido.
def es_solicitud_modificar_pedido(texto: str) -> bool:
    """Detecta modificaciones sobre el pedido actual."""
    return any(
        term in texto
        for term in ["cambiar", "modificar", "quitar", "sacar", "sin ", "reemplaza", "reemplázalo", "reemplazalo", "reemplazar", "otra fecha", "otro distrito"]
    )


# VALIDACION DE INTENCION: detecta si el usuario quiere revisar el pedido actual.
def es_solicitud_revisar_pedido(texto: str) -> bool:
    """Detecta pedidos de revision o resumen del pedido actual."""
    return any(term in texto for term in ["revisar pedido", "ver pedido", "mi pedido", "resumen del pedido", "qué tengo", "que tengo"])


# GUARDRAIL DE DERIVACION: permite derivar a humano solo si el usuario lo pide explicitamente.
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
