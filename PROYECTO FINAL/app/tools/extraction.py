from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.state import QuoteState


EVENT_ALIASES = {
    "matrimonio": ["matrimonio", "matriminio", "boda"],
    "cumpleanos": ["cumpleanos", "cumple", "cumpleaños"],
    "corporativo": ["corporativo", "empresa", "corporativa"],
    "reunion": ["reunion", "reunión"],
    "aniversario": ["aniversario"],
    "lanzamiento": ["lanzamiento"],
    "fin de ano": ["fin de ano", "fin de año"],
}

DISTRICTS = ["Miraflores", "San Isidro", "Surco", "Barranco", "La Molina", "San Borja", "Chosica"]

MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


# Ejecuta la responsabilidad de extraer intencion y campos.
def extraer_intencion_y_campos(message: str, state: QuoteState) -> dict[str, Any]:
    """Extrae intencion y campos del mensaje combinando reglas y agente."""
    text = message.lower()
    intent = _detectar_intencion(text, state)
    fields: dict[str, Any] = {}

    product_changes = _extraer_cambios_productos(text)
    if product_changes:
        fields["product_changes"] = product_changes
        if intent == "recommendation":
            intent = "modify_request"

    event_type = _extraer_tipo_evento(text)
    if event_type:
        fields["event_type"] = event_type

    attendees = _extraer_asistentes(text)
    if attendees is None and "attendees" in state.missing_fields:
        attendees = _extraer_asistentes_contextuales(text)
    if attendees:
        fields["attendees"] = attendees

    event_date = _extraer_fecha(text)
    if event_date:
        fields["event_date"] = event_date
    else:
        partial_date = _extraer_fecha_parcial(text)
        if partial_date:
            fields["partial_date"] = partial_date

    district = _extraer_distrito(message)
    if district:
        fields["district"] = district

    budget = _extraer_presupuesto(text)
    if budget:
        fields["budget"] = budget

    customer_name = _extraer_nombre_cliente(message)
    if customer_name:
        fields["customer_name"] = customer_name

    contact = _extraer_contacto(message)
    if contact:
        fields["contact"] = contact

    if not fields.get("customer_name") and contact:
        customer_name_from_contact = _extraer_nombre_cerca_contacto(message, contact)
        if customer_name_from_contact:
            fields["customer_name"] = customer_name_from_contact

    preferences = _extraer_preferencias(text)
    if preferences:
        fields["preferences"] = preferences

    requested_products = _extraer_productos_solicitados(text)
    if requested_products:
        fields["requested_products"] = requested_products

    unsupported_products = _extraer_productos_no_soportados(text, requested_products)
    if unsupported_products:
        fields["unsupported_requested_products"] = unsupported_products

    agentic_fields = _extraer_campos_con_agente(message, state)
    fields = _fusionar_campos_agenticos(fields, agentic_fields)
    if fields.get("product_changes"):
        intent = "modify_request"
    elif intent not in {"resume_previous", "memory_check", "greeting"} and fields.get("intent_override") in {"modify_request", "review_order"}:
        intent = fields["intent_override"]

    return {"intent": intent, "fields": fields}


# Ejecuta logica interna para detectar intencion.
def _detectar_intencion(text: str, state: QuoteState) -> str:
    """Clasifica la intencion principal del usuario para dirigir el flujo."""
    if any(
        phrase in text
        for phrase in [
            "ya te di datos",
            "ya te di mis datos",
            "ya di mis datos",
            "te di mis datos",
            "ya te deje datos",
            "ya te dejé datos",
            "deje datos anteriormente",
            "dejé datos anteriormente",
            "datos anteriormente",
            "otra session",
            "otra sesión",
            "sesion anterior",
            "sesión anterior",
            "interaccion anterior",
            "interacción anterior",
            "ya tuve una interaccion",
            "ya tuve una interacción",
            "conversacion que tuvimos",
            "conversación que tuvimos",
            "conversacion anterior",
            "conversación anterior",
            "seguir con la conversacion",
            "seguir con la conversación",
            "seguir con mi conversacion",
            "seguir con mi conversación",
            "deje algun dato",
            "dejé algún dato",
            "sabes cuales son",
            "sabes cuáles son",
        ]
    ):
        return "resume_previous"
    if any(term in text for term in ["retomar", "continuar", "seguir"]) and any(
        term in text for term in ["cotizacion", "cotización", "pedido", "conversacion", "conversación", "solicitud"]
    ):
        return "resume_previous"
    if _es_solo_saludo(text):
        return "greeting"
    if any(term in text for term in ["ya te di mi nombre", "ya di mi nombre", "te di mi nombre"]):
        return "memory_check"
    if any(term in text for term in ["imagen", "foto", "visual", "muéstrame", "muestrame", "ver como"]):
        return "image_request"
    if any(term in text for term in ["cerrar", "finalizar", "terminar conversacion", "terminar conversación"]):
        return "close"
    if any(term in text for term in ["asesor", "humano", "whatsapp", "derivame", "derívame"]):
        return "human_handoff"
    if any(term in text for term in ["descuento", "rebaja", "menos precio"]):
        return "discount_request"
    if any(term in text for term in ["pagar", "pago", "separar", "reservar"]):
        return "payment_request"
    if any(term in text for term in ["genera la cotizacion", "genera la cotización", "generame la cotizacion", "genérame la cotización", "cotizalo", "cotízalo", "emitir cotizacion", "emitir cotización"]):
        return "quote"
    if any(term in text for term in ["cuanto cuesta", "cuánto cuesta", "precio", "cuanto vale", "cuánto vale", "costo"]):
        return "price_query"
    if state.handoff_offered and any(term in text for term in ["si", "sí", "ok", "dale", "acepto"]):
        return "handoff_confirmation"
    if any(term in text for term in ["revisar pedido", "ver pedido", "mi pedido", "resumen del pedido", "qué tengo", "que tengo"]):
        return "review_order"
    if any(term in text for term in ["cambiar", "modificar", "quitar", "sacar", "sin ", "reemplaza", "reemplázalo", "reemplazalo", "reemplazar", "otra fecha", "otro distrito"]):
        return "modify_request"
    if any(term in text for term in ["politica", "política", "feriado", "anticipacion", "anticipación"]):
        return "general_question"
    return "recommendation"


# Ejecuta logica interna para es solo saludo.
def _es_solo_saludo(text: str) -> bool:
    """Distingue un saludo simple de una solicitud de cotizacion."""
    cleaned = re.sub(r"[^\wáéíóúñ ]+", " ", text.lower()).strip()
    quote_signals = [
        "cotizacion",
        "cotización",
        "evento",
        "matrimonio",
        "personas",
        "vino",
        "cerveza",
        "gaseosa",
        "hielo",
        "precio",
    ]
    greeting_signals = ["hola", "buenos dias", "buenos días", "buenas tardes", "buenas noches", "que tal", "qué tal"]
    return any(signal in cleaned for signal in greeting_signals) and not any(signal in cleaned for signal in quote_signals)


# Ejecuta logica interna para extraer tipo evento.
def _extraer_tipo_evento(text: str) -> str | None:
    """Normaliza el tipo de evento a una categoria soportada."""
    for canonical, aliases in EVENT_ALIASES.items():
        if any(alias in text for alias in aliases):
            return canonical
    if "bebidas" in text:
        return "reunion"
    return None


# Ejecuta logica interna para extraer asistentes.
def _extraer_asistentes(text: str) -> int | None:
    """Extrae cantidad de asistentes cuando aparece con contexto textual."""
    patterns = [
        r"(\d{1,4})\s*(personas|asistentes|invitados|pax)",
        r"para\s*(\d{1,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


# Ejecuta logica interna para extraer asistentes contextuales.
def _extraer_asistentes_contextuales(text: str) -> int | None:
    """Interpreta un numero suelto como asistentes solo si el flujo lo esperaba."""
    match = re.fullmatch(r"\s*(\d{1,4})\s*", text)
    if match:
        return int(match.group(1))
    return None


# Ejecuta logica interna para extraer fecha.
def _extraer_fecha(text: str) -> str | None:
    """Extrae fecha completa y la normaliza a formato ISO YYYY-MM-DD."""
    iso = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", text)
    if iso:
        year, month, day = map(int, iso.groups())
        return date(year, month, day).isoformat()

    numeric = re.search(r"(\d{1,2})[-/](\d{1,2})(?:[-/](20\d{2}))?", text)
    if numeric:
        day, month, year = numeric.groups()
        return date(int(year or 2026), int(month), int(day)).isoformat()

    for nombre_mes, month_num in MONTHS.items():
        match = re.search(rf"(?:para\s+)?(?:el\s+)?(\d{{1,2}})\s*(?:de\s*)?{nombre_mes}(?:\s*(?:del?|de)?\s*(20\d{{2}}))?", text)
        if match:
            day, year = match.groups()
            return date(int(year or 2026), month_num, int(day)).isoformat()
    return None


# Ejecuta logica interna para extraer fecha parcial.
def _extraer_fecha_parcial(text: str) -> dict[str, int | None] | None:
    """Extrae dia, mes o anio incompleto cuando falta parte de la fecha."""
    partial: dict[str, int | None] = {"day": None, "month": None, "year": None}
    for nombre_mes, month_num in MONTHS.items():
        if nombre_mes in text:
            partial["month"] = month_num
            break

    day_match = re.search(r"(?:para\s+el|el|dia|día)\s+(\d{1,2})(?:\b|$)", text)
    if day_match:
        possible_day = int(day_match.group(1))
        if 1 <= possible_day <= 31:
            partial["day"] = possible_day

    year_match = re.search(r"\b(20\d{2})\b", text)
    if year_match:
        partial["year"] = int(year_match.group(1))

    return partial if any(value is not None for value in partial.values()) else None


# Ejecuta logica interna para extraer distrito.
def _extraer_distrito(message: str) -> str | None:
    """Detecta distrito usando la lista de cobertura conocida."""
    lowered = message.lower()
    for district in DISTRICTS:
        if district.lower() in lowered:
            return district
    return None


# Ejecuta logica interna para extraer presupuesto.
def _extraer_presupuesto(text: str) -> float | None:
    """Extrae presupuesto si el usuario lo menciona explicitamente."""
    match = re.search(r"(?:presupuesto|hasta|s/|soles)\s*(\d{2,6})", text)
    if match:
        return float(match.group(1))
    return None


# Ejecuta logica interna para extraer preferencias.
def _extraer_preferencias(text: str) -> list[str]:
    """Extrae preferencias comerciales sin tratarlas como productos."""
    preferences = []
    for term in ["premium", "economico", "económico", "sencillo", "formal"]:
        if term in text:
            preferences.append("economico" if term == "económico" else term)
    return preferences


# Ejecuta logica interna para extraer productos solicitados.
def _extraer_productos_solicitados(text: str) -> list[str]:
    """Extrae productos o servicios concretos solicitados por el usuario."""
    product_aliases = {
        "cerveza": ["cerveza", "cervezas"],
        "vino": ["vino", "vinos"],
        "ron": ["ron"],
        "gaseosa": ["gaseosa", "gaseosas"],
        "agua": ["agua", "aguas"],
        "hielo": ["hielo"],
        "bartenders": ["bartender", "bartenders"],
        "bar movil": ["bar movil", "bar móvil", "barra movil", "barra móvil"],
    }
    requested = []
    for canonical, aliases in product_aliases.items():
        if any(alias in text for alias in aliases):
            requested.append(canonical)
    return requested


# Ejecuta logica interna para extraer cambios productos.
def _extraer_cambios_productos(text: str) -> dict[str, list[str]]:
    """Detecta acciones de agregar, quitar o reemplazar productos."""
    products = _extraer_productos_solicitados(text)
    changes: dict[str, list[str]] = {"remove": [], "add": [], "replace_from": [], "replace_to": []}
    if any(term in text for term in ["quitar", "quita", "sacar", "saca", "sin ", "no quiero", "ya no quiero"]):
        changes["remove"].extend(products)
    if any(term in text for term in ["agrega", "agregar", "añade", "anade", "incluye", "sumar"]):
        changes["add"].extend(products)

    replace_match = re.search(r"(?:cambia|cambiar|reemplaza|reemplazar)\s+(.+?)\s+por\s+(.+)", text)
    if replace_match:
        changes["replace_from"].extend(_extraer_productos_solicitados(replace_match.group(1)))
        changes["replace_to"].extend(_extraer_productos_solicitados(replace_match.group(2)))
    implicit_replace_match = re.search(r"(?:reemplazalo|reemplázalo|cambialo|cámbialo)\s+por\s+(.+)", text)
    if implicit_replace_match:
        changes["replace_to"].extend(_extraer_productos_solicitados(implicit_replace_match.group(1)))

    return {key: unique for key, values in changes.items() if (unique := list(dict.fromkeys(values)))}


# Ejecuta logica interna para extraer productos no soportados.
def _extraer_productos_no_soportados(text: str, requested_products: list[str]) -> list[str]:
    """Identifica productos pedidos que no existen en el catalogo mock."""
    unsupported_aliases = {
        "whisky": ["whisky", "whiskey"],
        "pisco": ["pisco"],
        "champagne": ["champagne", "espumante"],
        "jugo": ["jugo", "jugos"],
        "snacks": ["snack", "snacks", "piqueos", "bocaditos"],
    }
    unsupported = []
    for canonical, aliases in unsupported_aliases.items():
        if canonical in requested_products:
            continue
        if any(alias in text for alias in aliases):
            unsupported.append(canonical)
    return unsupported


# Ejecuta logica interna para extraer nombre cliente.
def _extraer_nombre_cliente(message: str) -> str | None:
    """Extrae nombre del cotizante desde frases explicitas."""
    patterns = [
        r"(?:me llamo|soy|mi nombre es)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]{2,40})",
        r"(?:a nombre de)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]{2,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            name = match.group(1).strip(" .,:;")
            stop_words = [" y ", " para ", " con ", " el ", " mi "]
            for stop_word in stop_words:
                if stop_word in name.lower():
                    name = name[: name.lower().index(stop_word)].strip()
            return name.title()
    return None


# Ejecuta logica interna para extraer contacto.
def _extraer_contacto(message: str) -> str | None:
    """Extrae correo o telefono de contacto."""
    email = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", message)
    if email:
        return email.group(0)
    phone = re.search(r"(?:\+?51\s*)?\d{9}", message.replace(" ", ""))
    if phone:
        return phone.group(0)
    return None


# Ejecuta logica interna para extraer nombre cerca contacto.
def _extraer_nombre_cerca_contacto(message: str, contact: str) -> str | None:
    """Busca un nombre cercano al telefono cuando no hubo frase directa."""
    prefix_name = _extraer_nombre_antes_frase_contacto(message)
    if prefix_name:
        return prefix_name

    text = re.sub(r"\b(?:mi\s+)?(?:telefono|teléfono|numero|número|celular|contacto)\s*(?:es|:)?\s*", " ", message, flags=re.IGNORECASE)
    text = text.replace(contact, " ")
    text = re.sub(r"\+?51?\d{9}", " ", text)
    text = re.sub(r"\d+", " ", text)
    text = re.sub(r"\b(?:mi|me|llamo|soy|es|y|el|la|para|personas|numero|número|telefono|teléfono)\b", " ", text, flags=re.IGNORECASE)
    candidates = re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3}\b", text)
    if not candidates:
        return None
    name = max(candidates, key=len).strip()
    return name.title() if len(name) >= 2 else None


# Ejecuta logica interna para extraer nombre antes frase contacto.
def _extraer_nombre_antes_frase_contacto(message: str) -> str | None:
    """Obtiene posible nombre ubicado antes de una frase de contacto."""
    explicit_name = re.search(
        r"\bpara\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]{2,40}?)(?:,\s*)?(?:\+?51\s*)?\d{9}\b",
        message,
        flags=re.IGNORECASE,
    )
    if explicit_name:
        return explicit_name.group(1).strip(" .,:;").title()

    split = re.split(
        r"\b(?:y\s+)?(?:mi\s+)?(?:telefono|teléfono|numero|número|celular|contacto)\b|\b\d{9}\b",
        message,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    if not split:
        return None
    prefix = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ\s]", " ", split[0])
    district_tokens = {token.lower() for district in DISTRICTS for token in district.split()}
    tokens = [
        token
        for token in prefix.split()
        if token.lower() not in _stopwords_nombre() and token.lower() not in district_tokens
    ]
    if not tokens:
        return None
    candidate = tokens[-3:]
    if len(candidate) > 1 and candidate[0].lower() in {"para", "de"}:
        candidate = candidate[1:]
    name = " ".join(candidate).strip()
    return name.title() if len(name) >= 2 else None


# Ejecuta logica interna para stopwords nombre.
def _stopwords_nombre() -> set[str]:
    """Lista palabras que no deben formar parte del nombre detectado."""
    return {
        "mi",
        "me",
        "llamo",
        "soy",
        "es",
        "y",
        "el",
        "la",
        "para",
        "personas",
        "numero",
        "número",
        "telefono",
        "teléfono",
        "contacto",
        "con",
        "que",
        "sea",
    }


# Ejecuta logica interna para extraer campos con agente.
def _extraer_campos_con_agente(message: str, state: QuoteState) -> dict[str, Any]:
    """Invoca el extractor con create_agent si esta disponible."""
    try:
        from app.agentic_extractor import extraer_campos_con_create_agent

        return extraer_campos_con_create_agent(message, state)
    except Exception:
        return {}


# Ejecuta logica interna para fusionar campos agenticos.
def _fusionar_campos_agenticos(fields: dict[str, Any], agentic_fields: dict[str, Any]) -> dict[str, Any]:
    """Combina extraccion deterministica y agentica sin perder evidencias."""
    merged = dict(fields)
    for key, value in agentic_fields.items():
        if value in (None, "", []):
            continue
        if key == "preferences":
            existing = merged.setdefault("preferences", [])
            for preference in value:
                if preference not in existing:
                    existing.append(preference)
            continue
        if key == "requested_products":
            existing = merged.setdefault("requested_products", [])
            for product in value:
                if product not in existing:
                    existing.append(product)
            continue
        if key == "unsupported_requested_products":
            existing = merged.setdefault("unsupported_requested_products", [])
            for product in value:
                if product not in existing:
                    existing.append(product)
            continue
        if key == "product_changes":
            existing = merged.setdefault("product_changes", {})
            for change_key, products in value.items():
                existing_products = existing.setdefault(change_key, [])
                for product in products:
                    if product not in existing_products:
                        existing_products.append(product)
            continue
        if key == "intent_override":
            merged[key] = value
            continue
        if key == "partial_date":
            if not merged.get("event_date"):
                merged[key] = value
            continue
        merged.setdefault(key, value)
    return merged
