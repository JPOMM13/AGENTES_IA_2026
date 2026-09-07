"""Carga, fragmentacion e indexacion de los PDF del proyecto."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_db"
MANIFEST_PATH = CHROMA_DIR / "manifest.json"
COLLECTION_NAME = "iniciativas_procedimientos"


# Busca recursivamente todos los archivos PDF almacenados en la carpeta data.
def _pdf_paths(data_dir: Path = DATA_DIR) -> list[Path]:
    return sorted(data_dir.glob("**/*.pdf"))


# Calcula la huella SHA-256 de un archivo para detectar cambios o duplicados.
def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


# Construye un manifiesto que relaciona cada PDF con su huella SHA-256.
def _manifest(data_dir: Path = DATA_DIR) -> dict[str, str]:
    return {
        str(path.relative_to(data_dir)): _file_hash(path)
        for path in _pdf_paths(data_dir)
    }


# Lee el manifiesto de la indexacion anterior; devuelve None si no existe o es invalido.
def _read_manifest() -> dict[str, Any] | None:
    if not MANIFEST_PATH.exists():
        return None
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# Convierte el nombre tecnico del archivo en un nombre legible para la metadata.
def _human_name(path: Path) -> str:
    stem = path.stem
    for prefix in ("iniciativa_", "procedimiento_"):
        if stem.startswith(prefix):
            stem = stem.removeprefix(prefix)
            break
    return stem.replace("_", " ").strip().title()


# Carga los PDF pagina por pagina y agrega metadata de fuente, pagina, tipo y nombre.
def load_pdf_pages(data_dir: Path = DATA_DIR) -> list[Any]:
    """Carga cada pagina como Document y normaliza su metadata."""
    paths = _pdf_paths(data_dir)
    if not paths:
        raise FileNotFoundError(f"No se encontraron PDF en {data_dir}")

    documents = []
    for path in paths:
        tipo = "iniciativa" if path.parent.name == "iniciativas" else "procedimiento"
        for document in PyPDFLoader(str(path)).load():
            document.metadata.update(
                {
                    "source": path.name,
                    "page": int(document.metadata.get("page", 0)),
                    "tipo": tipo,
                    "nombre": _human_name(path),
                }
            )
            documents.append(document)
    return documents


# Divide las paginas en chunks de 1000 caracteres con 200 caracteres de solapamiento.
def split_documents(documents: list[Any]) -> list[Any]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    return splitter.split_documents(documents)


class KnowledgeBase:
    """Administra Chroma y evita indexar dos veces los mismos archivos."""

    # Inicializa Chroma y crea o reutiliza el indice vectorial segun el manifiesto.
    def __init__(self, reindex: bool = False) -> None:
        files_manifest = _manifest()
        if not files_manifest:
            raise FileNotFoundError(f"No se encontraron PDF en {DATA_DIR}")

        embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        current_manifest = {
            "embedding_provider": "ollama",
            "embedding_model": embedding_model,
            "files": files_manifest,
        }

        needs_index = reindex or _read_manifest() != current_manifest
        if needs_index and CHROMA_DIR.exists():
            shutil.rmtree(CHROMA_DIR)
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        self.vector_store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=OllamaEmbeddings(
                model=embedding_model,
                base_url=ollama_base_url,
            ),
            persist_directory=str(CHROMA_DIR),
        )

        if needs_index or self.vector_store._collection.count() == 0:
            chunks = split_documents(load_pdf_pages())
            if not chunks:
                raise RuntimeError("Los PDF no produjeron contenido para indexar.")
            ids = [
                hashlib.sha256(
                    (
                        f"{doc.metadata['source']}:{doc.metadata['page']}:"
                        f"{index}:{doc.page_content}"
                    ).encode("utf-8")
                ).hexdigest()
                for index, doc in enumerate(chunks)
            ]
            self.vector_store.add_documents(chunks, ids=ids)
            MANIFEST_PATH.write_text(
                json.dumps(current_manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})

    # Devuelve la cantidad total de chunks almacenados en la coleccion de Chroma.
    @property
    def chunk_count(self) -> int:
        return self.vector_store._collection.count()
