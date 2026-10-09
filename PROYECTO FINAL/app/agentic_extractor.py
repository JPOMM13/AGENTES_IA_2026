from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from app.agentic_decider import debe_usar_create_agent
from app.guardrails.middleware import invocar_agente_con_guardrails, obtener_middleware_langchain_guardrails
from app.llm_config import obtener_configuracion_llm
from app.state import QuoteState


# Ejecuta la responsabilidad de extraer campos con create agent.
def extraer_campos_con_create_agent(user_message: str, state: QuoteState) -> dict[str, Any]:
    """Usa create_agent para extraer datos explicitos del usuario.

    El LLM interpreta lenguaje natural, pero el workflow consume solo la salida
    estructurada de la tool para reducir alucinaciones.
    """
    if not debe_usar_create_agent():
        return {}
    try:
        agent = obtener_agente_extractor()
        carga_agente = (
            {
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "user_message": user_message,
                                "current_state": state.a_diccionario_panel(),
                            },
                            ensure_ascii=False,
                        ),
                    }
                ]
            }
        )
        result = invocar_agente_con_guardrails(agent, carga_agente, user_message, state, "agente_extractor")
        if not result:
            return {}
        return normalizar_campos_extraidos(extraer_payload_tool(result["messages"]), user_message)
    except Exception:
        return {}


# Ejecuta la responsabilidad de obtener agente extractor.
@lru_cache(maxsize=1)
def obtener_agente_extractor():
    """Devuelve el agente extractor cacheado para reutilizarlo por turno."""
    return crear_agente_extractor()


# Ejecuta la responsabilidad de crear agente extractor.
def crear_agente_extractor():
    """Crea el agente extractor con create_agent usando el LLM configurado."""
    from langchain.agents import create_agent
    from langchain.tools import tool

    # Ejecuta la responsabilidad de registrar campos extraidos.
    @tool
    def registrar_campos_extraidos(
        event_type: str = "",
        attendees: str = "",
        event_date: str = "",
        district: str = "",
        customer_name: str = "",
        contact: str = "",
        requested_products_csv: str = "",
        preferences_csv: str = "",
        intent_override: str = "",
        remove_products_csv: str = "",
        add_products_csv: str = "",
        replace_from_csv: str = "",
        replace_to_csv: str = "",
        partial_day: str = "",
        partial_month: str = "",
        partial_year: str = "",
    ) -> str:
        """Registra los campos explicitamente detectados en el mensaje del usuario."""
        return json.dumps(
            {
                "event_type": event_type,
                "attendees": attendees,
                "event_date": event_date,
                "district": district,
                "customer_name": customer_name,
                "contact": contact,
                "requested_products_csv": requested_products_csv,
                "preferences_csv": preferences_csv,
                "intent_override": intent_override,
                "remove_products_csv": remove_products_csv,
                "add_products_csv": add_products_csv,
                "replace_from_csv": replace_from_csv,
                "replace_to_csv": replace_to_csv,
                "partial_day": partial_day,
                "partial_month": partial_month,
                "partial_year": partial_year,
            },
            ensure_ascii=False,
        )

    system_prompt = """
Eres el extractor de datos de un workflow agentico para cotizar eventos.
Tu tarea es extraer informacion estructurada del mensaje del usuario y llamar
exactamente una vez la tool registrar_campos_extraidos.

CONTEXTO:
- Recibiras un JSON con user_message y current_state.
- user_message es la unica fuente autorizada para nuevos datos.
- current_state solo sirve para entender referencias como "eso", "cambialo" o
  "lo anterior"; no lo uses para inventar campos no mencionados.

REGLAS IMPORTANTES:
- Extrae solo datos explicitamente dichos por el usuario. No inventes.
- No completes informacion faltante por intuicion, por ejemplos o por memoria.
- Si un campo no aparece en user_message, envialo vacio.
- Si el usuario dice "JOhn manchego y mi numero es 989515182", customer_name es
  "John Manchego" y contact es "989515182".
- Normaliza event_type a uno de: matrimonio, cumpleanos, corporativo, reunion,
  aniversario, lanzamiento, fin de ano.
- Normaliza event_date a YYYY-MM-DD solo si hay dia y mes. Usa 2026 si no se
  menciona anio.
- Si falta dia o mes, no llenes event_date; usa partial_day o partial_month.
- requested_products_csv puede incluir solo productos/servicios concretos:
  cerveza, vino, ron, agua, gaseosa, hielo, bartenders, bar movil.
- preferences_csv puede incluir economico, premium, formal, sencillo, separadas
  por coma. No pongas productos aqui.
- Si el usuario quiere revisar, cambiar, agregar o quitar productos, usa
  intent_override=review_order o intent_override=modify_request.
- Para modificar productos usa remove_products_csv, add_products_csv,
  replace_from_csv y replace_to_csv.
- Si dice "cambialo por gaseosa" y hay un producto pendiente/no disponible en
  current_state, deja replace_from_csv vacio y usa replace_to_csv=gaseosa.
- No generes cotizacion, no consultes stock y no respondas al usuario final.

FORMATO DE SALIDA:
- Llama exactamente una vez la tool registrar_campos_extraidos.
- No devuelvas texto libre fuera de la tool.
"""
    config = obtener_configuracion_llm()
    agente = create_agent(
        model=config.modelo_langchain,
        tools=[registrar_campos_extraidos],
        system_prompt=system_prompt,
        middleware=obtener_middleware_langchain_guardrails(),
    )
    return agente


# Ejecuta la responsabilidad de extraer payload tool.
def extraer_payload_tool(messages: list) -> dict[str, Any]:
    """Recupera el JSON emitido por la tool del agente extractor."""
    for message in reversed(messages):
        content = getattr(message, "content", "")
        if not isinstance(content, str):
            continue
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            continue
        if any(key in data for key in ["customer_name", "contact", "event_date", "requested_products_csv", "preferences_csv"]):
            return data
    return {}


# Ejecuta la responsabilidad de normalizar campos extraidos.
def normalizar_campos_extraidos(payload: dict[str, Any], user_message: str) -> dict[str, Any]:
    """Normaliza y acepta solo campos con evidencia en el mensaje."""
    fields: dict[str, Any] = {}
    event_type = limpiar_texto(payload.get("event_type")).lower()
    if event_type and tipo_evento_soportado_y_presente(event_type, user_message):
        fields["event_type"] = event_type

    event_date = limpiar_texto(payload.get("event_date"))
    if event_date and contiene_senal_fecha(user_message):
        fields["event_date"] = event_date

    for key in ["district", "customer_name", "contact"]:
        value = limpiar_texto(payload.get(key))
        if value and campo_tiene_evidencia_textual(key, value, user_message):
            fields[key] = normalizar_nombre(value) if key == "customer_name" else value

    attendees = limpiar_texto(payload.get("attendees"))
    if attendees and attendees.isdigit() and attendees in user_message:
        fields["attendees"] = int(attendees)

    preferences = [
        limpiar_texto(item).lower()
        for item in limpiar_texto(payload.get("preferences_csv")).split(",")
        if limpiar_texto(item)
    ]
    preferences = [preference for preference in preferences if preferencia_soportada_y_presente(preference, user_message)]
    if preferences:
        fields["preferences"] = preferences

    requested_products = [
        normalizar_producto_solicitado(limpiar_texto(item).lower())
        for item in limpiar_texto(payload.get("requested_products_csv")).split(",")
        if limpiar_texto(item)
    ]
    requested_products = [
        product
        for product in requested_products
        if product and producto_solicitado_soportado_y_presente(product, user_message)
    ]
    if requested_products:
        fields["requested_products"] = requested_products

    intent_override = limpiar_texto(payload.get("intent_override")).lower()
    if intent_override in {"modify_request", "review_order"}:
        fields["intent_override"] = intent_override

    product_changes = normalizar_cambios_productos(payload, user_message)
    if product_changes:
        fields["product_changes"] = product_changes

    partial_date = {
        "day": parsear_entero(payload.get("partial_day")),
        "month": parsear_entero(payload.get("partial_month")),
        "year": parsear_entero(payload.get("partial_year")),
    }
    if any(value is not None for value in partial_date.values()) and contiene_senal_fecha(user_message):
        fields["partial_date"] = partial_date

    return fields


# Ejecuta la responsabilidad de limpiar texto.
def limpiar_texto(value: Any) -> str:
    """Limpia valores vacios o placeholders enviados por el LLM."""
    text = str(value or "").strip(" .,:;`\"'")
    return "" if text.lower() in {"null", "none", "n/a", "na", "no aplica", "vacio", "vacío"} else text


# Ejecuta la responsabilidad de parsear entero.
def parsear_entero(value: Any) -> int | None:
    """Convierte texto numerico a entero de forma segura."""
    text = limpiar_texto(value)
    return int(text) if text.isdigit() else None


# Ejecuta la responsabilidad de normalizar nombre.
def normalizar_nombre(value: str) -> str:
    """Capitaliza nombres extraidos para guardarlos consistentemente."""
    return " ".join(part.capitalize() for part in value.split())


# Ejecuta la responsabilidad de contiene senal fecha.
def contiene_senal_fecha(user_message: str) -> bool:
    """Confirma que el mensaje contiene una senal real de fecha."""
    text = user_message.lower()
    months = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "setiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    return any(month in text for month in months) or bool(re.search(r"\b\d{1,2}[-/]\d{1,2}\b", text))


# Ejecuta la responsabilidad de preferencia soportada y presente.
def preferencia_soportada_y_presente(preference: str, user_message: str) -> bool:
    """Valida que la preferencia exista literalmente en el mensaje."""
    text = user_message.lower()
    aliases = {
        "economico": ["economico", "económico"],
        "premium": ["premium"],
        "formal": ["formal"],
        "sencillo": ["sencillo"],
    }
    return any(alias in text for alias in aliases.get(preference, []))


# Ejecuta la responsabilidad de normalizar producto solicitado.
def normalizar_producto_solicitado(value: str) -> str:
    """Mapea alias de productos a categorias canonicas."""
    mapping = {
        "cervezas": "cerveza",
        "vinos": "vino",
        "rones": "ron",
        "gaseosas": "gaseosa",
        "gaseosa": "gaseosa",
        "aguas": "agua",
        "bartender": "bartenders",
        "barra movil": "bar movil",
        "barra móvil": "bar movil",
        "bar móvil": "bar movil",
    }
    return mapping.get(value, value)


# Ejecuta la responsabilidad de normalizar cambios productos.
def normalizar_cambios_productos(payload: dict[str, Any], user_message: str) -> dict[str, list[str]]:
    """Convierte campos CSV del agente en cambios de productos."""
    mapping = {
        "remove": limpiar_texto(payload.get("remove_products_csv")),
        "add": limpiar_texto(payload.get("add_products_csv")),
        "replace_from": limpiar_texto(payload.get("replace_from_csv")),
        "replace_to": limpiar_texto(payload.get("replace_to_csv")),
    }
    changes: dict[str, list[str]] = {}
    for key, csv_value in mapping.items():
        products = [
            normalizar_producto_solicitado(limpiar_texto(item).lower())
            for item in csv_value.split(",")
            if limpiar_texto(item)
        ]
        products = [
            product
            for product in products
            if product and producto_solicitado_soportado_o_contextual(product, user_message, key)
        ]
        if products:
            changes[key] = list(dict.fromkeys(products))
    return changes


# Ejecuta la responsabilidad de producto solicitado soportado y presente.
def producto_solicitado_soportado_y_presente(product: str, user_message: str) -> bool:
    """Verifica que el producto soportado fue mencionado por el usuario."""
    text = user_message.lower()
    aliases = {
        "cerveza": ["cerveza", "cervezas"],
        "vino": ["vino", "vinos"],
        "ron": ["ron"],
        "agua": ["agua", "aguas"],
        "gaseosa": ["gaseosa", "gaseosas"],
        "hielo": ["hielo"],
        "bartenders": ["bartender", "bartenders"],
        "bar movil": ["bar movil", "bar móvil", "barra movil", "barra móvil"],
    }
    return any(alias in text for alias in aliases.get(product, []))


# Ejecuta la responsabilidad de producto solicitado soportado o contextual.
def producto_solicitado_soportado_o_contextual(product: str, user_message: str, change_key: str) -> bool:
    """Permite reemplazos contextuales cuando el origen viene del estado."""
    if producto_solicitado_soportado_y_presente(product, user_message):
        return True
    return change_key == "replace_from"


# Ejecuta la responsabilidad de tipo evento soportado y presente.
def tipo_evento_soportado_y_presente(event_type: str, user_message: str) -> bool:
    """Verifica que el tipo de evento soportado tenga evidencia textual."""
    text = user_message.lower()
    aliases = {
        "matrimonio": ["matrimonio", "matriminio", "boda"],
        "cumpleanos": ["cumpleanos", "cumpleaños", "cumple"],
        "corporativo": ["corporativo", "empresa", "corporativa"],
        "reunion": ["reunion", "reunión"],
        "aniversario": ["aniversario"],
        "lanzamiento": ["lanzamiento"],
        "fin de ano": ["fin de ano", "fin de año"],
    }
    return any(alias in text for alias in aliases.get(event_type, []))


# Ejecuta la responsabilidad de campo tiene evidencia textual.
def campo_tiene_evidencia_textual(key: str, value: str, user_message: str) -> bool:
    """Evita aceptar campos del LLM que no aparezcan en el mensaje."""
    text = user_message.lower()
    value_text = value.lower()
    if key == "contact":
        digits = "".join(char for char in value if char.isdigit())
        return bool(digits and digits in "".join(char for char in user_message if char.isdigit())) or value_text in text
    if key == "customer_name":
        parts = [part for part in value_text.split() if len(part) > 1]
        return bool(parts and all(part in text for part in parts))
    if key == "district":
        return value_text in text
    return value_text in text
