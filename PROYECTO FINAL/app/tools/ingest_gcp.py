# Ingesta del RAG en la base PostgreSQL de GCP (Cloud SQL + pgvector).
# Misma logica que ingest_supabase.py, pero escribiendo en rag.documents / rag.chunks de GCP.
# Uso, desde la carpeta PROYECTO FINAL:
#   python app/tools/ingest_gcp.py            -> solo valida la conexion (lectura)
#   python app/tools/ingest_gcp.py --ingestar -> carga el PDF en GCP

import argparse
import os
from pathlib import Path

import pdfplumber
import psycopg
from dotenv import dotenv_values, load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Carpeta con el .env y los certificados de la base de GCP
GCP_DIR = PROJECT_ROOT / "entrega-john"
CONNECT_TIMEOUT = 10

# OPENAI_API_KEY y EMBEDDING_MODEL vienen del .env del proyecto
load_dotenv(PROJECT_ROOT / ".env")

# Modelo de embeddings: debe ser el mismo que use el retriever al buscar
# y su dimension debe coincidir con vector(1536) de rag.chunks en GCP
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = 1536


def get_gcp_config() -> dict:
    """Lee las credenciales de entrega-john/.env sin mezclarlas con el .env del proyecto."""
    env_path = GCP_DIR / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f"No existe {env_path}")
    config = dotenv_values(env_path)

    faltantes = [k for k in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD") if not config.get(k)]
    if faltantes:
        raise ValueError(f"Faltan variables en {env_path}: {', '.join(faltantes)}")
    return config


def resolver_cert(ruta: str) -> str:
    """Convierte la ruta relativa del certificado en absoluta, desde la carpeta de GCP."""
    path = Path(ruta)
    if not path.is_absolute():
        path = GCP_DIR / path
    if not path.exists():
        raise FileNotFoundError(f"No existe el certificado {path}")
    return str(path)


def get_connection() -> psycopg.Connection:
    """
    Conecta con parametros separados (no con DATABASE_URL), porque la ruta
    del proyecto tiene espacios y la URL fallaria con 'missing "=" after ...'.
    """
    config = get_gcp_config()
    return psycopg.connect(
        host=config["DB_HOST"],
        port=int(config["DB_PORT"]),
        dbname=config["DB_NAME"],
        user=config["DB_USER"],
        password=config["DB_PASSWORD"],
        sslmode=config.get("DB_SSLMODE") or "verify-ca",
        sslrootcert=resolver_cert(config["DB_SSLROOTCERT"]),
        sslcert=resolver_cert(config["DB_SSLCERT"]),
        sslkey=resolver_cert(config["DB_SSLKEY"]),
        connect_timeout=CONNECT_TIMEOUT,
    )


def probar_conexion():
    """Valida la conexion y muestra lo necesario para la ingesta. Solo lectura."""
    config = get_gcp_config()
    print(f"Conectando a {config['DB_HOST']}:{config['DB_PORT']}/{config['DB_NAME']} como {config['DB_USER']} ...")

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT current_user, version()")
        usuario, version = cur.fetchone()
        print(f"\n1) Conectado como: {usuario}")
        print(f"   {version.split(',')[0]}")

        cur.execute(
            """SELECT table_schema, count(*)
                 FROM information_schema.tables
                WHERE table_schema IN ('core', 'rag', 'memory')
                GROUP BY table_schema ORDER BY table_schema"""
        )
        print("\n2) Tablas por esquema:")
        for esquema, total in cur.fetchall():
            print(f"   {esquema}: {total}")

        print("\n3) Filas en rag:")
        for tabla in ("documents", "chunks"):
            cur.execute(f"SELECT count(*) FROM rag.{tabla}")
            print(f"   rag.{tabla}: {cur.fetchone()[0]}")

        cur.execute(
            """SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull
                 FROM pg_attribute a
                WHERE a.attrelid = 'rag.chunks'::regclass AND a.attnum > 0 AND NOT a.attisdropped
                ORDER BY a.attnum"""
        )
        print("\n4) Columnas de rag.chunks:")
        for nombre, tipo, not_null in cur.fetchall():
            print(f"   {nombre:<16} {tipo}{'  NOT NULL' if not_null else ''}")

        cur.execute(
            """SELECT p.oid::regprocedure, pg_get_function_result(p.oid)
                 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'rag'"""
        )
        funciones = cur.fetchall()
        print("\n5) Funciones en el esquema rag:")
        for firma, resultado in funciones or [("(ninguna)", "")]:
            print(f"   {firma} -> {resultado}")

        print("\n6) Permisos de tu usuario:")
        for tabla in ("rag.documents", "rag.chunks"):
            cur.execute(
                "SELECT has_table_privilege(%s, 'SELECT'), has_table_privilege(%s, 'INSERT'), has_table_privilege(%s, 'UPDATE')",
                (tabla, tabla, tabla),
            )
            sel, ins, upd = cur.fetchone()
            print(f"   {tabla}: SELECT={sel} INSERT={ins} UPDATE={upd}")

    print("\nConexion OK.")


def get_embeddings(texts: list[str], model: str) -> list[list[float]]:
    """Calcula los embeddings de todos los chunks en una sola llamada a OpenAI."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    result = client.embeddings.create(model=model, input=texts)
    embeddings = [item.embedding for item in result.data]
    for embedding in embeddings:
        if len(embedding) != EMBEDDING_DIM:
            raise ValueError(f"El embedding tiene {len(embedding)} dimensiones; rag.chunks espera {EMBEDDING_DIM}")
    return embeddings


def extract_text_from_pdf(path: str) -> str:
    """Devuelve el texto completo del PDF."""
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def split_text(text: str, chunk_size: int, chunk_overlap: int):
    """
    Divide el texto en chunks con control de tamaño y superposición.
    Usa RecursiveCharacterTextSplitter de LangChain.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return text_splitter.create_documents([text])


def ingest_pdf(
    pdf_path: str,
    document_id: str,
    titulo: str,
    chunk_size: int,
    chunk_overlap: int
):
    full_text = extract_text_from_pdf(pdf_path)
    docs = split_text(full_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = [(idx, doc.page_content.strip()) for idx, doc in enumerate(docs) if doc.page_content.strip()]

    # Embeddings antes de abrir la conexion: la transaccion en GCP queda corta
    embeddings = get_embeddings([texto for _, texto in chunks], model=EMBEDDING_MODEL)

    # Una sola transaccion: si algo falla, no queda nada a medias
    with get_connection() as conn, conn.cursor() as cur:
        # 1) Documento padre (rag.chunks lo referencia con document_id)
        cur.execute(
            """INSERT INTO rag.documents (document_id, titulo, version, origen)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (document_id) DO UPDATE
                  SET titulo = EXCLUDED.titulo,
                      version = EXCLUDED.version,
                      origen = EXCLUDED.origen""",
            (document_id, titulo, "1.0", os.path.basename(pdf_path)),
        )

        # 2) Un registro por chunk (upsert: re-ejecutar no duplica)
        for (idx, chunk_text), embedding in zip(chunks, embeddings):
            cur.execute(
                """INSERT INTO rag.chunks
                     (chunk_id, document_id, categoria, servicio, tipo_contenido, texto, embedding, version)
                   VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s)
                   ON CONFLICT (chunk_id) DO UPDATE
                      SET texto = EXCLUDED.texto,
                          embedding = EXCLUDED.embedding,
                          categoria = EXCLUDED.categoria,
                          servicio = EXCLUDED.servicio,
                          tipo_contenido = EXCLUDED.tipo_contenido,
                          version = EXCLUDED.version,
                          actualizado_en = now()""",
                (
                    f"{document_id}-{idx}",
                    document_id,
                    "base_conocimiento",
                    "general",
                    "descripcion",
                    chunk_text,
                    str(embedding),
                    "1.0",
                ),
            )

    print(f" Ingestado: {pdf_path} | chunks: {len(chunks)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta del RAG en GCP")
    parser.add_argument("--ingestar", action="store_true", help="Carga el PDF en GCP (sin esto solo prueba la conexion)")
    args = parser.parse_args()

    try:
        if not args.ingestar:
            probar_conexion()
        else:
            PDF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Base_Conocimiento_RAG_Eventos_v2.pdf")
            ingest_pdf(
                PDF_PATH,
                document_id="Base_Conocimiento_RAG_Eventos_v2.pdf",
                titulo="Base de conocimiento: Servicio de Eventos",
                chunk_size=900,
                chunk_overlap=200
            )
    except psycopg.OperationalError as error:
        print(f"\nNo se pudo conectar: {error}")
        print("Si es timeout, la instancia puede estar apagada fuera de horario.")
