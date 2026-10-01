# POC - Workflow agentico para cotizaciones de eventos

Esta POC implementa un workflow agentico conversacional para recomendar y cotizar eventos con datos mockeados.

No usa PostgreSQL, pgvector, NoSQL, Redis ni WhatsApp real. Todo el catalogo, cobertura, disponibilidad, RAG y cotizacion son mocks locales.

## Instalacion

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecutar

```bash
streamlit run app/main.py
```

Luego abre la URL local que muestre Streamlit, normalmente:

```text
http://localhost:8501
```

## Pruebas sugeridas

## Configurar LLM

La POC usa una configuracion unica para el LLM. Con esto cambias de Ollama a OpenAI o Anthropic sin tocar el codigo.

La ejecucion del LLM esta centralizada en `app/llm.py` con un unico metodo (`call_llm`). El proveedor se cambia solo por variables de entorno.

Puedes configurar el proveedor editando `.env` en la raiz del proyecto. `.env.example` queda como plantilla.

Ollama local:

```env
LLM_ENABLED=true
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2:latest
LLM_HOST=http://127.0.0.1:11434
LLM_API_KEY=
```

Ollama no requiere API key, pero si requiere tener el servicio local activo. Por defecto usa:

```bash
LLM_HOST=http://127.0.0.1:11434
```

OpenAI:

```env
LLM_ENABLED=true
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=...
```

Anthropic:

```env
LLM_ENABLED=true
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-haiku-latest
LLM_API_KEY=...
```

La misma configuracion se usa para extraccion, decision agentica y redaccion final.

Imagen multimodal del evento:

```env
IMAGE_GENERATION_ENABLED=true
IMAGE_PROVIDER=openai
IMAGE_MODEL=gpt-image-1
IMAGE_API_KEY=...
IMAGE_SIZE=1024x1024
IMAGE_QUALITY=high
```

Si `IMAGE_GENERATION_ENABLED=false` o no hay `IMAGE_API_KEY`, la POC usa el SVG local como respaldo.

## Capa agentica con `create_agent`

La POC usa `create_agent` de LangChain para dos tareas controladas:

- extraccion estructurada de datos del usuario: nombre, contacto, fecha, distrito, tipo de evento, asistentes y preferencias;
- decision de la siguiente accion de alto nivel del workflow.

En el codigo se crean agentes con la misma forma vista en clase, usando el modelo configurado:

```python
def crear_agente_extractor():
    herramientas = [registrar_campos_extraidos]
    agente = create_agent(
        model=config.langchain_model,
        tools=herramientas,
        system_prompt="Extrae campos explicitos del usuario sin inventar datos.",
    )
    return agente
```

La POC tiene dos agentes creados asi:

- `crear_agente_extractor()`: interpreta el mensaje y extrae campos estructurados.
- `crear_agente_decisor()`: decide si pide datos, consulta precios, valida/recomienda, cotiza, deriva o muestra imagen.

Esta capa usa un agente tipo ReAct/goal-based acotado:

- el LLM lee frases naturales como `JOhn manchego y mi numero es 989515182` y llama una tool para registrar campos;
- el LLM interpreta intenciones de pedido como revisar, quitar, agregar o reemplazar productos y las devuelve como acciones estructuradas; las tools no modifican estado por si solas;
- el LLM decide la siguiente accion: pedir datos, responder precio, validar/recomendar, cotizar, derivar, etc.;
- antes de elegir una tool de negocio evalua prerequisitos minimos: por ejemplo, no puede validar/recomendar sin tipo de evento, asistentes, fecha, distrito, cotizante, contacto y productos/servicios solicitados;
- `economico`, `premium`, `formal` o `sencillo` son preferencias, no productos; el agente debe pedir productos/servicios concretos antes de recomendar o cotizar;
- los productos/servicios concretos pueden variar por cliente: cerveza, vino, gaseosas, hielo, bartender, bar movil, etc.;
- el mock maneja familias de productos para alternativas: `licores` agrupa vino, cerveza y ron; `sin_alcohol` agrupa agua y gaseosa. Si falta stock o no existe un producto exacto, el agente informa alternativas parecidas con stock antes de reemplazar;
- puede responder precios informativos de productos o paquetes si el usuario pregunta por un item concreto, sin generar cotizacion ni reservar stock;
- las tools internas devuelven JSON o una accion controlada;
- el workflow deterministico sigue ejecutando las validaciones reales;
- no se toma texto final del LLM para precios o stock, solo la informacion devuelta por tools.

En resumen: `create_agent` interpreta y dirige la conversacion, pero las reglas y tools del workflow siguen protegiendo precios, stock, cobertura y cotizacion.

## Estructura del codigo

La POC separa responsabilidades principales:

- `app/domain.py`: modelos de dominio legibles como cliente, evento, productos, cotizacion y memoria.
- `app/contracts.py`: contratos de entrada/salida para decisiones del agente y readiness de tools.
- `app/repositories.py`: capa de acceso a memoria; hoy llama JSON mock, luego puede cambiarse por Redis, PostgreSQL o NoSQL.
- `app/agentic_tools.py`: definicion de tools agenticas mock que representan catalogo, cobertura, stock y cotizacion.
- `app/artifacts.py`: generacion del artefacto visual multimodal de la cotizacion confirmada, con SVG local de respaldo.
- `app/workflow.py`: orquestacion del workflow agentico, validaciones y llamadas a tools mock.

Al confirmar una cotizacion con `genera la cotizacion`, el flujo genera:

- la cotizacion mock en memoria;
- persistencia mock de sesion;
- un PNG generado por modelo de imagen en `app/data/generated/`; si no hay proveedor configurado, usa un SVG local de respaldo.

Para reducir alucinaciones se usa:

- tool calling estructurado, no texto libre, para campos e intenciones;
- evidencia textual antes de aceptar datos extraidos;
- grounding contra catalogo/stock mock antes de recomendar;
- guardrails de estado para no pedir datos ya conocidos ni derivar a humano sin solicitud explicita;
- respuesta final del LLM tratada como redaccion: si contradice el workflow, se descarta.

## Memoria conversacional

La POC maneja dos niveles de memoria:

- Memoria corta de sesion: vive en `st.session_state.quote_state` y permite que el agente recuerde lo que el usuario ya dijo dentro de la conversacion actual.
- Memoria corta mock tipo Redis: se guarda tambien en `app/data/mock_redis_session.json` usando `session_id` como clave. Para la POC local se conserva solo la ultima sesion activa; en Redis real habria una key por `session_id` con TTL. Este archivo simula Redis y esta ignorado por Git.
- Memoria mock persistente: cuando ya existe nombre de cotizante y contacto, se guarda una copia local en `app/data/mock_session_memory.json`. Ese archivo representa la BD transaccional/NoSQL mock de la POC y esta ignorado por Git.

La diferencia de identificacion es importante:

- `mock_redis_session.json` identifica la conversacion viva por `session_id`; no identifica a la persona.
- `mock_session_memory.json` identifica al cliente por `customer_name + contact`, por ejemplo nombre y telefono, para poder retomar una cotizacion anterior.

Para retomar una cotizacion anterior en una nueva conversacion, el usuario debe pedirlo e identificarse con nombre y telefono/correo:

```text
Quiero retomar mi cotizacion anterior, soy John Manchego mi numero es 989515182
```

El flujo no retoma una conversacion anterior solo por nombre; exige contacto para reducir cruces entre clientes.

Cuando se retoma una cotizacion anterior:

```text
1. Se crea o usa un session_id nuevo para el chat actual.
2. Se busca la cotizacion anterior por customer_name + contact en la memoria persistente mock.
3. Se carga esa cotizacion dentro del session_id actual.
4. Se guarda la foto actualizada en mock_redis_session.json, simulando Redis.
```

Recomendacion completa con datos minimos:

```text
Soy Juan Perez, mi telefono es 999888777. Necesito bebidas premium para un matrimonio de 100 personas el 25 de octubre en Miraflores
```

Cotizacion:

```text
Cuanto cuesta?
```

Descuento:

```text
Me haces 15% de descuento?
```

Derivacion:

```text
Si, derivame con un asesor
```

Imagen referencial, solo despues de cotizar:

```text
Muestrame una imagen del evento
```

RAG mock:

```text
Que politica tienen para descuentos?
```

Sin cobertura:

```text
Soy Ana Torres, mi telefono es 999111222. Necesito bebidas sencillas para 80 personas el 25 de octubre en Chosica
```

## Tests

```bash
pytest
```

## Evals del agente

Los evals validan el comportamiento conversacional completo del workflow agentico: memoria temporal, extraccion de campos, fechas, productos solicitados, consulta a catalogo/stock mock, reemplazos, no derivacion sin pedido explicito y generacion de cotizacion solo cuando corresponde.

Modo deterministico, recomendado para demostrar que las reglas y tools del workflow funcionan sin variabilidad del LLM:

```bash
.venv/bin/python evals/run_evals.py
```

Con traza del flujo para revisar que tool/decision se ejecuto en cada caso:

```bash
.venv/bin/python evals/run_evals.py --trace
```

Con LLM activo, usando la configuracion actual de proveedor/modelo:

```bash
export LLM_ENABLED=true
export LLM_PROVIDER=ollama
export LLM_MODEL="llama3.2:latest"
.venv/bin/python evals/run_evals.py --with-llm
```

Casos cubiertos actualmente:

- fecha con anio explicito y asistentes dados en un turno posterior;
- producto no disponible con alternativa aceptada por el usuario;
- stock insuficiente con reemplazo implicito;
- derivacion humana solo si el usuario la solicita;
- consulta informativa de precio sin generar cotizacion;
- cotizacion formal despues de una recomendacion valida.
