from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.clasificador_intencion import clasificar_intencion_con_llm
from app.guardrails.decision import (
    es_solicitud_generar_cotizacion,
    es_solicitud_nueva_cotizacion,
    es_solicitud_recuperar_memoria,
    validar_override_intencion,
)
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


# TOOL/EXTRACCION HIBRIDA: extrae campos por reglas simples y deja la intencion principal al router LLM estructurado.
def extraer_intencion_y_campos(message: str, estado: EstadoCotizacion) -> dict[str, Any]:
    """Extrae campos del mensaje y resuelve la intencion con el router agentico."""
    texto = message.lower()
    fields: dict[str, Any] = {}

    # ROUTER DE INTENCION: primero el LLM interpreta que quiere hacer el usuario.
    intencion_clasificada = _clasificar_intencion_estructurada(message, estado)

    # EXTRACCION DE CAMPOS: despues de entender la intencion se capturan datos utiles del mensaje.
    product_changes = _extraer_cambios_productos(texto)
    if product_changes:
        fields["product_changes"] = product_changes

    tipo_evento = _extraer_tipo_evento(texto)
    if tipo_evento:
        fields["tipo_evento"] = tipo_evento

    asistentes = _extraer_asistentes(texto)
    if asistentes is None and "asistentes" in estado.campos_faltantes:
        asistentes = _extraer_asistentes_contextuales(texto)
    if asistentes:
        fields["asistentes"] = asistentes

    fecha_evento, error_fecha = _extraer_fecha_validada(texto)
    if error_fecha:
        fields.setdefault("errores_validacion_campos", []).append(error_fecha)
    if fecha_evento:
        fields["fecha_evento"] = fecha_evento
    elif not error_fecha:
        fecha_parcial = _extraer_fecha_parcial(texto)
        if fecha_parcial:
            fields["fecha_parcial"] = fecha_parcial

    distrito = _extraer_distrito(message, esperando_distrito="distrito" in estado.campos_faltantes)
    if distrito:
        fields["distrito"] = distrito

    presupuesto = _extraer_presupuesto(texto)
    if presupuesto:
        fields["presupuesto"] = presupuesto

    if not (distrito and _mensaje_es_distrito_suelto(message, distrito)):
        nombre_cliente = _extraer_nombre_cliente(message)
        if not nombre_cliente and "nombre_cliente" in estado.campos_faltantes:
            nombre_cliente = _extraer_nombre_cliente_contextual(message)
        if nombre_cliente:
            fields["nombre_cliente"] = nombre_cliente

    contacto = _extraer_contacto(message)
    if contacto:
        fields["contacto"] = contacto

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

    # GUARDRAIL DE INTENCION: valida la intencion del LLM contra campos, contexto y respaldo operativo.
    intencion = _resolver_intencion_principal(message, estado, fields, intencion_clasificada)

    return {"intencion": intencion, "fields": fields}


# ROUTER DE INTENCION: usa el LLM estructurado como ruta principal y reglas solo como respaldo si el LLM no responde.
def _resolver_intencion_principal(
    mensaje_usuario: str,
    estado: EstadoCotizacion,
    fields: dict[str, Any],
    intencion_clasificada: str | None,
) -> str:
    """Elige la intencion final con clasificacion LLM y guardrails de seguridad."""
    texto = mensaje_usuario.lower()
    if fields.get("product_changes"):
        return "modificar_pedido"
    if estado.intencion == "retomar_previa" and "contacto" in estado.campos_faltantes and fields.get("contacto"):
        return "retomar_previa"

    if intencion_clasificada:
        return _proteger_intencion_clasificada(intencion_clasificada, fields)

    override_validado = validar_override_intencion(fields.get("intent_override"), texto, estado)
    if override_validado:
        return override_validado

    return _resolver_intencion_respaldo(texto, estado)


# ROUTER DE INTENCION: clasifica cualquier mensaje con LLM estructurado, evitando listas rigidas de frases como ruta principal.
def _clasificar_intencion_estructurada(mensaje_usuario: str, estado: EstadoCotizacion) -> str | None:
    """Clasifica la intencion con el LLM y descarta respuestas con baja confianza."""
    resultado = clasificar_intencion_con_llm(mensaje_usuario, estado)
    if not resultado:
        return None
    if resultado.confianza < 0.35:
        estado.registrar_log(
            "clasificador_intencion_descartado",
            {
                "intencion": resultado.intencion,
                "confianza": resultado.confianza,
                "motivo": "confianza_baja",
            },
        )
        return None
    return resultado.intencion


# GUARDRAIL DE RESPALDO: solo se usa si el LLM esta apagado o falla; no es el router principal del agente.
def _resolver_intencion_respaldo(texto: str, estado: EstadoCotizacion) -> str:
    """Resuelve intenciones criticas sin LLM para pruebas locales y resiliencia operativa."""
    reglas_respaldo = (
        (lambda: es_solicitud_nueva_cotizacion(texto), "nueva_cotizacion"),
        (lambda: es_solicitud_recuperar_memoria(texto), "retomar_previa"),
        (lambda: _es_retomar_contextual(texto), "retomar_previa"),
        (lambda: _es_solo_saludo(texto), "saludo"),
        (lambda: _contiene_alguna(texto, ["ya te di mi nombre", "ya di mi nombre", "te di mi nombre"]), "consulta_memoria"),
        (lambda: _contiene_alguna(texto, ["imagen", "foto", "visual", "muéstrame", "muestrame", "ver como"]), "solicitud_imagen"),
        (lambda: _contiene_alguna(texto, ["cerrar", "finalizar", "terminar conversacion", "terminar conversación"]), "cierre"),
        (lambda: _contiene_alguna(texto, ["asesor", "humano", "whatsapp", "derivame", "derívame"]), "derivacion_humana"),
        (lambda: _contiene_alguna(texto, ["descuento", "rebaja", "menos precio"]), "solicitud_descuento"),
        (lambda: es_solicitud_generar_cotizacion(texto, estado), "cotizacion"),
        (lambda: _contiene_alguna(texto, ["pagar", "pago", "separar", "reservar"]), "solicitud_pago"),
        (lambda: _contiene_alguna(texto, ["cuanto cuesta", "cuánto cuesta", "precio", "cuanto vale", "cuánto vale", "costo"]), "consulta_precio"),
        (lambda: estado.derivacion_ofrecida and _contiene_alguna(texto, ["si", "sí", "ok", "dale", "acepto"]), "confirmacion_derivacion"),
        (lambda: _contiene_alguna(texto, ["revisar pedido", "ver pedido", "mi pedido", "resumen del pedido", "qué tengo", "que tengo"]), "revisar_pedido"),
        (lambda: _contiene_alguna(texto, ["cambiar", "modificar", "quitar", "sacar", "sin ", "reemplaza", "reemplázalo", "reemplazalo", "reemplazar", "otra fecha", "otro distrito"]), "modificar_pedido"),
        (lambda: _contiene_alguna(texto, ["politica", "política", "feriado", "anticipacion", "anticipación"]), "consulta_general"),
    )
    for cumple_regla, intencion in reglas_respaldo:
        if cumple_regla():
            estado.registrar_log("router_intencion_respaldo", {"intencion": intencion})
            return intencion
    estado.registrar_log("router_intencion_respaldo", {"intencion": "recomendacion"})
    return "recomendacion"


# GUARDRAIL DE RESPALDO: reconoce retomar por contexto solo cuando no hubo clasificacion LLM disponible.
def _es_retomar_contextual(texto: str) -> bool:
    """Detecta continuidad de conversacion previa como respaldo deterministico."""
    return _contiene_alguna(texto, ["retomar", "continuar", "seguir"]) and _contiene_alguna(
        texto,
        [
            "cotizacion",
            "cotización",
            "pedido",
            "conversacion",
            "conversación",
            "solicitud",
            "sesion",
            "sesión",
            "session",
            "datos",
        ],
    )


# UTILIDAD DE GUARDRAIL: centraliza busqueda de terminos para que el respaldo no sea una cadena de if/else.
def _contiene_alguna(texto: str, terminos: list[str]) -> bool:
    """Indica si el texto contiene alguna senal definida por guardrails."""
    return any(termino in texto for termino in terminos)


# GUARDRAIL DE ROUTER: evita que una etiqueta del LLM pierda datos explicitos de cotizacion.
def _proteger_intencion_clasificada(intencion_llm: str, fields: dict[str, Any]) -> str:
    """Corrige clasificaciones incompatibles con datos de negocio extraidos."""
    hay_datos_cotizacion = any(
        fields.get(key)
        for key in [
            "tipo_evento",
            "asistentes",
            "fecha_evento",
            "fecha_parcial",
            "distrito",
            "presupuesto",
            "nombre_cliente",
            "contacto",
            "preferencias",
            "productos_solicitados",
            "productos_solicitados_no_soportados",
        ]
    )
    if hay_datos_cotizacion and intencion_llm in {"saludo", "consulta_general", "consulta_memoria", "cierre"}:
        return "recomendacion"
    return intencion_llm


# VALIDACION CONVERSACIONAL: detecta saludos sin datos de cotizacion.
def _es_solo_saludo(texto: str) -> bool:
    """Distingue un saludo simple de una solicitud de cotizacion."""
    cleaned = re.sub(r"[^\wáéíóúñ ]+", " ", texto.lower()).strip()
    senales_cotizacion = [
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
    senales_saludo = ["hola", "buenos dias", "buenos días", "buenas tardes", "buenas noches", "que tal", "qué tal"]
    return any(senal in cleaned for senal in senales_saludo) and not any(senal in cleaned for senal in senales_cotizacion)


# EXTRACCION REGLADA: obtiene tipo de evento desde patrones simples.
def _extraer_tipo_evento(texto: str) -> str | None:
    """Normaliza el tipo de evento a una categoria soportada."""
    for canonical, aliases in EVENT_ALIASES.items():
        if any(alias in texto for alias in aliases):
            return canonical
    if "bebidas" in texto:
        return "reunion"
    return None


# EXTRACCION REGLADA: obtiene cantidad de asistentes cuando aparece explicitamente.
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


# EXTRACCION REGLADA: interpreta numeros contextuales como asistentes cuando corresponde.
def _extraer_asistentes_contextuales(texto: str) -> int | None:
    """Interpreta un numero suelto como asistentes solo si el flujo lo esperaba."""
    match = re.fullmatch(r"\s*(\d{1,4})\s*", texto)
    if match:
        return int(match.group(1))
    return None


# GUARDRAIL DE FECHA: obtiene fecha completa y rechaza fechas imposibles antes de guardar estado.
def _extraer_fecha_validada(texto: str) -> tuple[str | None, str | None]:
    """Extrae fecha completa y devuelve error si el calendario no permite esa fecha."""
    iso = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", texto)
    if iso:
        anio, mes, dia = map(int, iso.groups())
        return _fecha_iso_o_error(anio, mes, dia)

    numeric = re.search(r"(\d{1,2})[-/](\d{1,2})(?:[-/](20\d{2}))?", texto)
    if numeric:
        dia, mes, anio = numeric.groups()
        return _fecha_iso_o_error(int(anio or 2026), int(mes), int(dia))

    for nombre_mes, month_num in MONTHS.items():
        match = re.search(rf"(?:para\s+)?(?:el\s+)?(\d{{1,2}})\s*(?:de\s*)?{nombre_mes}(?:\s*(?:del?|de)?\s*(20\d{{2}}))?", texto)
        if match:
            dia, anio = match.groups()
            return _fecha_iso_o_error(int(anio or 2026), month_num, int(dia))
    return None, None


# GUARDRAIL DE FECHA: valida dia, mes y anio usando calendario real para evitar fechas alucinadas.
def _fecha_iso_o_error(anio: int, mes: int, dia: int) -> tuple[str | None, str | None]:
    """Convierte a ISO solo si la fecha existe en el calendario."""
    try:
        return date(anio, mes, dia).isoformat(), None
    except ValueError:
        return None, f"La fecha indicada no es valida: {dia:02d}/{mes:02d}/{anio}."


# VALIDACION DE FECHA: guarda dia, mes o anio parcial cuando falta completar la fecha.
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


# EXTRACCION REGLADA: obtiene distrito desde el mensaje, incluso si esta fuera de cobertura.
def _extraer_distrito(message: str, esperando_distrito: bool = False) -> str | None:
    """Detecta distrito conocido o distrito libre declarado por el usuario."""
    lowered = message.lower()
    for distrito in DISTRICTS:
        if distrito.lower() in lowered:
            return distrito
    return _extraer_distrito_libre(message, esperando_distrito=esperando_distrito)


# EXTRACCION REGLADA / COBERTURA: captura distritos no cubiertos para que luego la tool de cobertura los rechace claramente.
def _extraer_distrito_libre(message: str, esperando_distrito: bool = False) -> str | None:
    """Extrae un distrito fuera de la lista conocida cuando el usuario lo declara."""
    texto = message.strip()
    posicion_ultimo_en = texto.lower().rfind(" en ")
    if posicion_ultimo_en >= 0:
        candidato_en = _normalizar_distrito_libre(texto[posicion_ultimo_en + 4 :])
        if candidato_en:
            return candidato_en

    if esperando_distrito:
        candidato_suelto = _normalizar_distrito_libre(texto)
        if candidato_suelto:
            return candidato_suelto

    patrones = [
        r"\b(?:el\s+)?distrito\s+es\s+([a-zA-ZáéíóúÁÉÍÓÚñÑ\s]{3,50})\b",
        r"\b([a-zA-ZáéíóúÁÉÍÓÚñÑ\s]{3,50})\s+es\s+el\s+distrito\b",
    ]
    for patron in patrones:
        for match in re.finditer(patron, texto, flags=re.IGNORECASE):
            candidato = _normalizar_distrito_libre(match.group(1))
            if candidato:
                return candidato
    return None


# VALIDACION DE DISTRITO: evita confundir meses, eventos o datos generales con nombres de distrito.
def _normalizar_distrito_libre(value: str) -> str | None:
    """Limpia y valida un distrito libre antes de guardarlo en memoria temporal."""
    partes = re.split(r"\b(?:para|con|mi nombre|mi numero|mi número|telefono|teléfono|correo)\b", value, flags=re.IGNORECASE)
    candidato = partes[-1] if len(partes) > 1 and " en " in value.lower() else partes[0]
    candidato = re.split(r"\b(?:el|para el)\s+\d{1,2}\b|\b\d{1,2}\s+de\b", candidato, maxsplit=1, flags=re.IGNORECASE)[0]
    candidato = re.sub(r"[^a-zA-ZáéíóúÁÉÍÓÚñÑ\s]", " ", candidato)
    candidato = re.sub(r"\s+", " ", candidato).strip(" .,;:")
    if len(candidato) < 3:
        return None
    candidato_lower = candidato.lower()
    palabras = candidato_lower.split()
    if any(mes in candidato_lower for mes in MONTHS):
        return None
    if any(alias in candidato_lower for aliases in EVENT_ALIASES.values() for alias in aliases):
        return None
    if any(palabra in {"personas", "persona", "asistentes", "cotizacion", "cotización", "evento"} for palabra in palabras):
        return None
    return candidato.title()


# VALIDACION DE DISTRITO: detecta respuestas cortas que son solo el distrito pedido, para no tomarlas como nombre.
def _mensaje_es_distrito_suelto(message: str, distrito: str) -> bool:
    """Compara el mensaje normalizado con el distrito extraido."""
    normalizado = _normalizar_distrito_libre(message)
    return normalizado == distrito


# EXTRACCION REGLADA: obtiene presupuesto declarado si existe.
def _extraer_presupuesto(texto: str) -> float | None:
    """Extrae presupuesto si el usuario lo menciona explicitamente."""
    match = re.search(r"(?:presupuesto|hasta|s/|soles)\s*(\d{2,6})", texto)
    if match:
        return float(match.group(1))
    return None


# EXTRACCION REGLADA: obtiene preferencias como economico, premium o tipos de bebida.
def _extraer_preferencias(texto: str) -> list[str]:
    """Extrae preferencias comerciales sin tratarlas como productos."""
    preferencias = []
    for term in ["premium", "economico", "económico", "sencillo", "formal"]:
        if term in texto:
            preferencias.append("economico" if term == "económico" else term)
    return preferencias


# EXTRACCION REGLADA: obtiene productos/servicios solicitados para validar contra catalogo.
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


# EXTRACCION/PRODUCTOS: expone la deteccion reglada para guardrails del workflow.
def extraer_productos_mencionados(mensaje_usuario: str) -> list[str]:
    """Devuelve productos concretos mencionados explicitamente en el turno."""
    return _extraer_productos_solicitados(mensaje_usuario.lower())


# EXTRACCION REGLADA: detecta agregar, quitar o reemplazar productos en el pedido.
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


# VALIDACION DE CATALOGO: separa productos mencionados que no existen en el catalogo.
def _extraer_productos_no_soportados(texto: str, productos_solicitados: list[str]) -> list[str]:
    """Identifica productos pedidos que no existen en el catalogo."""
    unsupported_aliases = {
        "whisky": ["whisky", "whiskey"],
        "pisco": ["pisco"],
        "champagne": ["champagne", "espumante"],
        "tequila": ["tequila"],
        "vodka": ["vodka"],
        "gin": ["gin", "ginebra"],
        "jugo": ["jugo", "jugos"],
        "snacks": ["snack", "snacks", "piqueos", "bocaditos"],
        "torta": ["torta", "tortas", "pastel"],
        "comida": ["comida", "catering", "buffet"],
    }
    unsupported = []
    for canonical, aliases in unsupported_aliases.items():
        if canonical in productos_solicitados:
            continue
        if any(alias in texto for alias in aliases):
            unsupported.append(canonical)
    return unsupported


# EXTRACCION REGLADA: obtiene nombre del cotizante cuando el usuario lo declara.
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


# EXTRACCION REGLADA: infiere nombre solo desde frases contextuales claras.
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


# EXTRACCION REGLADA: obtiene telefono o correo usado para seguimiento y memoria.
def _extraer_contacto(message: str) -> str | None:
    """Extrae correo o telefono de contacto."""
    email = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", message)
    if email:
        return email.group(0)
    phone = re.search(r"(?:\+?51\s*)?\d{9}", message.replace(" ", ""))
    if phone:
        return phone.group(0)
    return None


# EXTRACCION REGLADA: busca nombre cercano al contacto para asociarlo al cotizante.
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


# EXTRACCION REGLADA: busca nombre antes de frases como mi numero es.
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


# VALIDACION DE IDENTIDAD: evita tomar palabras comunes como nombre del cotizante.
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


# AGENTE EXTRACTOR CREATE_AGENT: invoca LLM cuando las reglas no capturan suficiente informacion.
def _extraer_campos_con_agente(message: str, estado: EstadoCotizacion) -> dict[str, Any]:
    """Invoca el extractor con create_agent si esta disponible."""
    try:
        from app.extractor_agentico import extraer_campos_con_create_agent

        return extraer_campos_con_create_agent(message, estado)
    except Exception:
        return {}


# VALIDACION ANTI-ALUCINACION: fusiona campos del LLM solo si no contradicen reglas y evidencia.
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
