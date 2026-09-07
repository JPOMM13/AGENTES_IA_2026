# RAG de Iniciativas y Procedimientos

Primera version en Python de un agente que responde unicamente con informacion
recuperada de seis PDF locales. El flujo es: PDF -> paginas -> chunks ->
Ollama Embeddings -> Chroma -> retriever -> tool -> agente.

## Requisitos

- Python 3.11 o superior.
- Ollama instalado y ejecutandose localmente.
- El modelo `llama3.2:latest` disponible en Ollama.
- El modelo de embeddings `nomic-embed-text` disponible en Ollama.

## Instalacion

Desde esta carpeta:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

El modelo generativo y los embeddings se ejecutan localmente mediante Ollama. Para instalar ambos modelos y comprobar el servicio:

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
ollama list
```

Puedes utilizar otro modelo instalado modificando `OLLAMA_MODEL` en `.env`. El modelo de embeddings se configura con `OLLAMA_EMBEDDING_MODEL`.
La URL predeterminada del servicio es `http://127.0.0.1:11434` y puede cambiarse
mediante `OLLAMA_BASE_URL`.

## Ejecucion

```bash
python main.py
```

En la primera ejecucion se crean los embeddings y se persisten en `chroma_db/`.
Las siguientes ejecuciones reutilizan el indice. Si los PDF cambian, el indice se
reconstruye automaticamente usando el manifiesto de archivos.

Para forzar la reconstruccion:

```bash
python main.py --reindex
```

Para comprobar solamente que los documentos se indexan:

```bash
python main.py --check
```

## Preguntas sugeridas

- ¿Cual es el estado y avance de Samsung Pay Visa?
- ¿Que pendientes tiene Samsung Pay Visa?
- ¿Cual es el proximo hito de COFT Amex?
- ¿Cuantos pipelines faltan migrar a GitHub Actions?
- ¿Que debo validar antes de iniciar UAT?
- ¿Que evidencias se necesitan para un pase a produccion?
- ¿Cuando debe hacerse rollback de un pase a produccion?
- ¿Como se escala un incidente P1?
- ¿Cual es el presupuesto de Samsung Pay Visa?

La ultima pregunta debe indicar que el presupuesto no aparece en las fuentes.

## Estructura

```text
data/                       PDF clasificados por tipo
chroma_db/                  indice local (se crea al ejecutar)
vector.py                   carga, metadata, chunks e indexacion
toolbox.py                  herramienta de recuperacion
prompt.py                   reglas que limitan las respuestas a los PDF
main.py                     agente, salida estructurada y consola
```

El LLM y los embeddings se ejecutan localmente en Ollama. El proyecto no requiere una clave de OpenAI ni consulta servicios externos. No incorpora memoria, APIs de consulta externas ni multiagentes.
