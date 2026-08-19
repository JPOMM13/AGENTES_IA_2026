# Asistente multiagente de iniciativas

MVP académico que usa LangGraph para coordinar cuatro agentes: iniciativas,
procedimientos, seguimiento y estado técnico. Todos los datos son simulados y
se leen desde archivos JSON locales.

El avance técnico compara cada requisito del Spec con la evidencia del
repositorio simulado. Los factores son `completed=1`, `partial=0.5` y
`pending=0`; la cantidad de commits no interviene en el cálculo.

## Modo inteligente opcional

El Supervisor puede usar un LLM para comprender la intención y corregir el
nombre de una iniciativa. Los datos y el cálculo del avance siempre permanecen
en Python y los JSON, para evitar que el modelo invente información.

El modo determinístico viene activado por defecto y no requiere credenciales.
Para usar Ollama local, copia `.env.example` como `.env` y configura:

```text
USE_LLM=true
OLLAMA_MODEL=llama3.2:latest
```

Si el LLM no está disponible, el Supervisor vuelve automáticamente a las reglas
y el programa continúa funcionando.

## Ejecución

Requiere Python 3.11 o superior.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.graph
```

También puede abrirse `notebooks/langgraph_initiatives_demo.ipynb` y ejecutar
sus celdas en orden. El sistema no necesita API key ni acceso a servicios
externos.

## Ejemplos

- `¿Cuál es el estado de Samsung Pay?`
- `¿Cómo hago un pase a producción?`
- `¿Qué falta para Samsung Pay?`
- `¿Cuál es el avance técnico de Samsung Pay?`
- `¿Cómo va Samsung Pay y qué falta para pasar a producción?`

La última consulta recorre todos los agentes y Samsung Pay obtiene un avance
técnico estimado de 75 %.
