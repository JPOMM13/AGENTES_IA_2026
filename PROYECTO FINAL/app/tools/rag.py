from __future__ import annotations

from app.data.mock_data import MOCK_KNOWLEDGE


# Ejecuta la responsabilidad de mock buscar rag.
def mock_buscar_rag(query: str) -> dict:
    """Busca respuestas de politicas en la base de conocimiento mock."""
    # MOCK: ESTA TOOL DEBERIA CONSULTAR EL RAG REAL CON DOCUMENTOS EN STORAGE, EMBEDDINGS EN PGVECTOR/POSTGRESQL Y RETRIEVER SEMANTICO.
    text = query.lower()
    matches = []
    for document in MOCK_KNOWLEDGE:
        if any(keyword in text for keyword in document["keywords"]):
            matches.append(document)
    return {"matches": matches[:3]}
