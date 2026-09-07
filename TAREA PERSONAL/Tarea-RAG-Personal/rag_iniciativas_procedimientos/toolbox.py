"""Herramienta RAG expuesta al agente."""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from vector import KnowledgeBase


class ConsultaConocimiento(BaseModel):
    query: str = Field(description="Pregunta concreta sobre una iniciativa o procedimiento")


# Crea la herramienta que el agente utiliza para consultar la base vectorial local.
def create_rag_tool(knowledge_base: KnowledgeBase) -> StructuredTool:
    # Recupera los chunks mas relevantes y los presenta con el PDF y pagina de origen.
    def buscar_conocimiento_iniciativas(query: str) -> str:
        documents = knowledge_base.retriever.invoke(query)
        if not documents:
            return "No se encontro informacion relevante en los PDF disponibles."

        results = []
        for document in documents:
            source = document.metadata.get("source", "fuente desconocida")
            # PyPDFLoader almacena paginas desde cero; se muestran desde uno al usuario.
            page = int(document.metadata.get("page", 0)) + 1
            results.append(
                f"Fuente: {source} - pagina {page}\n"
                f"Contenido: {document.page_content.strip()}"
            )
        return "\n\n".join(results)

    return StructuredTool.from_function(
        func=buscar_conocimiento_iniciativas,
        name="buscar_conocimiento_iniciativas",
        description=(
            "Busca informacion verificable en los PDF locales de iniciativas tecnologicas "
            "y procedimientos operativos. Debe usarse antes de responder esas consultas."
        ),
        args_schema=ConsultaConocimiento,
    )
