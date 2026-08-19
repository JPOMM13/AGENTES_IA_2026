"""Catálogo mock y función determinística de utilidad."""

CATALOGO = [
    {
        "id": "OPT-001",
        "nombre": "Pack Celebración",
        "ocasiones": ["cumpleaños", "celebración"],
        "min_personas": 10,
        "max_personas": 30,
        "preferencias": ["práctico", "sencillo"],
        "simplicidad_operativa": 90,
        "disponible": True,
    },
    {
        "id": "OPT-002",
        "nombre": "Pack Reunión Grande",
        "ocasiones": ["reunión", "cumpleaños", "evento"],
        "min_personas": 20,
        "max_personas": 60,
        "preferencias": ["completo"],
        "simplicidad_operativa": 70,
        "disponible": True,
    },
    {
        "id": "OPT-003",
        "nombre": "Pack Íntimo",
        "ocasiones": ["reunión", "celebración"],
        "min_personas": 2,
        "max_personas": 12,
        "preferencias": ["sencillo"],
        "simplicidad_operativa": 95,
        "disponible": True,
    },
]

COBERTURA = {"miraflores", "san isidro", "surco", "barranco"}

PESOS = {
    "occasion_compatibility": 0.30,
    "capacity_fit": 0.20,
    "availability": 0.20,
    "user_preferences": 0.15,
    "budget_fit": 0.10,
    "operational_simplicity": 0.05,
}


def calcular_utilidad(opcion: dict, occasion: str, preferences: list[str]) -> dict:
    """Calcula un score 0..100 con los pesos invariables definidos en el MD."""
    desglose = {
        "occasion_compatibility": 100 if occasion in opcion["ocasiones"] else 50,
        "capacity_fit": 100,
        "availability": 100,
        "user_preferences": 100 if set(preferences) & set(opcion["preferencias"]) else 60,
        "budget_fit": 50,  # Valor neutral: este MVP todavía no trabaja con precios.
        "operational_simplicity": opcion["simplicidad_operativa"],
    }
    utilidad = round(sum(desglose[criterio] * peso for criterio, peso in PESOS.items()), 1)
    return {"utility_score": utilidad, "score_breakdown": desglose}

