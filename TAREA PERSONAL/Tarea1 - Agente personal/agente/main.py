"""
Agente híbrido de recomendaciones basado en Agentic_Profile_Card_v3.0_Codex.md.

Ejecutar desde esta carpeta:
    python main.py
"""

import os
from pathlib import Path
from uuid import uuid4

from langchain.agents import create_agent

from prompts import prompt_con_modelo_interno
from recomendaciones import EstadoRecomendacion, crear_estado_inicial
from tools import TOOLS


def cargar_configuracion() -> None:
    """Carga pares CLAVE=VALOR del .env local sin otra dependencia."""
    ruta_env = Path(__file__).with_name(".env")
    if not ruta_env.exists():
        return
    for linea in ruta_env.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip())


cargar_configuracion()

agent = create_agent(
    model=f"ollama:{os.getenv('OLLAMA_MODEL', 'llama3.2')}",
    tools=TOOLS,
    middleware=[prompt_con_modelo_interno],
    state_schema=EstadoRecomendacion,
)


def conversar() -> None:
    """Mantiene una conversación y conserva su modelo interno entre turnos."""
    estado = crear_estado_inicial(session_id=str(uuid4()))
    print("Agente: Hola. Cuéntame qué ocasión estás organizando.")

    while True:
        mensaje = input("\nTú (o 'salir'): ").strip()
        if mensaje.lower() == "salir":
            break
        if not mensaje:
            continue

        estado["messages"].append({"role": "user", "content": mensaje})
        estado = agent.invoke(estado)
        print(f"Agente: {estado['messages'][-1].content}")


if __name__ == "__main__":
    conversar()
