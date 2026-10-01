from __future__ import annotations

# MOCK: ESTE CATALOGO DEBERIA VENIR DE POSTGRESQL O DEL API/SISTEMA COMERCIAL DE PRODUCTOS, SERVICIOS Y PAQUETES.
CATALOG = [
    {
        "id": "PKG-BAR-100",
        "name": "Bar movil premium",
        "service": "eventos",
        "event_types": ["matrimonio", "cumpleanos", "corporativo"],
        "capacity_min": 80,
        "capacity_max": 130,
        "base_price": 2800.0,
        "currency": "PEN",
        "image": "app/data/assets/bar_movil_premium.svg",
        "event_affinity": {"matrimonio": 0.95, "cumpleanos": 0.78, "corporativo": 0.74},
        "includes": ["barra movil", "bartender", "cristaleria", "bebidas base"],
    },
    {
        "id": "PKG-BASIC-50",
        "name": "Pack celebracion esencial",
        "service": "botellas",
        "event_types": ["cumpleanos", "reunion", "aniversario", "matrimonio"],
        "capacity_min": 20,
        "capacity_max": 60,
        "base_price": 950.0,
        "currency": "PEN",
        "image": "app/data/assets/pack_celebracion_esencial.svg",
        "event_affinity": {"cumpleanos": 0.9, "reunion": 0.86, "aniversario": 0.82, "matrimonio": 0.55},
        "includes": ["cervezas", "gaseosas", "hielo"],
    },
    {
        "id": "PKG-CORP-150",
        "name": "Servicio corporativo 150",
        "service": "eventos",
        "event_types": ["corporativo", "lanzamiento", "fin de ano"],
        "capacity_min": 100,
        "capacity_max": 180,
        "base_price": 4200.0,
        "currency": "PEN",
        "image": "app/data/assets/servicio_corporativo_150.svg",
        "event_affinity": {"corporativo": 0.96, "lanzamiento": 0.9, "fin de ano": 0.88},
        "includes": ["barra movil", "2 bartenders", "bebidas premium", "coordinador"],
    },
]

# MOCK: ESTOS PRODUCTOS DEBERIAN VENIR DEL MAESTRO REAL DE PRODUCTOS/SERVICIOS, CON CATEGORIAS, FAMILIAS, PRECIOS Y VIGENCIA.
PRODUCTS = [
    {
        "id": "PROD-CERVEZA-001",
        "name": "Cerveza artesanal lata",
        "category": "cerveza",
        "family": "licores",
        "unit": "unidad",
        "unit_price": 8.5,
        "currency": "PEN",
        "event_types": ["matrimonio", "cumpleanos", "reunion", "corporativo"],
    },
    {
        "id": "PROD-VINO-001",
        "name": "Vino tinto reserva",
        "category": "vino",
        "family": "licores",
        "unit": "botella",
        "unit_price": 42.0,
        "currency": "PEN",
        "event_types": ["matrimonio", "aniversario", "corporativo", "reunion"],
    },
    {
        "id": "PROD-RON-001",
        "name": "Ron añejo botella",
        "category": "ron",
        "family": "licores",
        "unit": "botella",
        "unit_price": 38.0,
        "currency": "PEN",
        "event_types": ["matrimonio", "cumpleanos", "reunion", "corporativo"],
    },
    {
        "id": "PROD-GASEOSA-001",
        "name": "Gaseosa 1.5L",
        "category": "gaseosa",
        "family": "sin_alcohol",
        "unit": "botella",
        "unit_price": 9.0,
        "currency": "PEN",
        "event_types": ["matrimonio", "cumpleanos", "reunion", "corporativo"],
    },
    {
        "id": "PROD-AGUA-001",
        "name": "Agua mineral 625ml",
        "category": "agua",
        "family": "sin_alcohol",
        "unit": "botella",
        "unit_price": 2.5,
        "currency": "PEN",
        "event_types": ["matrimonio", "cumpleanos", "reunion", "corporativo"],
    },
    {
        "id": "PROD-HIELO-001",
        "name": "Bolsa de hielo",
        "category": "hielo",
        "family": "complementos",
        "unit": "kg",
        "unit_price": 3.0,
        "currency": "PEN",
        "event_types": ["matrimonio", "cumpleanos", "reunion", "corporativo"],
    },
    {
        "id": "PROD-BARTENDER-001",
        "name": "Servicio bartender",
        "category": "bartenders",
        "family": "servicios",
        "unit": "persona",
        "unit_price": 180.0,
        "currency": "PEN",
        "event_types": ["matrimonio", "corporativo", "cumpleanos", "reunion"],
    },
]

PRODUCT_CATEGORIES = {
    "licores": {
        "categories": ["vino", "cerveza", "ron"],
        "alternatives": {
            "vino": ["ron", "cerveza"],
            "cerveza": ["ron", "vino"],
            "ron": ["cerveza", "vino"],
            "whisky": ["ron", "vino", "cerveza"],
            "pisco": ["ron", "vino"],
            "champagne": ["vino", "ron"],
        },
    },
    "sin_alcohol": {
        "categories": ["agua", "gaseosa"],
        "alternatives": {
            "agua": ["gaseosa"],
            "jugo": ["gaseosa", "agua"],
            "gaseosa": ["agua"],
        },
    },
    "complementos": {
        "categories": ["hielo"],
        "alternatives": {"hielo": []},
    },
    "servicios": {
        "categories": ["bartenders", "bar movil"],
        "alternatives": {"bar movil": ["bartenders"], "bartenders": ["bar movil"]},
    },
}

COVERED_DISTRICTS = {"miraflores", "san isidro", "surco", "barranco", "la molina", "san borja"}

DEFAULT_PRODUCT_STOCK = {
    "PROD-CERVEZA-001": 160,
    "PROD-VINO-001": 40,
    "PROD-RON-001": 35,
    "PROD-GASEOSA-001": 90,
    "PROD-AGUA-001": 70,
    "PROD-HIELO-001": 80,
    "PROD-BARTENDER-001": 3,
}

# MOCK: ESTA DISPONIBILIDAD DEBERIA VENIR DE INVENTARIO/RESERVAS/CALENDARIO OPERATIVO, NO DE UNA CONSTANTE EN CODIGO.
AVAILABILITY = {
    "2026-10-25": {
        "PKG-BAR-100": 2,
        "PKG-BASIC-50": 4,
        "PKG-CORP-150": 0,
        "PROD-CERVEZA-001": 250,
        "PROD-VINO-001": 60,
        "PROD-RON-001": 35,
        "PROD-GASEOSA-001": 120,
        "PROD-AGUA-001": 80,
        "PROD-HIELO-001": 100,
        "PROD-BARTENDER-001": 4,
    },
    "2026-11-15": {
        "PKG-BAR-100": 1,
        "PKG-BASIC-50": 3,
        "PKG-CORP-150": 1,
        "PROD-CERVEZA-001": 180,
        "PROD-VINO-001": 30,
        "PROD-RON-001": 45,
        "PROD-GASEOSA-001": 80,
        "PROD-AGUA-001": 0,
        "PROD-HIELO-001": 70,
        "PROD-BARTENDER-001": 2,
    },
}

# MOCK: ESTA BASE DE CONOCIMIENTO DEBERIA VENIR DEL RAG REAL, CON DOCUMENTOS EN STORAGE Y VECTORES EN PGVECTOR/POSTGRESQL.
MOCK_KNOWLEDGE = [
    {
        "id": "POL-001",
        "title": "Anticipacion minima",
        "text": "Los pedidos deben realizarse con al menos 72 horas de anticipacion.",
        "keywords": ["anticipacion", "72", "horas", "pedido"],
    },
    {
        "id": "POL-002",
        "title": "Feriados",
        "text": "En feriados, la entrega puede realizarse el dia habil anterior y el recojo el dia habil siguiente.",
        "keywords": ["feriado", "feriados", "entrega", "recojo"],
    },
    {
        "id": "POL-003",
        "title": "Descuentos",
        "text": "Los descuentos, convenios y excepciones comerciales deben ser aprobados por un asesor humano.",
        "keywords": ["descuento", "descuentos", "convenio", "excepcion"],
    },
]

WHATSAPP_NUMBER = "51999999999"
