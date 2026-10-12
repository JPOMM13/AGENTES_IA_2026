# Analisis del agente cotizador segun Anthropic

Referencia: [Building Effective Agents - Anthropic](https://www.anthropic.com/engineering/building-effective-agents)

## Clasificacion general

El agente cotizador no corresponde a un agente autonomo puro. Segun la
clasificacion de Anthropic, el sistema se entiende mejor como un **workflow**
implementado con LangGraph, que combina:

- **Augmented LLM**
- **Workflow: Prompt Chaining**
- **Workflow: Routing**

En resumen:

> Es un workflow con LangGraph que combina Prompt Chaining y Routing, construido
> sobre un Augmented LLM con tools, memoria persistente, RAG y guardrails.

No es un agente autonomo puro porque el LLM no controla libremente todo el
proceso. El flujo principal esta definido por nodos y rutas de codigo. El LLM
participa en puntos concretos, principalmente extraccion y decision, pero la
ejecucion real pasa por validaciones, tools y guardrails deterministas.

## 1. Augmented LLM

En Anthropic, un **Augmented LLM** es un LLM aumentado con capacidades externas,
como tools, retrieval, memoria o reglas de ejecucion.

En este proyecto, esto aparece cuando se usa `create_agent` con:

- Modelo LLM configurable.
- System prompt.
- Tools.
- Middleware de guardrails.
- Estado de la cotizacion.

### Extractor agentico

Archivo:

```text
app/extractor_agentico.py
```

Parte relevante:

```python
agente = create_agent(
    model=config.modelo_langchain,
    tools=[registrar_campos_extraidos],
    system_prompt=PROMPT_SISTEMA_EXTRACTOR,
    middleware=obtener_middleware_langchain_guardrails(),
)
```

Este componente usa el LLM para interpretar lenguaje natural y convertirlo en
datos estructurados. Sin embargo, el workflow no acepta cualquier texto libre del
LLM: consume la salida de una tool estructurada y luego la normaliza.

### Decisor agentico

Archivo:

```text
app/decisor_agentico.py
```

Parte relevante:

```python
agente = create_agent(
    model=config.modelo_langchain,
    tools=[elegir_accion_workflow],
    system_prompt=PROMPT_SISTEMA_DECISOR,
    middleware=obtener_middleware_langchain_guardrails(),
)
```

Este componente usa el LLM para decidir una accion de alto nivel, por ejemplo:

```text
pedir_campos_faltantes
validar_y_recomendar
generar_cotizacion
retomar_previa
nueva_cotizacion
responder_politica
```

Luego esa decision pasa por validaciones posteriores para evitar que el LLM salte
reglas del negocio.

### Otras capacidades aumentadas

El agente tambien esta aumentado con:

- RAG para responder consultas de politicas.
- Memoria persistente para retomar cotizaciones.
- Tools de negocio para cobertura, calendario, catalogo, disponibilidad, precios
  y cotizacion.
- Guardrails de entrada, decision, middleware y salida.

Por eso el LLM no trabaja solo: esta conectado a herramientas y validaciones.

## 2. Workflow: Prompt Chaining

En Anthropic, **Prompt Chaining** ocurre cuando una tarea se divide en pasos
secuenciales. La salida de un paso alimenta al siguiente.

Este patron aparece claramente en el grafo LangGraph.

Archivo:

```text
app/grafo_cotizador.py
```

Ruta principal:

```text
validar_entrada
-> extraer_y_enrutar_intencion
-> gestionar_memoria_persistente
-> decidir_accion_agentica
-> ejecutar_tools_negocio
-> evaluar_salida_guardrail
```

Cada nodo tiene una responsabilidad especifica:

- `validar_entrada`: aplica guardrail de entrada.
- `extraer_y_enrutar_intencion`: interpreta el mensaje y actualiza el estado.
- `gestionar_memoria_persistente`: revisa si debe recuperar una cotizacion previa.
- `decidir_accion_agentica`: usa el decisor agentico para elegir la accion.
- `ejecutar_tools_negocio`: ejecuta las validaciones y tools de negocio.
- `evaluar_salida_guardrail`: valida la respuesta final antes de mostrarla.

Parte relevante del codigo:

```python
grafo.add_node("validar_entrada", validar_entrada)
grafo.add_node("extraer_y_enrutar_intencion", extraer_y_enrutar_intencion)
grafo.add_node("gestionar_memoria_persistente", gestionar_memoria_persistente)
grafo.add_node("decidir_accion_agentica", decidir_accion_agentica)
grafo.add_node("ejecutar_tools_negocio", ejecutar_tools_negocio)
grafo.add_node("evaluar_salida_guardrail", evaluar_salida_guardrail)
```

Y la ejecucion inicia con:

```python
resultado = obtener_grafo_cotizador().invoke(...)
```

Este es el patron mas fuerte del proyecto: el agente no improvisa todo el flujo,
sino que avanza por pasos controlados.

## 3. Workflow: Routing

En Anthropic, **Routing** ocurre cuando el sistema clasifica una entrada y decide
que ruta especializada debe ejecutar.

En el proyecto existe routing en varios niveles.

### Routing en LangGraph

Archivo:

```text
app/grafo_cotizador.py
```

Parte relevante:

```python
grafo.add_conditional_edges(
    "validar_entrada",
    ruta_si_finalizado,
    {"finalizar": "evaluar_salida_guardrail", "continuar": "extraer_y_enrutar_intencion"},
)
```

Esto permite que el grafo decida si continua al siguiente nodo o si pasa directo
a la salida segura.

Tambien ocurre despues de memoria:

```python
grafo.add_conditional_edges(
    "gestionar_memoria_persistente",
    ruta_si_finalizado,
    {"finalizar": "evaluar_salida_guardrail", "continuar": "decidir_accion_agentica"},
)
```

Si memoria resuelve el turno, el flujo no sigue al decisor. Si no lo resuelve,
continua.

### Routing por intencion de negocio

Archivo:

```text
app/flujo.py
```

Metodo:

```python
ejecutar_decision_negocio(...)
```

Ejemplos:

```python
if estado.intencion == "retomar_previa":
    ...

if estado.intencion == "saludo":
    ...

if estado.intencion == "consulta_general":
    ...

if estado.intencion == "consulta_precio":
    ...

if estado.intencion == "derivacion_humana":
    ...
```

Esto enruta la conversacion segun la intencion detectada y validada.

### Routing desde el decisor agentico

Archivo:

```text
app/decisor_agentico.py
```

Tool:

```python
def elegir_accion_workflow(...)
```

Esta tool limita las acciones que el LLM puede elegir. Por ejemplo:

```python
if solicito_emitir_propuesta:
    if puede_generar_cotizacion:
        return "generar_cotizacion"
    return "validar_y_recomendar" if puede_validar_y_recomendar else "pedir_campos_faltantes"

if solicito_empezar_otro_pedido:
    return "nueva_cotizacion"

if solicito_recuperar_memoria:
    return "retomar_previa"
```

Aqui el LLM participa en el routing, pero no ejecuta directamente las tools. El
workflow valida y ejecuta la decision despues.

## Por que no es un agente autonomo puro

Segun Anthropic, un agente autonomo permite que el LLM dirija dinamicamente su
proceso y uso de herramientas durante varios pasos.

Este proyecto no funciona asi. En este sistema:

- El flujo principal esta definido en LangGraph.
- Los nodos tienen orden fijo.
- Las rutas condicionales estan definidas en codigo.
- El LLM no puede llamar cualquier herramienta libremente.
- Las acciones del LLM pasan por tools estructuradas y guardrails.
- La ejecucion real de negocio esta controlada por codigo.

Por eso se clasifica mejor como **workflow** y no como agente autonomo.

## Frase recomendada para exposicion

> Nuestro agente cotizador se basa en un workflow con LangGraph que combina los
> patrones Prompt Chaining y Routing descritos por Anthropic. Sobre ese workflow
> usamos un Augmented LLM, porque el modelo esta conectado a tools, memoria,
> RAG y guardrails. No es un agente autonomo puro, ya que el LLM no controla
> libremente el proceso: interpreta, extrae y decide acciones de alto nivel,
> pero el flujo, las validaciones y la ejecucion de negocio estan controlados
> por nodos y reglas deterministicas.
