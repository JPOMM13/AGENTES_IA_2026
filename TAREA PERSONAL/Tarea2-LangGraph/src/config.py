from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
