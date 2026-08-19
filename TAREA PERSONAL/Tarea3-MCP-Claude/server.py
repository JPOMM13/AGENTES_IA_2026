from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from fastmcp import FastMCP


# PRINCIPIOS ÉTICOS DEL PROTOTIPO:
# - Utiliza únicamente datos ficticios con fines académicos.
# - No debe almacenar credenciales ni información bancaria confidencial.
# - Las respuestas generadas por IA deben ser revisadas por una persona.
# - No debe ejecutar decisiones sensibles o pases a producción automáticamente.
# - Todo uso empresarial requiere autorización, trazabilidad y control de acceso.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INICIATIVAS_FILE = DATA_DIR / "iniciativas.json"
PROCEDIMIENTOS_FILE = DATA_DIR / "procedimientos.json"
PROJECT_CONTEXT_FILE = BASE_DIR / "project_context.md"

mcp = FastMCP(
    "MCP Personal - Iniciativas y Procedimientos"
)


# Lee y devuelve los registros de un archivo JSON.
def _leer_json(ruta: Path) -> list[dict[str, Any]]:
    with ruta.open("r", encoding="utf-8") as archivo:
        return json.load(archivo)


# Guarda los registros en un archivo JSON con formato legible.
def _guardar_json(ruta: Path, contenido: list[dict[str, Any]]) -> None:
    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)


# Normaliza un texto para compararlo sin espacios ni mayúsculas.
def _normalizar(texto: str) -> str:
    return texto.strip().lower()


# Busca una iniciativa por su ID o por una parte de su nombre.
def _buscar_iniciativa(termino: str) -> dict[str, Any] | None:
    termino_normalizado = _normalizar(termino)

    for iniciativa in _leer_json(INICIATIVAS_FILE):
        if (
            termino_normalizado == _normalizar(iniciativa["id"])
            or termino_normalizado in _normalizar(iniciativa["nombre"])
            or _normalizar(iniciativa["nombre"]) in termino_normalizado
        ):
            return iniciativa

    return None


# Lista todas las iniciativas registradas en el archivo local.
@mcp.tool
def listar_iniciativas() -> list[dict[str, Any]]:
    return _leer_json(INICIATIVAS_FILE)


# Consulta el detalle de una iniciativa mediante su nombre o ID.
@mcp.tool
def consultar_iniciativa(nombre_o_id: str) -> dict[str, Any]:
    iniciativa = _buscar_iniciativa(nombre_o_id)

    if iniciativa is None:
        return {
            "encontrada": False,
            "mensaje": f"No se encontró la iniciativa: {nombre_o_id}",
        }

    return {
        "encontrada": True,
        **iniciativa,
    }


# Actualiza datos simulados; en producción requeriría autorización y auditoría.
@mcp.tool
def registrar_avance(
    nombre_o_id: str,
    avance: int,
    estado: str | None = None,
    proximo_paso: str | None = None,
    comentario: str | None = None,
) -> dict[str, Any]:
    if avance < 0 or avance > 100:
        return {
            "actualizada": False,
            "mensaje": "El avance debe estar entre 0 y 100.",
        }

    iniciativas = _leer_json(INICIATIVAS_FILE)
    termino = _normalizar(nombre_o_id)

    for iniciativa in iniciativas:
        coincide = (
            termino == _normalizar(iniciativa["id"])
            or termino in _normalizar(iniciativa["nombre"])
            or _normalizar(iniciativa["nombre"]) in termino
        )

        if not coincide:
            continue

        iniciativa["avance"] = avance
        iniciativa["ultima_actualizacion"] = date.today().isoformat()

        if estado:
            iniciativa["estado"] = estado.strip()

        if proximo_paso:
            iniciativa["proximo_paso"] = proximo_paso.strip()

        if comentario:
            iniciativa["ultima_observacion"] = comentario.strip()

        _guardar_json(INICIATIVAS_FILE, iniciativas)

        return {
            "actualizada": True,
            "mensaje": "Iniciativa actualizada correctamente.",
            "iniciativa": iniciativa,
        }

    return {
        "actualizada": False,
        "mensaje": f"No se encontró la iniciativa: {nombre_o_id}",
    }


# Consulta procedimientos de referencia que deben validarse antes de ejecutarse.
@mcp.tool
def consultar_procedimiento(nombre_o_id: str) -> dict[str, Any]:
    termino = _normalizar(nombre_o_id)

    for procedimiento in _leer_json(PROCEDIMIENTOS_FILE):
        if (
            termino == _normalizar(procedimiento["id"])
            or termino in _normalizar(procedimiento["nombre"])
            or _normalizar(procedimiento["nombre"]) in termino
        ):
            return {
                "encontrado": True,
                **procedimiento,
            }

    return {
        "encontrado": False,
        "mensaje": f"No se encontró el procedimiento: {nombre_o_id}",
    }


# Genera un resumen compacto para la revisión diaria de iniciativas.
@mcp.tool
def resumen_diario() -> dict[str, Any]:
    iniciativas = _leer_json(INICIATIVAS_FILE)

    resumen = []
    for iniciativa in iniciativas:
        resumen.append(
            {
                "id": iniciativa["id"],
                "nombre": iniciativa["nombre"],
                "estado": iniciativa["estado"],
                "ambiente": iniciativa["ambiente"],
                "avance": iniciativa["avance"],
                "proximo_paso": iniciativa["proximo_paso"],
                "bloqueos": iniciativa.get("bloqueos", []),
            }
        )

    return {
        "total_iniciativas": len(resumen),
        "iniciativas": resumen,
    }


# Expone como recurso MCP el contenido actual de las iniciativas.
@mcp.resource("iniciativas://actual")
def iniciativas_actuales() -> str:
    iniciativas = _leer_json(INICIATIVAS_FILE)
    return json.dumps(iniciativas, ensure_ascii=False, indent=2)


# Expone como recurso MCP la definición y el alcance del proyecto.
@mcp.resource("context://project")
def contexto_proyecto() -> str:
    return PROJECT_CONTEXT_FILE.read_text(encoding="utf-8")


# Genera una guía para Claude sin permitirle inventar información no disponible.
@mcp.prompt
def resumen_iniciativas() -> str:
    return """
Analiza las iniciativas disponibles mediante el MCP.

Para cada iniciativa:
1. Indica su estado actual y ambiente.
2. Resume su porcentaje de avance.
3. Señala el próximo paso.
4. Identifica bloqueos explícitos.
5. Sugiere una prioridad de atención: Alta, Media o Baja, explicando brevemente por qué.

No inventes datos que no estén disponibles en el MCP.

Al final genera un resumen ejecutivo breve con:
- iniciativas que requieren atención inmediata,
- próximos hitos,
- bloqueos que deben resolverse.
""".strip()

# Inicia el servidor MCP usando STDIO al ejecutar este archivo.
if __name__ == "__main__":
    mcp.run()
