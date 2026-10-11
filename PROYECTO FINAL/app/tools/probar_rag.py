# solo para validar la consulta RAG
# Uso, desde la carpeta PROYECTO FINAL:
#   python app/tools/probar_rag.py
#   python -m app.tools.probar_rag

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from openai import OpenAI
from app.tools.retriever import retrieve_chunks

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
CHAT_MODEL = "gpt-4o-mini"
RAG_THRESHOLD = float(os.getenv("RAG_THRESHOLD", "0.40"))

def answer_question(question: str, top_k: int = 6, threshold: float = RAG_THRESHOLD):

    # 🔎 1) Retrieval
    chunks = retrieve_chunks(question, top_k=top_k, threshold=threshold)

    if not chunks:
        return "No encontré información relevante en la base de conocimiento."

    # 📚 2) Construir contexto
    context = "\n\n---\n\n".join([c["texto"] for c in chunks])

    # 🤖 3) Llamar al LLM
    messages = [
        {
            "role": "system",
            "content": (
                "Responde únicamente usando el contexto proporcionado. "
                "Si no encuentras la respuesta en el contexto, indícalo claramente."
            )
        },
        {
            "role": "user",
            "content": f"CONTEXTO:\n{context}\n\nPREGUNTA:\n{question}"
        }
    ]

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=0.2
    )

    return response.choices[0].message.content

if __name__ == "__main__":
    pregunta = input("Haz tu pregunta: ")
    respuesta = answer_question(pregunta)

    print("\n=== RESPUESTA ===\n")
    print(respuesta)


