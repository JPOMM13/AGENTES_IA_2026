# Cafe.AI — equipo publicitario multiagente

Proyecto educativo que utiliza LangGraph y un modelo local de Ollama para crear una campaña inicial de redes sociales para Cafe.AI.

## Arquitectura

El enrutador revisa el estado compartido y entrega el control al agente correspondiente:

```text
Enrutador → Creativo → Enrutador → Redactor → Enrutador
           → Diseñador → Enrutador → Validador → Enrutador → Fin
```

- **Enrutador:** crea el brief y controla el avance.
- **Creativo:** define el concepto rector.
- **Redactor:** crea piezas para Instagram, TikTok y LinkedIn.
- **Diseñador:** entrega dirección de arte y prompts visuales.
- **Validador:** comprueba campos y permite una sola corrección.

El diseñador no genera imágenes ni llama a servicios externos.

## Requisitos

- Python 3.10 o superior.
- [Ollama](https://ollama.com/) instalado y activo.
- Un modelo local. El valor predeterminado es `llama3.2:latest`.

Comprueba Ollama:

```bash
ollama list
```

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Las variables disponibles son:

```dotenv
OLLAMA_MODEL=llama3.2:latest
OLLAMA_BASE_URL=http://127.0.0.1:11434
MODEL_TEMPERATURE=0.2
```

## Uso por consola

Modo interactivo:

```bash
python -m cafe_ai_agents.cli
```

Brief directo y archivo de salida:

```bash
python -m cafe_ai_agents.cli \
  --brief "Crea la primera campaña orgánica de Cafe.AI" \
  --output campaign.md
```

Selección explícita del modelo:

```bash
python -m cafe_ai_agents.cli --model llama3.2:latest
```

## Notebook

Inicia Jupyter y abre `notebooks/cafe_ai_demo.ipynb`:

```bash
jupyter notebook
```

El notebook importa el mismo paquete usado por la CLI; la lógica no está duplicada.

## Pruebas

Las pruebas usan un modelo falso, por lo que no necesitan Ollama:

```bash
pytest -q
```

Verificaciones adicionales:

```bash
python -m compileall cafe_ai_agents
python -m cafe_ai_agents.cli --help
```

## Archivos principales

- `cafe_ai_agents/models.py`: datos que comparten los agentes.
- `cafe_ai_agents/prompts.py`: rol e instrucciones de cada agente.
- `cafe_ai_agents/agents.py`: métodos que ejecutan los roles.
- `cafe_ai_agents/graph.py`: nodos y conexiones de LangGraph.
- `cafe_ai_agents/formatter.py`: salida Markdown.
- `cafe_ai_agents/cli.py`: aplicación de consola.

Los métodos están documentados y las decisiones principales incluyen comentarios con `#` para facilitar el seguimiento del código.
