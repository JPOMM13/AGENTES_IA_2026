import json
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from src.config import DATA_DIR


# Carga un archivo JSON desde la carpeta data.
def load_json(filename: str) -> list[dict[str, Any]]:
    with open(DATA_DIR / filename, encoding="utf-8") as file:
        return json.load(file)


# Normaliza el texto para comparar palabras sin tildes ni signos.
def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    without_accents = "".join(
        char for char in text if unicodedata.category(char) != "Mn"
    )
    without_punctuation = "".join(
        char if char.isalnum() or char.isspace() else " " for char in without_accents
    )
    return " ".join(without_punctuation.split())


# Busca una iniciativa por nombre, alias o similitud de escritura.
def get_initiative(query: str) -> dict[str, Any] | None:
    clean_query = normalize(query)
    initiatives = load_json("initiatives.json")

    # Primero se intenta una coincidencia exacta para los nombres bien escritos.
    for initiative in initiatives:
        if any(normalize(alias) in clean_query for alias in initiative["aliases"]):
            return initiative

    # Luego se comparan fragmentos de la pregunta para tolerar errores de escritura.
    best_match = None
    best_score = 0.0
    query_words = clean_query.split()
    for initiative in initiatives:
        for alias in initiative["aliases"]:
            clean_alias = normalize(alias)
            if len(clean_alias) < 5:
                continue

            word_count = len(clean_alias.split())
            fragments = [
                " ".join(query_words[index:index + word_count])
                for index in range(len(query_words) - word_count + 1)
            ]
            for fragment in fragments:
                score = SequenceMatcher(None, fragment, clean_alias).ratio()
                if score > best_score:
                    best_match = initiative
                    best_score = score

    # El umbral evita confundir, por ejemplo, Apple Pay con Samsung Pay.
    if best_score >= 0.75:
        return best_match
    return None


# Agrega un actor a una iniciativa y guarda el cambio sin crear duplicados.
def add_actor_to_initiative(initiative_name: str, actor_name: str) -> str:
    initiatives = load_json("initiatives.json")
    initiative = next(
        (item for item in initiatives if item["name"] == initiative_name),
        None,
    )
    if not initiative:
        return "No se encontró la iniciativa que se desea actualizar."

    actors = initiative.setdefault("actors", [])
    if any(normalize(actor) == normalize(actor_name) for actor in actors):
        return f"El actor {actor_name} ya pertenece a {initiative_name}."

    actors.append(actor_name.strip())
    with open(DATA_DIR / "initiatives.json", "w", encoding="utf-8") as file:
        json.dump(initiatives, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return f"Actor {actor_name.strip()} agregado correctamente a {initiative_name}."


def update_initiative_from_meeting(
    initiative_name: str | None, meeting_context: dict[str, Any]
) -> str:
    """Guarda los hallazgos sólo después de una orden explícita del usuario."""
    if not initiative_name or not meeting_context:
        return "No pude identificar la iniciativa o el contexto de la reunión."

    initiatives = load_json("initiatives.json")
    initiative = next(
        (item for item in initiatives if item["name"] == initiative_name), None
    )
    if not initiative:
        return "No se encontró la iniciativa que se desea actualizar."

    # Estos campos tienen correspondencia directa con la ficha de iniciativa.
    direct_fields = [
        "status", "target_date", "next_milestone", "owner", "repository",
        "branch", "environment", "priority", "description", "objective", "scope",
    ]
    updated_fields = []
    for field in direct_fields:
        value = meeting_context.get(field)
        if value not in (None, "", []):
            initiative[field] = value
            updated_fields.append(field)

    progress = meeting_context.get("progress_percentage")
    if progress not in (None, ""):
        try:
            initiative["progress_percentage"] = float(str(progress).replace("%", "").strip())
            updated_fields.append("progress_percentage")
        except ValueError:
            pass

    # Las listas se guardan con nombres claros para no mezclarlas silenciosamente
    # con información histórica proveniente de otras fuentes.
    list_mapping = {
        "agreements": "meeting_agreements",
        "pending": "meeting_pending",
        "risks": "meeting_risks",
        "technical_information": "meeting_technical_information",
        "responsibles": "meeting_responsibles",
        "actors": "meeting_actors",
        "dates": "meeting_dates",
    }
    for source_field, target_field in list_mapping.items():
        values = meeting_context.get(source_field, [])
        if values:
            initiative[target_field] = values
            updated_fields.append(target_field)

    # Los equipos mencionados se incorporan sin duplicar actores existentes.
    mentioned_actors = meeting_context.get("actors", []) + meeting_context.get("responsibles", [])
    for actor in mentioned_actors:
        if actor and not any(normalize(actor) == normalize(old) for old in initiative.get("actors", [])):
            initiative.setdefault("actors", []).append(actor)

    initiative["last_meeting_update"] = meeting_context
    with open(DATA_DIR / "initiatives.json", "w", encoding="utf-8") as file:
        json.dump(initiatives, file, ensure_ascii=False, indent=2)
        file.write("\n")
    details = ", ".join(updated_fields) if updated_fields else "last_meeting_update"
    return f"{initiative_name} fue actualizada. Campos guardados: {details}."


# Busca el procedimiento relacionado mediante palabras clave.
def get_procedure(query: str) -> dict[str, Any] | None:
    clean_query = normalize(query)
    for procedure in load_json("procedures.json"):
        if any(normalize(word) in clean_query for word in procedure["keywords"]):
            return procedure
    return None


# Obtiene los pendientes, bloqueos y próximo paso de una iniciativa.
def get_tracking(initiative_name: str) -> dict[str, Any] | None:
    return next(
        (item for item in load_json("tracking.json") if item["initiative"] == initiative_name),
        None,
    )


# Busca un Spec técnico mediante su identificador.
def get_spec(spec_id: str) -> dict[str, Any] | None:
    return next((item for item in load_json("specs.json") if item["id"] == spec_id), None)


# Busca la evidencia simulada de un repositorio y una rama.
def get_repository(repository: str, branch: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in load_json("github_mock.json")
            if item["repository"] == repository and item["branch"] == branch
        ),
        None,
    )


# Calcula el avance ponderado comparando el Spec con la evidencia técnica.
def calculate_technical_progress(spec: dict, repository: dict) -> dict[str, Any]:
    factors = {"completed": 1.0, "partial": 0.5, "pending": 0.0}
    evidence_by_id = {item["requirement_id"]: item for item in repository["evidence"]}
    total_weight = sum(item["weight"] for item in spec["requirements"])
    achieved = 0.0
    status = {"completed": [], "partial": [], "pending": []}
    details = []

    for requirement in spec["requirements"]:
        evidence = evidence_by_id.get(
            requirement["id"],
            {"requirement_id": requirement["id"], "status": "pending", "evidence": []},
        )
        requirement_status = evidence["status"]
        contribution = requirement["weight"] * factors[requirement_status]
        achieved += contribution
        status[requirement_status].append(requirement["name"])
        details.append({
            "requirement": requirement["name"],
            "weight": requirement["weight"],
            "status": requirement_status,
            "contribution": contribution,
            "evidence": evidence["evidence"],
        })

    progress = achieved / total_weight * 100 if total_weight else 0
    return {"progress": progress, "status": status, "details": details, "total_weight": total_weight}
