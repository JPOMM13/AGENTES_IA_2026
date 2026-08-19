import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

for archivo in [
    BASE_DIR / "data" / "iniciativas.json",
    BASE_DIR / "data" / "procedimientos.json",
]:
    with archivo.open("r", encoding="utf-8") as f:
        contenido = json.load(f)

    assert isinstance(contenido, list)
    assert len(contenido) > 0
    print(f"OK JSON: {archivo.name} -> {len(contenido)} registros")

print("OK: archivos JSON válidos.")

