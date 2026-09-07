# Agente de cotizaciones y evaluación — UTEC

Demo Python sin Streamlit: un único agente con LangGraph, reglas determinísticas y evaluación separada en LangSmith. `team.py` y `langsmith_evaluator.py` son puntos de entrada equivalentes a los del ejemplo de clase.

## Ejecutar

Desde esta carpeta, con Python 3.12 o superior:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Editar `.env` localmente y colocar las claves de OpenAI y LangSmith. No pegarlas en el chat. `.env` se carga desde la raíz del proyecto incluso cuando el comando se ejecuta desde otra carpeta. No se imprime su contenido.

```bash
python app.py
# Equivalente: python team.py
```

Ejemplo de conversación con una fecha futura que exista en el JSON:

```text
Cotiza un cumpleaños para 40 asistentes el 12 de septiembre de 2026 a las 20:00 en Miraflores.
Cambia la solicitud a 80 asistentes.
Quiero hablar con un asesor.
```

`/nuevo` inicia otra sesión; `salir` termina. La memoria dura mientras permanece abierta la CLI. El runtime usa el reloj real de Lima. El JSON sintético contiene stock del 1 de septiembre al 15 de octubre de 2026; fuera de ese intervalo el agente deriva por falta de disponibilidad. Ajustar las fechas del JSON para demostraciones posteriores.

El modelo por defecto conserva `gpt-5.6-terra` porque lo pide el SPEC. La disponibilidad de ese identificador en tu cuenta de la API no se ha verificado. Si el proveedor lo rechaza, configura un modelo accesible con salida estructurada en **ambas** variables `OPENAI_MODEL` y `OPENAI_JUDGE_MODEL`. No confundir el modelo seleccionado en Codex con acceso a un modelo de la API.

## Evaluación para la tarea

Sin claves ni consumo de APIs:

```bash
python -m pytest -q
python -m evaluation.run_evaluation --offline
```

Este modo sustituye la extracción por fixtures explícitas. Ejecuta el grafo real y las reglas, pero **no evalúa la comprensión de lenguaje del LLM, no aplica juez y no crea trazas remotas**. El reporte se guarda en `reports/` como Markdown y JSON.

Con ambas claves configuradas:

```bash
python -m evaluation.run_evaluation
# Equivalente: python langsmith_evaluator.py
```

El comando crea o reutiliza un dataset versionado por contenido, ejecuta 15 casos con el LLM real, registra un experimento, aplica 11 métricas determinísticas y cuatro notas semánticas, muestra el experimento y genera un reporte local. Los datos de extracción que acompañan los ejemplos son fixtures exclusivas del modo offline: el runtime online solo recibe los mensajes de cada turno, nunca las respuestas de referencia. La prueba de fallos usa un repositorio inyectado que falla; el usuario no puede activar este mecanismo desde su mensaje.

El reloj de evaluación es `EVAL_REFERENCE_DATETIME`; cambiarlo requiere actualizar las expectativas temporales del dataset. Los ejemplos actuales están diseñados para `2026-09-06T20:00:00-05:00`. Opcionalmente configura `LANGSMITH_ENDPOINT` según la región de tu cuenta. La evaluación online activa tracing dentro de su contexto incluso si se desactiva para la CLI.

Un caso aprueba solo si sus 11 métricas binarias valen 1 y, en modo online, las cuatro notas del juez son al menos 4/5. No se promedian fallos críticos con buenas notas de redacción. Un error del juez queda sin nota y el caso se considera incompleto. Código de salida: 0 todos aprobados; 1 fallidos/incompletos; 2 claves faltantes. Los errores de conexión o configuración del SDK interrumpen la ejecución y no se presentan como experimentos exitosos.

## Documentos para entregar

- `docs/METRICAS_PARA_GOOGLE_DOCS.md`: texto y tabla listos para copiar a Google Docs.
- `docs/ANALISIS_SPEC_Y_EJEMPLO.md`: adaptación del SPEC y del ZIP; límites y supuestos.
- `docs/GUIA_CAPTURAS.md`: pasos para conseguir evidencias auténticas de LangSmith.
- `docs/VALIDACION_LOCAL.md`: resultados ejecutados en este entorno.

## Diseño

```text
app.py / team.py
  → QuoteAgent → StateGraph
    → interpretación estructurada → actualizar estado → faltantes
    → reglas → catálogo → cobertura → disponibilidad → ranking
    → cotización → validación → respuesta o derivación

DataRepository ← JsonDataRepository ← data/mock_data_eventos.json

evaluation.dataset → ejecución aislada por caso → evaluadores + juez → LangSmith
```

Los nodos son funciones de un mismo agente. No hay supervisor ni agentes especializados. El LLM extrae intención y datos, y selecciona una apertura entre frases aprobadas; el cuerpo comercial se renderiza mediante código. Esta decisión deliberada limita la redacción libre para que precios, fechas, stock y condiciones no puedan alterarse durante la presentación.

`DataRepository` permite migrar a SQL/API sin reescribir las tools. `config_mock` fija impuestos sintéticos, moneda y feriado; el catálogo define capacidad y precios. El ranking ordena por afinidad, preferencia autorizada, menor capacidad excedente, menor precio e ID. El presupuesto incluye impuestos. La política mock permite un pack por solicitud, no suma varios packs para cubrir capacidad.

Solo se usan productos activos con capacidad suficiente, cobertura explícita y al menos una unidad disponible todos los días de entrega a recojo, inclusive. Para feriado mock se usa entrega el día hábil anterior y recojo el siguiente hábil. Los importes usan `Decimal` con redondeo a dos decimales. La validez comercial mock es de 24 horas.

Cada turno invalida cotizaciones y validaciones previas. La derivación devuelve un resumen para contacto manual: no envía mensajes ni crea reservas. Los reintentos solo aplican a lecturas/interpretación ante timeout o conexión: un intento inicial y cinco reintentos, sin multiplicarlos con reintentos del SDK. Otros errores derivan directamente.

## Datos y privacidad

**No se entregaron el Excel `BD_Relacional_Agente_Eventos.xlsx` ni el Profile Card v3.2.** Todos los registros son sintéticos, identificados como mock. Las once entidades están presentes; los históricos están vacíos y la demo no escribe transacciones. Deben validarse las reglas y reemplazarse los datos con esos documentos antes de considerar esta implementación una reproducción del negocio real.

Las preferencias históricas solo se consultan con `trusted_customer_id` proporcionado por una capa de autenticación confiable, y con consentimiento registrado. La CLI no autentica clientes, así que no habilita preferencias personales. Indicar un correo en el chat no prueba identidad. El dataset utiliza identificadores sintéticos para probar el control de consentimiento.

Se redactan patrones comunes de correo y teléfono antes del grafo y de las trazas. Esto no es un anonimizador completo: usar solo datos sintéticos en la evaluación académica. Las API keys se manejan en configuración y no se incorporan a estado, prompts ni reportes.

## Verificación y dependencias

Desarrollado y verificado localmente con Python 3.14.7. `requirements.txt` contiene rangos de compatibilidad; `requirements-lock.txt` registra las versiones exactas usadas para las pruebas. Para reproducirlas, usar `pip install -r requirements-lock.txt`. No se ha ejecutado una matriz de versiones de Python ni una llamada real a OpenAI/LangSmith.

APIs consultadas: [StateGraph](https://docs.langchain.com/oss/python/langgraph/graph-api), [evaluadores de código](https://docs.langchain.com/langsmith/code-evaluator-sdk) y [evaluación de aplicaciones](https://docs.langchain.com/langsmith/evaluate-llm-application).
