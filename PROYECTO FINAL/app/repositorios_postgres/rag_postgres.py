from __future__ import annotations

from app.repositorios_postgres.conexion import conexion_postgres


# POSTGRES/RAG MOCK: busca documentos de politica por keywords guardadas en PostgreSQL.
def buscar_rag_postgres(query: str) -> dict:
    """Replica el RAG mock buscando palabras clave en jpomm_rag_documentos."""
    texto = query.lower()
    with conexion_postgres() as conexion:
        documentos = conexion.execute(
            """
            SELECT id, titulo, texto, palabras_clave
            FROM jpomm_rag_documentos
            WHERE activo = true
            ORDER BY id
            """
        ).fetchall()
    matches = []
    for document in documentos:
        keywords = list(document["palabras_clave"] or [])
        if any(keyword in texto for keyword in keywords):
            matches.append(
                {
                    "id": document["id"],
                    "title": document["titulo"],
                    "texto": document["texto"],
                    "keywords": keywords,
                }
            )
    return {"matches": matches[:3]}
