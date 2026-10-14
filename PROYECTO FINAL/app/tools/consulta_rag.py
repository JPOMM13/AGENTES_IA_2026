from __future__ import annotations

import logging
import os
import unicodedata

from app.data.datos_mock import MOCK_KNOWLEDGE
from app.fuente_datos import usar_postgres_negocio
from app.repositorios_postgres.rag_postgres import buscar_rag_postgres

RAG_CHAT_MODEL = "gpt-4o-mini"
logger = logging.getLogger("cotizador.rag")

SIN_RESULTADOS = (
    "No encontre esa informacion en nuestras politicas. Si quieres, te derivo con un asesor para confirmarlo; "
    "mientras tanto podemos seguir con la cotizacion."
)
SIN_SERVICIO = (
    "Ahora mismo no puedo consultar la base de conocimiento. Un asesor puede confirmartelo; "
    "mientras tanto podemos seguir con la cotizacion."
)


# RAG DE RESPALDO: busqueda por palabras clave en las politicas locales (mock o tabla jpomm_rag_documentos).
# Se usa solo cuando el RAG real (embeddings + pgvector en GCP) no responde: nunca dejamos la pregunta sin contestar.
def buscar_rag_local(query: str) -> dict:
    """Busca respuestas de politicas en la base de conocimiento local por palabras clave."""
    if usar_postgres_negocio():
        return buscar_rag_postgres(query)

    texto = _sin_tildes(query.lower())  # "anticipación" debe encontrar la keyword "anticipacion"
    matches = [document for document in MOCK_KNOWLEDGE if any(_sin_tildes(keyword) in texto for keyword in document["keywords"])]
    return {"matches": matches[:3]}


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _renderizar_respaldo_local(query: str) -> str:
    resultado = buscar_rag_local(query)
    if not resultado.get("matches"):
        return SIN_SERVICIO
    lines = [f"- **{doc['title']}**: {doc['texto']}" for doc in resultado["matches"]]
    return "Segun nuestras politicas:\n\n" + "\n".join(lines)


# TOOL RAG: recupera chunks del documento de politicas (pgvector en GCP) y responde solo con ese contexto.
def buscar_rag(query: str) -> str:
    """Consulta el RAG real (GCP) y responde usando solo el contexto recuperado; degrada al respaldo local."""
    try:
        # Imports diferidos: el retriever abre el pool a la base al importarse.
        from openai import OpenAI
        from app.tools.retriever_gcp import retrieve_chunks  # GCP (antes: app.tools.retriever para Supabase)

        chunks = retrieve_chunks(query, top_k=6)
    except Exception as exc:  # noqa: BLE001 - base caida, certs, red: el turno no debe romperse.
        logger.warning("rag_real_no_disponible error=%s", str(exc)[:200])
        return _renderizar_respaldo_local(query)

    if not chunks:
        return SIN_RESULTADOS

    context = "\n\n---\n\n".join(chunk["texto"] for chunk in chunks)
    messages = [
        {
            "role": "system",
            "content": (
                "Eres el asistente de un servicio de eventos. Responde en espanol, breve y amable, "
                "unicamente con el contexto proporcionado. Si el contexto no responde la pregunta, dilo claramente "
                "y sugiere confirmar con un asesor. No inventes precios, zonas ni disponibilidad."
            ),
        },
        {"role": "user", "content": f"CONTEXTO:\n{context}\n\nPREGUNTA:\n{query}"},
    ]
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(model=RAG_CHAT_MODEL, messages=messages, temperature=0.2, timeout=20)
        return response.choices[0].message.content or SIN_RESULTADOS
    except Exception as exc:  # noqa: BLE001 - si el modelo falla, al menos devolvemos el fragmento recuperado.
        logger.warning("rag_llm_no_disponible error=%s", str(exc)[:200])
        return "Lo que dicen nuestras politicas:\n\n" + chunks[0]["texto"][:600]
