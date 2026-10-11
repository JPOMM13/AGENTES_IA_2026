import os
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()

# Debe ser el mismo modelo con el que se ingestaron los chunks
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
RAG_THRESHOLD = float(os.getenv("RAG_THRESHOLD", "0.40"))

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text: str, model: str):
    result = openai_client.embeddings.create(
        model=model,
        input=text
    )
    return result.data[0].embedding

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def retrieve_chunks(
    query: str,
    top_k: int = 5,
    threshold: float = RAG_THRESHOLD,
    filtro_servicio: str = None,
    filtro_tipo: str = None
):
    """
    1) Genera embedding de la pregunta
    2) Consulta Supabase vía RPC (rag.match_chunks)
    3) Devuelve los chunks más similares
    """

    query_vector = get_embedding(query, model=EMBEDDING_MODEL)

    response = supabase.schema("rag").rpc(
        "match_chunks",
        {
            "query_embedding": query_vector,
            "similarity_threshold": threshold,
            "match_count": top_k,
            "filtro_servicio": filtro_servicio,
            "filtro_tipo": filtro_tipo
        }
    ).execute()

    return response.data or []
