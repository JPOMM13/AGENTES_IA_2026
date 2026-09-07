"""Consola del Agente RAG de Iniciativas y Procedimientos."""

from __future__ import annotations

import argparse
import os
from typing import Literal

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from prompt import SYSTEM_PROMPT
from toolbox import create_rag_tool
from vector import KnowledgeBase


class RespuestaAgente(BaseModel):
    respuesta: str = Field(description="Respuesta basada unicamente en los PDF")
    fuentes: list[str] = Field(description="PDF y pagina usados para responder")
    tools_usadas: list[str] = Field(description="Herramientas utilizadas")
    tipo_consulta: Literal["iniciativa", "procedimiento", "desconocido"]


# Construye la base de conocimiento, registra la tool RAG y configura el agente LangChain.
def build_agent(reindex: bool = False):
    knowledge_base = KnowledgeBase(reindex=reindex)
    tool = create_rag_tool(knowledge_base)
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.2:latest"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        temperature=0,
    )
    agent = create_agent(
        model=llm,
        tools=[tool],
        system_prompt=SYSTEM_PROMPT,
        response_format=RespuestaAgente,
    )
    return agent, knowledge_base


# Construye una respuesta valida cuando Ollama devuelve texto en lugar de JSON.
def _response_from_messages(result: dict) -> RespuestaAgente | None:
    answer = ""
    sources: list[str] = []
    tools: list[str] = []

    for message in result.get("messages", []):
        message_type = type(message).__name__
        if message_type == "AIMessage" and isinstance(message.content, str):
            if message.content.strip():
                answer = message.content.strip()
        elif message_type == "ToolMessage":
            tool_name = getattr(message, "name", None)
            if tool_name and tool_name not in tools:
                tools.append(tool_name)
            for line in str(message.content).splitlines():
                if line.startswith("Fuente: "):
                    source = line.removeprefix("Fuente: ").strip()
                    if source not in sources:
                        sources.append(source)

    if not answer:
        return None
    if any(source.startswith("iniciativa_") for source in sources):
        query_type = "iniciativa"
    elif any(source.startswith("procedimiento_") for source in sources):
        query_type = "procedimiento"
    else:
        query_type = "desconocido"
    return RespuestaAgente(
        respuesta=answer,
        fuentes=sources,
        tools_usadas=tools,
        tipo_consulta=query_type,
    )


# Presenta en consola la respuesta estructurada, sus fuentes y la herramienta utilizada.
def _print_response(result: dict) -> None:
    response = result.get("structured_response")
    if response is None:
        response = _response_from_messages(result)
        if response is None:
            print("No se pudo obtener una respuesta del agente.")
            return
    if isinstance(response, dict):
        response = RespuestaAgente.model_validate(response)

    print(f"\n{response.respuesta}")
    print("\nFuentes:")
    if response.fuentes:
        for source in response.fuentes:
            print(f"- {source}")
    else:
        print("- Ninguna")
    print(f"Tools usadas: {', '.join(response.tools_usadas) or 'ninguna'}")
    print(f"Tipo de consulta: {response.tipo_consulta}")


# Lee las opciones --reindex y --check enviadas al ejecutar el programa.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reindex", action="store_true", help="Reconstruye chroma_db")
    parser.add_argument("--check", action="store_true", help="Indexa y muestra el total de chunks")
    return parser.parse_args()


# Valida la configuracion, inicia el agente y mantiene el ciclo interactivo de preguntas.
def main() -> int:
    args = parse_args()
    load_dotenv()
    try:
        agent, knowledge_base = build_agent(reindex=args.reindex)
    except Exception as exc:
        print(f"Error al preparar la base RAG: {exc}")
        return 1

    print(f"Base lista: {knowledge_base.chunk_count} chunks indexados.")
    if args.check:
        return 0

    print("Escribe una pregunta o 'salir' para terminar.")
    while True:
        try:
            question = input("\nPregunta: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            return 0
        if question.lower() in {"salir", "exit", "quit"}:
            print("Hasta luego.")
            return 0
        if not question:
            continue
        try:
            result = agent.invoke({"messages": [{"role": "user", "content": question}]})
            _print_response(result)
        except Exception as exc:
            print(f"No se pudo procesar la consulta: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
