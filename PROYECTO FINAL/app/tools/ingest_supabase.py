import os
import pdfplumber
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from supabase import create_client

load_dotenv()

# Modelo de embeddings: debe ser el mismo que use retriever.py al buscar
# y su dimensión debe coincidir con vector(N) de rag.chunks
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text: str, model: str):
    result = openai_client.embeddings.create(
        model=model,
        input=text
    )
    return result.data[0].embedding

def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("Faltan SUPABASE_URL o SUPABASE_KEY en el .env")

    return create_client(url, key)

def extract_text_from_pdf(path: str):
    """
    Devuelve el texto completo del PDF y la posición (carácter)
    donde empieza cada página: [(posición, número de página), ...]
    """
    text = ""
    inicios = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                inicios.append((len(text), page.page_number))
                text += page_text + "\n"
    return text, inicios

def split_text(text: str, chunk_size: int, chunk_overlap: int):
    """
    Divide el texto en chunks con control de tamaño y superposición.
    Usa RecursiveCharacterTextSplitter de LangChain.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True  # guarda en doc.metadata["start_index"] dónde empieza el chunk
    )

    docs = text_splitter.create_documents([text])
    # Cada documento tiene .page_content con el texto del chunk
    return docs

def pagina_en(posicion: int, inicios):
    """Devuelve el número de página que contiene ese carácter del texto."""
    pagina = inicios[0][1]
    for inicio, numero in inicios:
        if inicio <= posicion:
            pagina = numero
    return pagina

def ingest_pdf(
    pdf_path: str,
    document_id: str,
    titulo: str,
    chunk_size: int,
    chunk_overlap: int
):
    supabase = get_supabase()
    rag = supabase.schema("rag")

    # 1) Documento padre (rag.chunks lo referencia con document_id)
    rag.table("documents").upsert({
        "document_id": document_id,
        "titulo": titulo,
        "version": "1.0",
        "origen": os.path.basename(pdf_path)
    }).execute()

    full_text, inicios = extract_text_from_pdf(pdf_path)
    docs = split_text(full_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    for idx, doc in enumerate(docs):
        chunk_text = doc.page_content.strip()
        if not chunk_text:
            continue

        # Páginas donde empieza y termina el chunk (puede cruzar de página)
        inicio = doc.metadata["start_index"]
        fin = inicio + len(doc.page_content) - 1

        embedding = get_embedding(chunk_text, model=EMBEDDING_MODEL)

        # 2) Un registro por chunk (upsert: re-ejecutar no duplica)
        rag.table("chunks").upsert({
            "chunk_id": f"{document_id}-{idx}",
            "document_id": document_id,
            "categoria": "base_conocimiento",
            "servicio": "general",
            "tipo_contenido": "descripcion",
            "texto": chunk_text,
            "embedding": embedding,
            "metadata": {
                "source": os.path.basename(pdf_path),
                "chunk_index": idx,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "embedding_model": EMBEDDING_MODEL,
                "pagina_inicio": pagina_en(inicio, inicios),
                "pagina_fin": pagina_en(fin, inicios)
            }
        }).execute()

    print(f" Ingestado: {pdf_path} | chunks: {len(docs)}")

if __name__ == "__main__":
    # Path portable (funciona en Windows y Linux/Render)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PDF_PATH = os.path.join(BASE_DIR, "Base_Conocimiento_RAG_Eventos_v2.pdf")

    ingest_pdf(
        PDF_PATH,
        document_id="Base_Conocimiento_RAG_Eventos_v2.pdf",
        titulo="Base de conocimiento: Servicio de Eventos",
        chunk_size=900,
        chunk_overlap=200
    )
