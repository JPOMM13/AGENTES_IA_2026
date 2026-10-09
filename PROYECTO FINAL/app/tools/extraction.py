from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.guardrails.decision import es_solicitud_nueva_cotizacion, es_solicitud_recuperar_memoria
from app.estado import EstadoCotizacion


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
def extraer_intencion_y_campos(message: str, estado: EstadoCotizacion) -> dict[str, Any]:
    """Extrae intencion y campos del mensaje combinando reglas y agente."""
    texto = message.lower()
    intencion = _detectar_intencion(texto, estado)
    fields: dict[str, Any] = {}

    product_changes = _extraer_cambios_productos(texto)
    if product_changes:
        fields["product_changes"] = product_changes
        if intencion == "recommendation":
            intencion = "modify_request"

    tipo_evento = _extraer_tipo_evento(texto)
    if tipo_evento:
        fields["tipo_evento"] = tipo_evento

    asistentes = _extraer_asistentes(texto)
    if asistentes is None and "asistentes" in estado.campos_faltantes:
        asistentes = _extraer_asistentes_contextuales(texto)
    if asistentes:
        fields["asistentes"] = asistentes

    fecha_evento = _extraer_fecha(texto)
    if fecha_evento:
        fields["fecha_evento"] = fecha_evento
    else:
        fecha_parcial = _extraer_fecha_parcial(texto)
        if fecha_parcial:
            fields["fecha_parcial"] = fecha_parcial

    distrito = _extraer_distrito(message)
    if distrito:
        fields["distrito"] = distrito

    presupuesto = _extraer_presupuesto(texto)
    if presupuesto:
        fields["presupuesto"] = presupuesto

    nombre_cliente = _extraer_nombre_cliente(message)
    if not nombre_cliente and "nombre_cliente" in estado.campos_faltantes:
        nombre_cliente = _extraer_nombre_cliente_contextual(message)
    if nombre_cliente:
        fields["nombre_cliente"] = nombre_cliente

    contacto = _extraer_contacto(message)
    if contacto:
        fields["contacto"] = contacto
        if estado.intencion == "resume_previous" and "contacto" in estado.campos_faltantes:
            intencion = "resume_previous"

    if not fields.get("nombre_cliente") and contacto:
        customer_name_from_contact = _extraer_nombre_cerca_contacto(message, contacto)
        if customer_name_from_contact:
            fields["nombre_cliente"] = customer_name_from_contact

    preferencias = _extraer_preferencias(texto)
    if preferencias:
        fields["preferencias"] = preferencias

    productos_solicitados = _extraer_productos_solicitados(texto)
    if productos_solicitados:
        fields["productos_solicitados"] = productos_solicitados

    unsupported_products = _extraer_productos_no_soportados(texto, productos_solicitados)
    if unsupported_products:
        fields["productos_solicitados_no_soportados"] = unsupported_products

    agentic_fields = _extraer_campos_con_agente(message, estado)
    fields = _fusionar_campos_agenticos(fields, agentic_fields)
    if fields.get("product_changes"):
        intencion = "modify_request"
    elif intencion not in {"resume_previous", "new_quote", "memory_check", "greeting"} and fields.get("intent_override") in {
        "modify_request",
        "review_order",
        "resume_previous",
        "new_quote",
    }:
        intencion = fields["intent_override"]

    return {"intencion": intencion, "fields": fields}


# Ejecuta logica interna para detectar intencion.
def _detectar_intencion(texto: str, estado: EstadoCotizacion) -> str:
    """Clasifica la intencion principal del usuario para dirigir el flujo."""
    if es_solicitud_nueva_cotizacion(texto):
        return "new_quote"
    if es_solicitud_recuperar_memoria(texto):
        return "resume_previous"
    if any(term in texto for term in ["retomar", "continuar", "seguir"]) and any(
        term in texto for term in ["cotizacion", "cotización", "pedido", "conversacion", "conversación", "solicitud", "sesion", "sesión", "session", "datos"]
    ):
        return "resume_previous"
    if _es_solo_saludo(texto):
        return "greeting"
    if any(term in texto for term in ["ya te di mi nombre", "ya di mi nombre", "te di mi nombre"]):
        return "memory_check"
    if any(term in texto for term in ["imagen", "foto", "visual", "muéstrame", "muestrame", "ver como"]):
        return "image_request"
    if any(term in texto for term in ["cerrar", "finalizar", "terminar conversacion", "terminar conversación"]):
        return "close"
    if any(term in texto for term in ["asesor", "humano", "whatsapp", "derivame", "derívame"]):
        return "human_handoff"
    if any(term in texto for term in ["descuento", "rebaja", "menos precio"]):
        return "discount_request"
    if any(term in texto for term in ["pagar", "pago", "separar", "reservar"]):
        return "payment_request"
    if any(term in texto for term in ["genera la cotizacion", "genera la cotización", "generame la cotizacion", "genérame la cotización", "cotizalo", "cotízalo", "emitir cotizacion", "emitir cotización"]):
        return "cotizacion"
    if any(term in texto for term in ["cuanto cuesta", "cuánto cuesta", "precio", "cuanto vale", "cuánto vale", "costo"]):
        return "price_query"
    if estado.derivacion_ofrecida and any(term in texto for term in ["si", "sí", "ok", "dale", "acepto"]):
        return "handoff_confirmation"
    if any(term in texto for term in ["revisar pedido", "ver pedido", "mi pedido", "resumen del pedido", "qué tengo", "que tengo"]):
        return "review_order"
    if any(term in texto for term in ["cambiar", "modificar", "quitar", "sacar", "sin ", "reemplaza", "reemplázalo", "reemplazalo", "reemplazar", "otra fecha", "otro distrito"]):
        return "modify_request"
    if any(term in texto for term in ["politica", "política", "feriado", "anticipacion", "anticipación"]):
        return "general_question"
    return "recommendation"

# Ejecuta logica interna para es solo saludo.
def _es_solo_saludo(texto: str) -> bool:
    """Distingue un saludo simple de una solicitud de cotizacion."""
    cleaned = re.sub(r"[^\wáéíóúñ ]+", " ", texto.lower()).strip()
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
        "datos",
        "anterior",
        "anteriormente",
        "enteriormente",
        "sesion",
        "sesión",
        "session",
        "conversacion",
        "conversación",
    ]
    greeting_signals = ["hola", "buenos dias", "buenos días", "buenas tardes", "buenas noches", "que tal", "qué tal"]
    return any(signal in cleaned for signal in greeting_signals) and not any(signal in cleaned for signal in quote_signals)


# Ejecuta logica interna para extraer tipo evento.
def _extraer_tipo_evento(texto: str) -> str | None:
    """Normaliza el tipo de evento a una categoria soportada."""
    for canonical, aliases in EVENT_ALIASES.items():
        if any(alias in texto for alias in aliases):
            return canonical
    if "bebidas" in texto:
        return "reunion"
    return None


# Ejecuta logica interna para extraer asistentes.
def _extraer_asistentes(texto: str) -> int | None:
    """Extrae cantidad de asistentes cuando aparece con contexto textual."""
    patterns = [
        r"(\d{1,4})\s*(personas|asistentes|invitados|pax)",
        r"para\s*(\d{1,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, texto)
        if match:
            return int(match.group(1))
    return None


# Ejecuta logica interna para extraer asistentes contextuales.
def _extraer_asistentes_contextuales(texto: str) -> int | None:
    """Interpreta un numero suelto como asistentes solo si el flujo lo esperaba."""
    match = re.fullmatch(r"\s*(\d{1,4})\s*", texto)
    if match:
        return int(match.group(1))
    return None


# Ejecuta logica interna para extraer fecha.
def _extraer_fecha(texto: str) -> str | None:
    """Extrae fecha completa y la normaliza a formato ISO YYYY-MM-DD."""
    iso = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", texto)
    if iso:
        anio, mes, dia = map(int, iso.groups())
        return date(anio, mes, dia).isoformat()

    numeric = re.search(r"(\d{1,2})[-/](\d{1,2})(?:[-/](20\d{2}))?", texto)
    if numeric:
        dia, mes, anio = numeric.groups()
        return date(int(anio or 2026), int(mes), int(dia)).isoformat()

    for nombre_mes, month_num in MONTHS.items():
        match = re.search(rf"(?:para\s+)?(?:el\s+)?(\d{{1,2}})\s*(?:de\s*)?{nombre_mes}(?:\s*(?:del?|de)?\s*(20\d{{2}}))?", texto)
        if match:
            dia, anio = match.groups()
            return date(int(anio or 2026), month_num, int(dia)).isoformat()
    return None


# Ejecuta logica interna para extraer fecha parcial.
def _extraer_fecha_parcial(texto: str) -> dict[str, int | None] | None:
    """Extrae dia, mes o anio incompleto cuando falta parte de la fecha."""
    partial: dict[str, int | None] = {"dia": None, "mes": None, "anio": None}
    for nombre_mes, month_num in MONTHS.items():
        if nombre_mes in texto:
            partial["mes"] = month_num
            break

    day_match = re.search(r"(?:para\s+el|el|dia|día)\s+(\d{1,2})(?:\b|$)", texto)
    if day_match:
        possible_day = int(day_match.group(1))
        if 1 <= possible_day <= 31:
            partial["dia"] = possible_day

    year_match = re.search(r"\b(20\d{2})\b", texto)
    if year_match:
        partial["anio"] = int(year_match.group(1))

    return partial if any(value is not None for value in partial.values()) else None


# Ejecuta logica interna para extraer distrito.
def _extraer_distrito(message: str) -> str | None:
    """Detecta distrito usando la lista de cobertura conocida."""
    lowered = message.lower()
    for distrito in DISTRICTS:
        if distrito.lower() in lowered:
            return distrito
    return None


# Ejecuta logica interna para extraer presupuesto.
def _extraer_presupuesto(texto: str) -> float | None:
    """Extrae presupuesto si el usuario lo menciona explicitamente."""
    match = re.search(r"(?:presupuesto|hasta|s/|soles)\s*(\d{2,6})", texto)
    if match:
        return float(match.group(1))
    return None


# Ejecuta logica interna para extraer preferencias.
def _extraer_preferencias(texto: str) -> list[str]:
    """Extrae preferencias comerciales sin tratarlas como productos."""
    preferencias = []
    for term in ["premium", "economico", "económico", "sencillo", "formal"]:
        if term in texto:
            preferencias.append("economico" if term == "económico" else term)
    return preferencias


# Ejecuta logica interna para extraer productos solicitados.
def _extraer_productos_solicitados(texto: str) -> list[str]:
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
        if any(alias in texto for alias in aliases):
            requested.append(canonical)
    return requested


# Ejecuta logica interna para extraer cambios productos.
def _extraer_cambios_productos(texto: str) -> dict[str, list[str]]:
    """Detecta acciones de agregar, quitar o reemplazar productos."""
    products = _extraer_productos_solicitados(texto)
    changes: dict[str, list[str]] = {"remove": [], "add": [], "replace_from": [], "replace_to": []}
    if any(term in texto for term in ["quitar", "quita", "sacar", "saca", "sin ", "no quiero", "ya no quiero"]):
        changes["remove"].extend(products)
    if any(term in texto for term in ["agrega", "agregar", "añade", "anade", "incluye", "sumar"]):
        changes["add"].extend(products)

    replace_match = re.search(r"(?:cambia|cambiar|reemplaza|reemplazar)\s+(.+?)\s+por\s+(.+)", texto)
    if replace_match:
        changes["replace_from"].extend(_extraer_productos_solicitados(replace_match.group(1)))
        changes["replace_to"].extend(_extraer_productos_solicitados(replace_match.group(2)))
    implicit_replace_match = re.search(r"(?:reemplazalo|reemplázalo|cambialo|cámbialo)\s+por\s+(.+)", texto)
    if implicit_replace_match:
        changes["replace_to"].extend(_extraer_productos_solicitados(implicit_replace_match.group(1)))

    return {key: unique for key, values in changes.items() if (unique := list(dict.fromkeys(values)))}


# Ejecuta logica interna para extraer productos no soportados.
def _extraer_productos_no_soportados(texto: str, productos_solicitados: list[str]) -> list[str]:
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
        if canonical in productos_solicitados:
            continue
        if any(alias in texto for alias in aliases):
            unsupported.append(canonical)
    return unsupported


# Ejecuta logica interna para extraer nombre cliente.
def _extraer_nombre_cliente(message: str) -> str | None:
    """Extrae nombre del cotizante desde frases explicitas."""
    patterns = [
        r"(?:me llamo|soy|mi nombre es)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]{2,40})",
        r"(?:a nombre de)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]{2,40})",
        r"(?:es para|para)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ ]{2,40})",
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


# Ejecuta logica interna para extraer nombre cliente contextual.
def _extraer_nombre_cliente_contextual(message: str) -> str | None:
    """Extrae un nombre cuando el flujo esta esperando solo el cotizante."""
    cleaned = message.strip(" .,:;")
    if re.fullmatch(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúñ]+){1,3}", cleaned):
        if not any(token.lower() in _stopwords_nombre() for token in cleaned.split()):
            return cleaned.title()
    match = re.search(
        r"(?:es\s+para|para)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúñ]+){1,3})",
        message,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).strip(" .,:;").title()
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
def _extraer_nombre_cerca_contacto(message: str, contacto: str) -> str | None:
    """Busca un nombre cercano al telefono cuando no hubo frase directa."""
    prefix_name = _extraer_nombre_antes_frase_contacto(message)
    if prefix_name:
        return prefix_name

    texto = re.sub(r"\b(?:mi\s+)?(?:telefono|teléfono|numero|número|celular|contacto)\s*(?:es|:)?\s*", " ", message, flags=re.IGNORECASE)
    texto = texto.replace(contacto, " ")
    texto = re.sub(r"\+?51?\d{9}", " ", texto)
    texto = re.sub(r"\d+", " ", texto)
    texto = re.sub(r"\b(?:mi|me|llamo|soy|es|y|el|la|para|personas|numero|número|telefono|teléfono)\b", " ", texto, flags=re.IGNORECASE)
    candidates = re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3}\b", texto)
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
    district_tokens = {token.lower() for distrito in DISTRICTS for token in distrito.split()}
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
def _extraer_campos_con_agente(message: str, estado: EstadoCotizacion) -> dict[str, Any]:
    """Invoca el extractor con create_agent si esta disponible."""
    try:
        from app.agentic_extractor import extraer_campos_con_create_agent

        return extraer_campos_con_create_agent(message, estado)
    except Exception:
        return {}


# Ejecuta logica interna para fusionar campos agenticos.
def _fusionar_campos_agenticos(fields: dict[str, Any], agentic_fields: dict[str, Any]) -> dict[str, Any]:
    """Combina extraccion deterministica y agentica sin perder evidencias."""
    merged = dict(fields)
    for key, value in agentic_fields.items():
        if value in (None, "", []):
            continue
        if key == "preferencias":
            existing = merged.setdefault("preferencias", [])
            for preference in value:
                if preference not in existing:
                    existing.append(preference)
            continue
        if key == "productos_solicitados":
            existing = merged.setdefault("productos_solicitados", [])
            for product in value:
                if product not in existing:
                    existing.append(product)
            continue
        if key == "productos_solicitados_no_soportados":
            existing = merged.setdefault("productos_solicitados_no_soportados", [])
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
        if key == "fecha_parcial":
            if not merged.get("fecha_evento"):
                merged[key] = value
            continue
        merged.setdefault(key, value)
    return merged
