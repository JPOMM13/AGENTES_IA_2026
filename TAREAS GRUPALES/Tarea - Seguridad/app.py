"""Conversación CLI sin Streamlit. Memoria mientras la sesión permanece abierta."""
from config import Settings
from repositories.json_repository import JsonDataRepository
from agent.graph import QuoteAgent, OllamaInterpreter

# Inicia la conversación por terminal y conserva el estado entre mensajes hasta salir o usar /nuevo.
def main():
    try:
        settings = Settings.load()
        from local_llm import check_models
        check_models([settings.model])
        agent = QuoteAgent(JsonDataRepository(settings.data_path), OllamaInterpreter(settings))
    except ValueError as exc:
        print(exc)
        return 2
    print("Agente de eventos MOCK. Escribe salir para terminar o /nuevo para reiniciar.")
    state = None
    while True:
        try:
            message = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if message.lower() == "salir":
            break
        if message == "/nuevo":
            state = None
            continue
        if message:
            # Envía el mensaje con el estado previo: así el agente recuerda datos de turnos anteriores.
            state = agent.respond(message, state)
            print("Agente:", state["response"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
