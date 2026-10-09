from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from app.agentic_decider import debe_usar_create_agent
from app.guardrails.middleware import invocar_agente_con_guardrails, obtener_middleware_langchain_guardrails
from app.llm_config import obtener_configuracion_llm
from app.estado import EstadoCotizacion


# Ejecuta la responsabilidad de extraer campos con create agente.
def extraer_campos_con_create_agent(mensaje_usuario: str, estado: EstadoCotizacion) -> dict[str, Any]:
    """Usa create_agent para extraer datos explicitos del usuario.

    El LLM interpreta lenguaje natural, pero el workflow consume solo la salida
    estructurada de la tool para reducir alucinaciones.
    """
    if not debe_usar_create_agent():
        return {}
    try:
        agente = obtener_agente_extractor()
        carga_agente = (
            {
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "mensaje_usuario": mensaje_usuario,
                                "current_state": estado.a_diccionario_panel(),
                            },
                            ensure_ascii=False,
                        ),
                    }
                ]
            }
        )
        resultado = invocar_agente_con_guardrails(agente, carga_agente, mensaje_usuario, estado, "agente_extractor")
        if not resultado:
            return {}
        return normalizar_campos_extraidos(extraer_payload_tool(resultado["messages"]), mensaje_usuario)
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
        tipo_evento: str = "",
        asistentes: str = "",
        fecha_evento: str = "",
        distrito: str = "",
        nombre_cliente: str = "",
        contacto: str = "",
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
                "tipo_evento": tipo_evento,
                "asistentes": asistentes,
                "fecha_evento": fecha_evento,
                "distrito": distrito,
                "nombre_cliente": nombre_cliente,
                "contacto": contacto,
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
- Recibiras un JSON con mensaje_usuario y current_state.
- mensaje_usuario es la unica fuente autorizada para nuevos datos.
- current_state solo sirve para entender referencias como "eso", "cambialo" o
  "lo anterior"; no lo uses para inventar campos no mencionados.

REGLAS IMPORTANTES:
- Extrae solo datos explicitamente dichos por el usuario. No inventes.
- No completes informacion faltante por intuicion, por ejemplos o por memoria.
- Si un campo no aparece en mensaje_usuario, envialo vacio.
- Si el usuario dice "JOhn manchego y mi numero es 989515182", nombre_cliente es
  "John Manchego" y contacto es "989515182".
- Normaliza tipo_evento a uno de: matrimonio, cumpleanos, corporativo, reunion,
  aniversario, lanzamiento, fin de ano.
- Normaliza fecha_evento a YYYY-MM-DD solo si hay dia y mes. Usa 2026 si no se
  menciona anio.
- Si falta dia o mes, no llenes fecha_evento; usa partial_day o partial_month.
- requested_products_csv puede incluir solo productos/servicios concretos:
  cerveza, vino, ron, agua, gaseosa, hielo, bartenders, bar movil.
- preferences_csv puede incluir economico, premium, formal, sencillo, separadas
  por coma. No pongas productos aqui.
- Si el usuario quiere revisar, cambiar, agregar o quitar productos, usa
  intent_override=review_order o intent_override=modify_request.
- Si el usuario dice que quiere otra/nueva cotizacion, otro numero, otro
  contacto u otra persona, usa intent_override=new_quote.
- Si el usuario dice que ya tuvo una sesion/conversacion anterior, que ya
  conversaron, que ya dio/dejo todos sus datos, que ya dio datos antes aunque
  escriba con errores como "enteriormente", o que quiere continuar lo anterior,
  usa intent_override=resume_previous. No extraigas datos de evento desde esa
  frase; primero se debe buscar memoria por telefono o correo.
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


# Ejecuta la responsabilidad de extraer carga tool.
def extraer_payload_tool(mensajes: list) -> dict[str, Any]:
    """Recupera el JSON emitido por la tool del agente extractor."""
    for message in reversed(mensajes):
        content = getattr(message, "content", "")
        if not isinstance(content, str):
            continue
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            continue
        if any(key in data for key in ["nombre_cliente", "contacto", "fecha_evento", "requested_products_csv", "preferences_csv"]):
            return data
    return {}


# Ejecuta la responsabilidad de normalizar campos extraidos.
def normalizar_campos_extraidos(carga: dict[str, Any], mensaje_usuario: str) -> dict[str, Any]:
    """Normaliza y acepta solo campos con evidencia en el mensaje."""
    fields: dict[str, Any] = {}
    tipo_evento = limpiar_texto(carga.get("tipo_evento")).lower()
    if tipo_evento and tipo_evento_soportado_y_presente(tipo_evento, mensaje_usuario):
        fields["tipo_evento"] = tipo_evento

    fecha_evento = limpiar_texto(carga.get("fecha_evento"))
    if fecha_evento and contiene_senal_fecha(mensaje_usuario):
        fields["fecha_evento"] = fecha_evento

    for key in ["distrito", "nombre_cliente", "contacto"]:
        value = limpiar_texto(carga.get(key))
        if value and campo_tiene_evidencia_textual(key, value, mensaje_usuario):
            fields[key] = normalizar_nombre(value) if key == "nombre_cliente" else value

    asistentes = limpiar_texto(carga.get("asistentes"))
    if asistentes and asistentes.isdigit() and asistentes in mensaje_usuario:
        fields["asistentes"] = int(asistentes)

    preferencias = [
        limpiar_texto(item).lower()
        for item in limpiar_texto(carga.get("preferences_csv")).split(",")
        if limpiar_texto(item)
    ]
    preferencias = [preference for preference in preferencias if preferencia_soportada_y_presente(preference, mensaje_usuario)]
    if preferencias:
        fields["preferencias"] = preferencias

    productos_solicitados = [
        normalizar_producto_solicitado(limpiar_texto(item).lower())
        for item in limpiar_texto(carga.get("requested_products_csv")).split(",")
        if limpiar_texto(item)
    ]
    productos_solicitados = [
        product
        for product in productos_solicitados
        if product and producto_solicitado_soportado_y_presente(product, mensaje_usuario)
    ]
    if productos_solicitados:
        fields["productos_solicitados"] = productos_solicitados

    intent_override = limpiar_texto(carga.get("intent_override")).lower()
    if intent_override in {"modify_request", "review_order", "resume_previous", "new_quote"}:
        fields["intent_override"] = intent_override

    product_changes = normalizar_cambios_productos(carga, mensaje_usuario)
    if product_changes:
        fields["product_changes"] = product_changes

    fecha_parcial = {
        "dia": parsear_entero(carga.get("partial_day")),
        "mes": parsear_entero(carga.get("partial_month")),
        "anio": parsear_entero(carga.get("partial_year")),
    }
    if any(value is not None for value in fecha_parcial.values()) and contiene_senal_fecha(mensaje_usuario):
        fields["fecha_parcial"] = fecha_parcial

    return fields


# Ejecuta la responsabilidad de limpiar texto.
def limpiar_texto(value: Any) -> str:
    """Limpia valores vacios o placeholders enviados por el LLM."""
    texto = str(value or "").strip(" .,:;`\"'")
    return "" if texto.lower() in {"null", "none", "n/a", "na", "no aplica", "vacio", "vacío"} else texto


# Ejecuta la responsabilidad de parsear entero.
def parsear_entero(value: Any) -> int | None:
    """Convierte texto numerico a entero de forma segura."""
    texto = limpiar_texto(value)
    return int(texto) if texto.isdigit() else None


# Ejecuta la responsabilidad de normalizar nombre.
def normalizar_nombre(value: str) -> str:
    """Capitaliza nombres extraidos para guardarlos consistentemente."""
    return " ".join(part.capitalize() for part in value.split())


# Ejecuta la responsabilidad de contiene senal fecha.
def contiene_senal_fecha(mensaje_usuario: str) -> bool:
    """Confirma que el mensaje contiene una senal real de fecha."""
    texto = mensaje_usuario.lower()
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
    return any(mes in texto for mes in months) or bool(re.search(r"\b\d{1,2}[-/]\d{1,2}\b", texto))


# Ejecuta la responsabilidad de preferencia soportada y presente.
def preferencia_soportada_y_presente(preference: str, mensaje_usuario: str) -> bool:
    """Valida que la preferencia exista literalmente en el mensaje."""
    texto = mensaje_usuario.lower()
    aliases = {
        "economico": ["economico", "económico"],
        "premium": ["premium"],
        "formal": ["formal"],
        "sencillo": ["sencillo"],
    }
    return any(alias in texto for alias in aliases.get(preference, []))


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
def normalizar_cambios_productos(carga: dict[str, Any], mensaje_usuario: str) -> dict[str, list[str]]:
    """Convierte campos CSV del agente en cambios de productos."""
    mapping = {
        "remove": limpiar_texto(carga.get("remove_products_csv")),
        "add": limpiar_texto(carga.get("add_products_csv")),
        "replace_from": limpiar_texto(carga.get("replace_from_csv")),
        "replace_to": limpiar_texto(carga.get("replace_to_csv")),
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
            if product and producto_solicitado_soportado_o_contextual(product, mensaje_usuario, key)
        ]
        if products:
            changes[key] = list(dict.fromkeys(products))
    return changes


# Ejecuta la responsabilidad de producto solicitado soportado y presente.
def producto_solicitado_soportado_y_presente(product: str, mensaje_usuario: str) -> bool:
    """Verifica que el producto soportado fue mencionado por el usuario."""
    texto = mensaje_usuario.lower()
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
    return any(alias in texto for alias in aliases.get(product, []))


# Ejecuta la responsabilidad de producto solicitado soportado o contextual.
def producto_solicitado_soportado_o_contextual(product: str, mensaje_usuario: str, change_key: str) -> bool:
    """Permite reemplazos contextuales cuando el origen viene del estado."""
    if producto_solicitado_soportado_y_presente(product, mensaje_usuario):
        return True
    return change_key == "replace_from"


# Ejecuta la responsabilidad de tipo evento soportado y presente.
def tipo_evento_soportado_y_presente(tipo_evento: str, mensaje_usuario: str) -> bool:
    """Verifica que el tipo de evento soportado tenga evidencia textual."""
    texto = mensaje_usuario.lower()
    aliases = {
        "matrimonio": ["matrimonio", "matriminio", "boda"],
        "cumpleanos": ["cumpleanos", "cumpleaños", "cumple"],
        "corporativo": ["corporativo", "empresa", "corporativa"],
        "reunion": ["reunion", "reunión"],
        "aniversario": ["aniversario"],
        "lanzamiento": ["lanzamiento"],
        "fin de ano": ["fin de ano", "fin de año"],
    }
    return any(alias in texto for alias in aliases.get(tipo_evento, []))


# Ejecuta la responsabilidad de campo tiene evidencia textual.
def campo_tiene_evidencia_textual(key: str, value: str, mensaje_usuario: str) -> bool:
    """Evita aceptar campos del LLM que no aparezcan en el mensaje."""
    texto = mensaje_usuario.lower()
    value_text = value.lower()
    if key == "contacto":
        digits = "".join(char for char in value if char.isdigit())
        return bool(digits and digits in "".join(char for char in mensaje_usuario if char.isdigit())) or value_text in texto
    if key == "nombre_cliente":
        parts = [part for part in value_text.split() if len(part) > 1]
        return bool(parts and all(part in texto for part in parts))
    if key == "distrito":
        return value_text in texto
    return value_text in texto
