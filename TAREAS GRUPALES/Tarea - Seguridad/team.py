"""Compatibilidad con el ejemplo de clase: un solo agente, sin supervisor."""
from agent.graph import QuoteAgent, OllamaInterpreter
from app import main

# Entrada para conversar: reutiliza app.main; la lógica del monoagente está en agent/graph.py.
if __name__ == "__main__":
    raise SystemExit(main())
