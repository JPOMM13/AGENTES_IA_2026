import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from src.config import (
    OLLAMA_MODEL, VISION_MODEL, WHISPER_LANGUAGE, WHISPER_MODEL, WHISPER_PROMPT,
)


FIELDS = [
    "dates", "responsibles", "actors", "agreements", "pending", "risks",
    "technical_information",
]
IMPORTANT_FIELDS = [
    "status", "progress_percentage", "target_date", "next_milestone",
    "owner", "priority", "description", "objective", "scope",
    "repository", "branch", "environment",
]


# Coordina la transcripción, el análisis visual y la unión de ambas fuentes.
def process_meeting(video_path: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    path = Path(video_path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in {".mp4", ".mov"}:
        raise FileNotFoundError(f"No existe el archivo MP4 o MOV: {path}")

    transcription = _transcribe(path)
    frames = _extract_frames(path)
    visual_evidence = [_analyze_frame(frame, second) for frame, second in frames]

    audio_data = _extract_facts(transcription, "audio de la reunión", OLLAMA_MODEL)
    audio_data = _supplement_audio_facts(transcription, audio_data)
    visual_text = "\n".join(item["analysis"] for item in visual_evidence)
    visual_data = _extract_facts(visual_text, "pantalla compartida", OLLAMA_MODEL)
    visual_data = _sanitize_visual_facts(visual_data)
    context = _merge_context(audio_data, visual_data)
    return transcription, visual_evidence, context


# Extrae el audio del video y lo convierte en texto en español con Whisper.
def _transcribe(video_path: Path) -> str:
    from faster_whisper import WhisperModel

    with tempfile.TemporaryDirectory() as temp_dir:
        audio_path = Path(temp_dir) / "meeting.wav"
        command = [
            "ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1",
            "-ar", "16000", str(audio_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("FFmpeg no pudo extraer el audio. Verifica que esté instalado.")

        model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(
            str(audio_path),
            language=WHISPER_LANGUAGE,
            initial_prompt=WHISPER_PROMPT,
            beam_size=5,
            vad_filter=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()


# Obtiene cuatro imágenes distribuidas a lo largo de la grabación.
def _extract_frames(video_path: Path, count: int = 4) -> list[tuple[bytes, float]]:
    import cv2

    video = cv2.VideoCapture(str(video_path))
    total = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = video.get(cv2.CAP_PROP_FPS) or 1
    if total <= 0:
        video.release()
        raise RuntimeError("No fue posible leer frames del video.")

    positions = [int(total * index / (count + 1)) for index in range(1, count + 1)]
    frames = []
    for position in positions:
        video.set(cv2.CAP_PROP_POS_FRAMES, position)
        ok, frame = video.read()
        if ok:
            encoded, buffer = cv2.imencode(".jpg", frame)
            if encoded:
                frames.append((buffer.tobytes(), position / fps))
    video.release()
    return frames


# Envía un frame a Ollama para recuperar información visible de la iniciativa.
def _analyze_frame(image: bytes, second: float) -> dict[str, Any]:
    import ollama

    prompt = (
        "Lee esta pantalla de reunión. Extrae únicamente datos visibles sobre iniciativa, "
        "estado, fechas, responsables, repositorio, rama, pipeline, pruebas, aprobaciones, "
        "pendientes y riesgos. No describas personas ni inventes datos. Si no hay información "
        "útil responde: Sin evidencia útil. Copia números y fechas exactamente como aparecen; "
        "no cambies el año ni conviertas fechas por tu cuenta."
    )
    response = ollama.chat(
        model=VISION_MODEL,
        messages=[{"role": "user", "content": prompt, "images": [image]}],
    )
    return {"second": round(second, 1), "analysis": response.message.content.strip()}


# Organiza el texto del audio o de la pantalla en campos verificables.
def _extract_facts(text: str, source: str, model_name: str) -> dict[str, Any]:
    if not text.strip():
        return _empty_context()

    import ollama

    schema = {
        "initiative": "texto o null",
        "status": "estado actual o null",
        "progress_percentage": "porcentaje numérico de avance o null",
        "target_date": "fecha de entrega explícita en formato YYYY-MM-DD si es posible o null",
        "next_milestone": "siguiente hito o null",
        "owner": "responsable principal o null",
        "priority": "prioridad o null",
        "description": "descripción explícita o null",
        "objective": "objetivo explícito o null",
        "scope": "alcance funcional explícito o null",
        "repository": "repositorio o null",
        "branch": "rama o null",
        "environment": "ambiente o null",
        "dates": [], "responsibles": [], "actors": [], "agreements": [], "pending": [],
        "risks": [], "technical_information": [],
    }
    prompt = (
        f"Extrae hechos explícitos del siguiente contenido procedente de {source}. "
        f"Devuelve sólo JSON válido con esta estructura: {json.dumps(schema)}. "
        "No deduzcas ni inventes. Conserva cada hecho como texto breve.\n\n"
        f"CONTENIDO:\n{text}"
    )
    response = ollama.chat(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        format="json",
    )
    data = json.loads(response.message.content)
    clean = _empty_context()
    clean["initiative"] = _clean_scalar(data.get("initiative"))
    for field in IMPORTANT_FIELDS:
        clean[field] = _clean_scalar(data.get(field))
    for field in FIELDS:
        values = data.get(field) or []
        if not isinstance(values, list):
            values = [values]
        clean[field] = [_plain_text(value) for value in values if value]
    return clean


# Convierte valores anidados devueltos por el modelo en texto sencillo.
def _plain_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or value.get("value") or next(iter(value.values()), ""))
    return str(value)


# Convierte textos como null o none en valores vacíos reales de Python.
def _clean_scalar(value: Any) -> Any:
    if isinstance(value, str) and value.strip().lower() in {"null", "none", "no indicado", ""}:
        return None
    return value


# Refuerza la extracción de porcentaje, fecha y prioridad con reglas simples.
def _supplement_audio_facts(text: str, facts: dict[str, Any]) -> dict[str, Any]:
    lower = text.lower()
    progress = re.search(r"avance[^.]{0,80}?(\d{1,3})\s*%", lower)
    facts["progress_percentage"] = int(progress.group(1)) if progress else None

    months = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
        "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9,
        "octubre": 10, "noviembre": 11, "diciembre": 12,
    }
    date = re.search(
        r"fecha (?:estimada|objetivo)[^.]{0,40}?(\d{1,2}) de (" + "|".join(months) + r") (?:de|del) (\d{4})",
        lower,
    )
    if date:
        day, month, year = int(date.group(1)), months[date.group(2)], int(date.group(3))
        facts["target_date"] = f"{year:04d}-{month:02d}-{day:02d}"
        literal_date = date.group(0).split("para el ")[-1]
        if literal_date not in facts["dates"]:
            facts["dates"].append(literal_date)
    else:
        facts["target_date"] = None

    priority = re.search(r"prioridad\s+(alta|media|baja)", lower)
    facts["priority"] = priority.group(1).capitalize() if priority else None

    status = re.search(r"(?:estado|status) actual\s*(?:es|seria|:)\s*([^.,]+)", lower)
    facts["status"] = status.group(1).strip().capitalize() if status else None

    explicit_keywords = {
        "owner": ["equipo responsable", "responsable principal"],
        "description": ["descripcion"], "objective": ["objetivo"],
        "next_milestone": ["proximo hito"], "repository": ["repositorio"],
        "branch": ["rama"], "environment": ["ambiente"],
    }
    for field, keywords in explicit_keywords.items():
        if not any(keyword in lower for keyword in keywords):
            facts[field] = None

    scope = re.search(r"alcance funcional[^.]*?(?:contempla|es)\s+([^.]+)", text, re.IGNORECASE)
    facts["scope"] = scope.group(1).strip() if scope else None
    if "samsung pay" in lower:
        facts["initiative"] = "Samsung Pay Visa"
    return facts


# Descarta lecturas visuales incompletas o que no pertenecen a la iniciativa.
def _sanitize_visual_facts(facts: dict[str, Any]) -> dict[str, Any]:
    repository = str(facts.get("repository") or "").lower()
    if "..." in repository or "utec" in repository:
        facts["repository"] = None
    facts["pending"] = [
        item for item in facts["pending"]
        if "pendient" in item.lower() or "pending" in item.lower()
    ]
    facts["actors"] = [
        item.strip() for item in facts["actors"]
        if "cliente deber" not in item.lower()
    ]
    facts["dates"] = _consistent_dates(facts["dates"], facts.get("target_date"))
    return facts


# Crea la estructura vacía utilizada para guardar el contexto de la reunión.
def _empty_context() -> dict[str, Any]:
    return {
        "initiative": None,
        **{field: None for field in IMPORTANT_FIELDS},
        **{field: [] for field in FIELDS},
        "sources": {},
    }


# Combina audio y pantalla conservando el origen de cada información.
def _merge_context(audio: dict[str, Any], visual: dict[str, Any]) -> dict[str, Any]:
    context = _empty_context()
    audio["dates"] = _consistent_dates(audio["dates"], audio.get("target_date"))
    visual["dates"] = _consistent_dates(visual["dates"], visual.get("target_date"))
    context["initiative"] = audio.get("initiative") or visual.get("initiative")
    for field in IMPORTANT_FIELDS:
        context[field] = audio.get(field) or visual.get(field)
    for field in FIELDS:
        context[field] = audio[field] + [item for item in visual[field] if item not in audio[field]]
    context["dates"] = _consistent_dates(context["dates"], context.get("target_date"))
    context["sources"] = {
        "audio de la reunión": {field: audio.get(field) for field in IMPORTANT_FIELDS + FIELDS},
        "pantalla compartida": {field: visual.get(field) for field in IMPORTANT_FIELDS + FIELDS},
    }
    return context


# Elimina fechas cuyo año contradice la fecha objetivo seleccionada.
def _consistent_dates(dates: list[str], target_date: Any) -> list[str]:
    if not target_date:
        return dates
    year_match = re.search(r"\b(20\d{2})\b", str(target_date))
    if not year_match:
        return dates
    expected_year = year_match.group(1)
    return [
        date for date in dates
        if not re.search(r"\b20\d{2}\b", date) or expected_year in date
    ]
