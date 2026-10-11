from __future__ import annotations

from app.data.datos_mock import MOCK_KNOWLEDGE


# TOOL MOCK/RAG: busca politicas o contexto de negocio en una base de conocimiento simulada.
def mock_buscar_rag(query: str) -> dict:
    """Busca respuestas de politicas en la base de conocimiento mock."""
    # MOCK: ESTA TOOL DEBERIA CONSULTAR EL RAG REAL CON DOCUMENTOS EN STORAGE, EMBEDDINGS EN PGVECTOR/POSTGRESQL Y RETRIEVER SEMANTICO.
    texto = query.lower()
    matches = []
    for document in MOCK_KNOWLEDGE:
        if any(keyword in texto for keyword in document["keywords"]):
            matches.append(document)
    return {"matches": matches[:3]}
