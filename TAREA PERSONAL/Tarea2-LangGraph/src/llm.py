from typing import Literal

from pydantic import BaseModel, Field

from src.config import OLLAMA_MODEL, USE_LLM
from src.tools import load_json


# Define la respuesta estructurada que debe devolver el LLM.
class QueryAnalysis(BaseModel):
    intent: Literal[
        "iniciativa",
        "procedimiento",
        "seguimiento",
        "estado_tecnico",
        "consulta_compuesta",
        "actualizar_actor",
    ] = Field(description="Intención principal de la pregunta")
    initiative_name: str | None = Field(
        description="Nombre exacto de la iniciativa o null si no se menciona"
    )
    actor_name: str | None = Field(
        description="Nombre del actor que se desea agregar o null si no corresponde"
    )


# Interpreta la consulta con Ollama y devuelve None si el LLM falla o está apagado.
def analyze_with_llm(question: str) -> QueryAnalysis | None:
    if not USE_LLM:
        return None

    try:
        # La importación es local para que USE_LLM=false no dependa de Ollama.
        from langchain_ollama import ChatOllama

        initiatives = [item["name"] for item in load_json("initiatives.json")]
        model = ChatOllama(model=OLLAMA_MODEL, temperature=0)
        structured_model = model.with_structured_output(QueryAnalysis)
        return structured_model.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "Clasifica la consulta de un asistente de iniciativas. "
                        "Las intenciones válidas son: iniciativa, procedimiento, "
                        "seguimiento, estado_tecnico, consulta_compuesta y actualizar_actor. "
                        "Usa actualizar_actor solamente si se pide agregar un actor "
                        "o participante a una iniciativa. Extrae su nombre en actor_name. "
                        "Usa consulta_compuesta cuando se soliciten varias capacidades. "
                        "Corrige errores de escritura en el nombre, pero selecciona "
                        "solamente una iniciativa de esta lista: "
                        f"{initiatives}. Si ninguna corresponde, devuelve null. "
                        "No respondas la pregunta ni inventes datos."
                    ),
                },
                {"role": "user", "content": question},
            ]
        )
    except Exception as error:
        # El error se informa en consola, pero el workflow no se detiene.
        print(f"[LLM no disponible: {error}. Se usarán reglas determinísticas]")
        return None
