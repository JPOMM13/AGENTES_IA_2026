"""Configuración centralizada; no construye clientes al importar."""
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = "gpt-5.6-terra"

@dataclass(frozen=True)
class Settings:
    model: str
    judge_model: str
    data_path: Path
    reference_datetime: datetime

    # Carga el .env de la raíz, valida la fuente y el reloj, y devuelve la configuración compartida.
    @classmethod
    def load(cls):
        # Usa el archivo junto a app.py; las variables ya exportadas en la terminal tienen prioridad.
        load_dotenv(ROOT / ".env", override=False)
        if os.getenv("DATA_SOURCE", "json") != "json":
            raise ValueError("DATA_SOURCE debe ser json en esta versión.")
        model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        now = datetime.fromisoformat(os.getenv("EVAL_REFERENCE_DATETIME", "2026-09-06T20:00:00-05:00"))
        if now.tzinfo is None:
            raise ValueError("EVAL_REFERENCE_DATETIME requiere zona horaria.")
        return cls(model, os.getenv("OPENAI_JUDGE_MODEL", model),
                   ROOT / os.getenv("MOCK_DATA_PATH", "data/mock_data_eventos.json"), now)


# Comprueba que exista una clave configurada; informa su nombre si falta, sin mostrar su valor.
def require_key(name):
    value = os.getenv(name, "")
    if not value or value.startswith("PEGAR_"):
        raise ValueError(f"Falta {name}. Configura el archivo .env en la raíz del proyecto.")
