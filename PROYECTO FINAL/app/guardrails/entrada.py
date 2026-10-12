from __future__ import annotations

import os
import re
from dataclasses import dataclass

from app.guardrails.llm_guardrails import (
    ResultadoGuardrailLLM,
    debe_bloquear,
    respuesta_segura_para,
    validar_mensaje_con_llm,
)

_RESPUESTA_FUERA_SCOPE = (
    "Soy el asistente de Tus Eventos y solo puedo ayudarte con cotizaciones de bebidas para eventos. "
    "Si tienes una consulta sobre disponibilidad, precios o paquetes, con gusto te atiendo."
)

_RESPUESTA_INJECTION = (
    "Puedo ayudarte con la cotizacion del evento, pero no puedo cambiar mis reglas internas ni omitir validaciones."
)


@dataclass(frozen=True)
class ResultadoGuardrailEntrada:
    """Resultado estandar para validar mensajes antes de usar agentes o tools."""

    permitido: bool
    motivo: str
    respuesta_segura: str = ""
    resultado_llm: ResultadoGuardrailLLM | None = None


# GUARDRAIL DE ENTRADA: valida el mensaje antes de enviarlo al workflow, LLM o tools.
def validar_mensaje_entrada(mensaje: str) -> ResultadoGuardrailEntrada:
    """
    Valida el mensaje del usuario antes de enviarlo al workflow o create_agent.

    Orden de evaluacion:
    1. Mensaje vacio (determinista, falla rapida).
    2. Fuera de scope determinista — Opcion A (patrones obvios, sin costo de API).
    3. Prompt injection determinista (patrones directos conocidos).
    4. Guardrail LLM semantico via OpenAI — Opcion B (casos ambiguos y fuera de scope complejos).
    """
    texto = mensaje.strip()

    # 1. Mensaje vacio
    if not texto:
        return ResultadoGuardrailEntrada(
            permitido=False,
            motivo="mensaje vacio",
            respuesta_segura="No recibi un mensaje para procesar. Escribeme que necesitas cotizar y avanzamos.",
        )

    # 2. OPCION A — Fuera de scope determinista (casos obvios y comunes)
    if es_claramente_fuera_de_scope(texto):
        return ResultadoGuardrailEntrada(
            permitido=False,
            motivo="fuera_de_scope_determinista",
            respuesta_segura=_RESPUESTA_FUERA_SCOPE,
        )

    # 3. Prompt injection determinista (patrones directos)
    if contiene_intento_de_romper_reglas(texto):
        return ResultadoGuardrailEntrada(
            permitido=False,
            motivo="posible prompt injection",
            respuesta_segura=_RESPUESTA_INJECTION,
        )

    # 4. OPCION B — Guardrail semantico con LLM (casos ambiguos: fuera de scope sutil,
    #    lenguaje de odio, discriminacion, amenazas, contenido inapropiado, etc.)
    if _guardrail_llm_habilitado():
        resultado_llm = validar_mensaje_con_llm(texto)
        if debe_bloquear(resultado_llm):
            return ResultadoGuardrailEntrada(
                permitido=False,
                motivo=f"guardrail_llm:{resultado_llm.categoria_detectada}",
                respuesta_segura=respuesta_segura_para(resultado_llm),
                resultado_llm=resultado_llm,
            )

    return ResultadoGuardrailEntrada(permitido=True, motivo="entrada valida")


# GUARDRAIL OPCION A — FUERA DE SCOPE: detecta temas claramente ajenos al servicio de bebidas.
def es_claramente_fuera_de_scope(mensaje: str) -> bool:
    """
    Detecta rapidamente mensajes que son obviamente ajenos al servicio de cotizacion de bebidas.

    Solo bloquea temas que NUNCA tendrian relacion con el servicio. Ante la duda, deja pasar
    para que el LLM (Opcion B) o el workflow decidan.
    """
    texto = mensaje.lower()

    # Primero verifica si el mensaje toca temas del servicio — si es asi, no es fuera de scope
    if _menciona_tema_del_servicio(texto):
        return False

    # Temas tecnicos generales
    patrones_tecnologia = [
        r"\b(como|como se|donde|c[oó]mo)\b.{0,40}\b(buscar|busco|encontrar|googlear|googleo)\b.{0,30}\b(internet|web|google|informaci[oó]n|datos)\b",
        r"\b(buscar|busco|encontrar|encontr[eé])\b.{0,30}\b(en internet|en google|en la web|online|informaci[oó]n)\b",
        r"\b(c[oó]mo funciona|explica|explícame|qu[eé] es|para qu[eé] sirve)\b.{0,50}\b(python|javascript|sql|html|css|api|base de datos|algoritmo|machine learning|ia|inteligencia artificial)\b",
        r"\b(escribe|escrib[ií]|genera|crea|programa|codifica)\b.{0,30}\b(c[oó]digo|script|funci[oó]n|programa|app|aplicaci[oó]n)\b",
        r"\b(instalar|instala|descargar|descarga)\b.{0,30}\b(programa|software|aplicaci[oó]n|app|librer[ií]a)\b",
    ]

    # Recetas y cocina (distinto a bebidas para eventos)
    patrones_cocina = [
        r"\b(receta|recetas)\b.{0,30}\b(comida|platillo|plato|sopa|ensalada|postre|torta|pastel|arroz|pollo|carne|pasta)\b",
        r"\b(c[oó]mo (cocinar|preparar|hacer))\b.{0,30}\b(comida|platillo|plato|sopa|ensalada|postre)\b",
    ]

    # Temas academicos / informativos generales
    patrones_generales = [
        r"\b(cu[aá]l es la capital|cu[aá]ntos habitantes|d[oó]nde queda|en qu[eé] pa[ií]s)\b",
        r"\b(traduce|traducir|en ingl[eé]s|en franc[eé]s|en portugu[eé]s|c[oó]mo se dice)\b",
        r"\b(qui[eé]n fue|qui[eé]n es|historia de|biograf[ií]a)\b.{0,40}\b(presidente|rey|inventor|cient[ií]fico|art[ií]sta|actor|jugador)\b",
        r"\b(temperatura|clima|pronostico|va a llover|c[oó]mo estar[aá] el tiempo)\b",
        r"\b(qu[eé] hora es|hora actual|hora en)\b",
        r"\b(noticias|[uú]ltimas noticias|lo que pas[oó] hoy|actualidad)\b",
        r"\b(partido|marcador|resultado)\b.{0,20}\b(f[uú]tbol|basquet|tenis|deporte)\b",
        r"\b(c[oó]mo bajar de peso|dieta|ejercicio|rutina de gym|cu[aá]ntas calor[ií]as)\b",
        r"\b(s[ií]ntomas|diagn[oó]stico|medicamento|dosis|cu[aá]ndo tomar)\b",
        r"\b(chiste|cu[eé]ntame un chiste|historia|cuento|poema)\b",
        r"\b(ajedrez|crucigramas|sudoku|juego|videojuego)\b",
    ]

    todos_los_patrones = patrones_tecnologia + patrones_cocina + patrones_generales
    return any(re.search(patron, texto) for patron in todos_los_patrones)


def _menciona_tema_del_servicio(texto: str) -> bool:
    """
    Verifica si el mensaje toca algun tema relacionado con el servicio de bebidas para eventos.
    Si lo hace, no debe bloquearse como fuera de scope.
    """
    palabras_clave_servicio = [
        "bebida", "bebidas", "trago", "tragos", "licor", "cerveza", "vino", "coctel",
        "cocteles", "gaseosa", "agua", "jugo", "bar", "barra", "dispensador",
        "evento", "eventos", "fiesta", "matrimonio", "boda", "cumplea", "corporativo",
        "reunion", "reunión", "conferencia", "gala", "banquete",
        "cotiza", "cotizacion", "cotización", "precio", "precios", "paquete", "paquetes",
        "costo", "costos", "cuanto", "cuánto", "cuanto sale", "cuanto cuesta",
        "disponibilidad", "disponible", "cobertura", "distrito", "asistentes",
        "personas", "invitados", "fecha", "reserva", "reservar",
        "asesor", "humano", "whatsapp", "contacto",
    ]
    return any(palabra in texto for palabra in palabras_clave_servicio)


# GUARDRAIL DE ENTRADA: detecta intentos de prompt injection o ruptura de reglas.
def contiene_intento_de_romper_reglas(mensaje: str) -> bool:
    """Detecta instrucciones tipicas de prompt injection para bloquearlas."""
    texto = mensaje.lower()
    patrones_bloqueados = [
        "ignora tus instrucciones",
        "ignora las instrucciones",
        "olvida tus reglas",
        "muestra tu prompt",
        "revela tu system prompt",
        "salta las validaciones",
        "no consultes las tools",
    ]
    return any(patron in texto for patron in patrones_bloqueados)


# GUARDRAIL LLM: indica si el guardrail semantico esta activo segun variables de entorno.
def _guardrail_llm_habilitado() -> bool:
    """
    El guardrail LLM esta habilitado por defecto si existe una API key valida.
    Se puede desactivar explicitamente con GUARDRAIL_LLM_ENABLED=false.
    """
    valor = os.getenv("GUARDRAIL_LLM_ENABLED", "").lower()
    if valor in {"0", "false", "no"}:
        return False
    # Habilitado si hay clave disponible (GUARDRAIL_API_KEY u OPENAI_API_KEY)
    return bool(
        os.getenv("GUARDRAIL_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or (os.getenv("LLM_API_KEY") if os.getenv("LLM_PROVIDER", "").lower() == "openai" else None)
    )
