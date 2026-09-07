import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
VISION_MODEL = os.getenv("VISION_MODEL", "gemma4:latest")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "es")
WHISPER_PROMPT = os.getenv(
    "WHISPER_PROMPT",
    "Samsung Pay Visa, UAT, Thales, tokenización, enrolamiento, Monitor, Latina, SendOTP.",
)
