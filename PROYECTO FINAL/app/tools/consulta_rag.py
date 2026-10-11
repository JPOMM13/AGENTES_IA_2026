from __future__ import annotations

import os

from app.data.datos_mock import MOCK_KNOWLEDGE

RAG_CHAT_MODEL = "gpt-4o-mini"


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


# TOOL RAG: consulta el RAG real en Supabase y responde solo con el contexto recuperado.
def buscar_rag(query: str) -> str:
    """Consulta el RAG real en Supabase y responde usando solo el contexto recuperado."""
    # Imports diferidos: retriever.py se conecta a Supabase al importarse.
    from openai import OpenAI
    from app.tools.retriever import retrieve_chunks

    chunks = retrieve_chunks(query, top_k=6)
    if not chunks:
        return "No encontré información relevante en la base de conocimiento."

    context = "\n\n---\n\n".join(chunk["texto"] for chunk in chunks)
    messages = [
        {
            "role": "system",
            "content": (
                "Responde únicamente usando el contexto proporcionado. "
                "Si no encuentras la respuesta en el contexto, indícalo claramente."
            ),
        },
        {"role": "user", "content": f"CONTEXTO:\n{context}\n\nPREGUNTA:\n{query}"},
    ]

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=RAG_CHAT_MODEL,
        messages=messages,
        temperature=0.2,
    )
    return response.choices[0].message.content
