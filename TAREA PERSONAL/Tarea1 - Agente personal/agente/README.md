# Agente de recomendaciones

Primera versión sencilla basada en `Agentic_Profile_Card_v3.0_Codex.md` y en los
ejemplos de agentes con LangChain, LangGraph y Ollama.

## Estructura

```text
agente/
├── recomendaciones/
│   ├── __init__.py
│   ├── catalogo.py     # opciones mock y cálculo de utilidad
│   └── estado.py       # modelo interno de la conversación
├── .env                # modelo local utilizado
├── .gitignore
├── main.py             # crea y ejecuta el agente
├── prompts.py          # system prompt y prompt dinámico
├── README.md
├── requirements.txt
└── tools.py            # tools y reglas autorizadas
```

## Tipos de agente mostrados

Es un único monoagente híbrido:

- **Model-Based Reflex:** recuerda ocasión, asistentes, fecha, ubicación y resultados.
- **Simple Reflex:** pregunta datos faltantes y deriva solicitudes humanas o descuentos.
- **Goal-Based:** mantiene un objetivo explícito hasta recomendar o derivar.
- **Utility-Based:** filtra alternativas y elige la de mayor utilidad con pesos fijos.

## Instalación

Desde la carpeta `agente`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
ollama pull llama3.2
```

## Ejecución

```bash
python main.py
```

Ejemplo:

```text
Necesito algo práctico para un cumpleaños.
Somos 20, será el 2026-08-15 en Miraflores.
```

El catálogo y la cobertura todavía son simulados. Esta versión no cotiza, no realiza
pagos y no guarda memoria permanente.

