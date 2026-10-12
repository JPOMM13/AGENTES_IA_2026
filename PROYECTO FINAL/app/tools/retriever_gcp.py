import os
import sys
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from openai import OpenAI
from psycopg.conninfo import conninfo_to_dict, make_conninfo

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Carpeta con datos.py, el .env y los certificados de la base de GCP
GCP_DIR = PROJECT_ROOT / "entrega-john"

# Debe ser el mismo modelo con el que se ingestaron los chunks
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
RAG_THRESHOLD = float(os.getenv("RAG_THRESHOLD", "0.40"))

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def preparar_database_url():
    """
    datos.py se conecta con DATABASE_URL, cuyas rutas de certificados (certs/...)
    son relativas a la carpeta desde donde se ejecuta. Las convierte en absolutas
    (respecto a entrega-john/) y deja la URL lista en el entorno antes de usar datos.py.
    El load_dotenv() de datos.py no sobrescribe una variable que ya existe.
    """
    url = dotenv_values(GCP_DIR / ".env").get("DATABASE_URL")
    if not url:
        raise RuntimeError(f"Falta DATABASE_URL en {GCP_DIR / '.env'}")

    params = conninfo_to_dict(url)
    for clave in ("sslrootcert", "sslcert", "sslkey"):
        if not Path(params[clave]).is_absolute():
            params[clave] = str(GCP_DIR / params[clave])
    params.setdefault("connect_timeout", "10")
    # make_conninfo pone comillas: el espacio de "PROYECTO FINAL" no rompe la conexion
    os.environ["DATABASE_URL"] = make_conninfo(**params)


preparar_database_url()

# entrega-john tiene guion: no es un paquete, se importa agregando la carpeta al path
if str(GCP_DIR) not in sys.path:
    sys.path.insert(0, str(GCP_DIR))
import datos  # noqa: E402  (debe importarse despues de preparar DATABASE_URL)


def get_embedding(text: str, model: str):
    result = openai_client.embeddings.create(
        model=model,
        input=text
    )
    return result.data[0].embedding


# CIERRE DE RECURSOS: expone el cierre del pool GCP sin acoplar scripts a entrega-john/datos.py.
def cerrar_pool_rag() -> None:
    """Cierra el pool de conexiones usado por el retriever GCP."""
    cerrar = getattr(datos, "cerrar_pool", None)
    if cerrar:
        cerrar()

def retrieve_chunks(
    query: str,
    top_k: int = 5,
    threshold: float = RAG_THRESHOLD,
    filtro_servicio: str = None,
    filtro_tipo: str = None
):
    """
    1) Genera embedding de la pregunta
    2) Consulta GCP con datos.buscar_conocimiento (rag.fn_buscar; filtra por servicio
       e incluye siempre 'general'). Reutiliza el pool de conexiones de datos.py.
    3) Devuelve los chunks más similares que superan el umbral

    rag.fn_buscar devuelve distancia coseno; similitud = 1 - distancia.
    No soporta filtro por tipo de contenido.
    """
    if filtro_tipo is not None:
        raise ValueError("rag.fn_buscar en GCP no soporta filtro_tipo")

    query_vector = get_embedding(query, model=EMBEDDING_MODEL)

    filas = datos.buscar_conocimiento(
        query_vector,
        servicio=filtro_servicio or "general",
        top_k=top_k
    )

    return [
        {**fila, "similarity": 1 - fila["distancia"]}
        for fila in filas
        if 1 - fila["distancia"] > threshold
    ]
