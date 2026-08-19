# Agentic Profile Card + Technical Agent Specification

## Agente de recomendaciones y atención para ocasiones de consumo

**Versión:** 3.0  
**Estado:** Ready for Implementation / Codex  
**Arquitectura:** Monoagente híbrido con workflow agéntico controlado  
**Patrón principal:** Model-Based Reflex + Goal-Based + Simple Reflex + Utility-Based  
**Runtime recomendado:** Python + LangGraph/LangChain  
**Canal inicial:** WhatsApp / Chat API  
**Nivel de autonomía:** Semiautónomo y constreñido  
**Criticidad:** Media – controlada  
**Objetivo de esta versión:** entregar una especificación suficientemente precisa para implementar un MVP funcional sin redefinir la arquitectura durante el desarrollo.

---

# 1. Propósito del agente

Construir un agente conversacional que ayude a un consumidor a encontrar una alternativa adecuada para una reunión, celebración o evento, utilizando información del usuario, reglas del negocio, disponibilidad, cobertura, preferencias y criterios de utilidad.

El agente debe poder:

1. Comprender la intención del usuario.
2. Extraer y mantener contexto durante la conversación.
3. Detectar datos faltantes.
4. Consultar información mediante herramientas.
5. Aplicar reglas determinísticas.
6. Filtrar alternativas inválidas.
7. Comparar alternativas válidas.
8. Recomendar una alternativa explicable.
9. Preparar una cotización cuando corresponda.
10. Derivar el caso a un asesor cuando exceda su autonomía.
11. Persistir preferencias únicamente con consentimiento explícito.
12. Registrar trazabilidad de decisiones y llamadas a herramientas.

---

# 2. Principio arquitectónico

El sistema NO debe ser implementado como un chatbot que responde libremente usando únicamente un LLM.

Debe implementarse como:

```text
USUARIO
   ↓
CANAL / API
   ↓
AGENT HARNESS
   ↓
LLM + STATE + POLICIES
   ↓
DECISIÓN
   ↓
TOOLS / RAG / WORKFLOWS
   ↓
VALIDACIÓN
   ↓
RESPUESTA / COTIZACIÓN / DERIVACIÓN
```

El LLM se utiliza para comprensión, extracción, razonamiento controlado y generación de lenguaje.

Las decisiones críticas deben depender de:

- reglas;
- contratos de estado;
- fuentes estructuradas;
- herramientas;
- validadores;
- guardrails.

---

# 3. Tipo de agente

## 3.1 Model-Based Reflex Agent — núcleo principal

Responsabilidad:

- mantener el estado interno;
- combinar información nueva con información previa;
- evitar preguntas repetidas;
- conocer la etapa actual;
- determinar qué información sigue siendo válida.

Ejemplo:

```json
{
  "occasion": "birthday",
  "attendees": 20,
  "date": null,
  "location": "Miraflores",
  "conversation_state": "collecting_data"
}
```

No debe reaccionar únicamente al último mensaje.

---

## 3.2 Goal-Based Agent — orientación a objetivos

Objetivo principal:

```text
llevar la conversación desde una necesidad
hasta una recomendación, cotización o derivación válida.
```

Objetivos intermedios:

```text
IDENTIFY_INTENT
COLLECT_REQUIRED_DATA
VALIDATE_CONDITIONS
RETRIEVE_OPTIONS
FILTER_OPTIONS
RANK_OPTIONS
PRESENT_RECOMMENDATION
PREPARE_QUOTE
ESCALATE
FINISH
```

El agente debe seleccionar siempre el siguiente objetivo explícitamente.

---

## 3.3 Simple Reflex Agent — reglas determinísticas

No utilizar el LLM para decisiones que pueden resolverse con reglas exactas.

Ejemplos:

```text
IF user_requests_human = true
THEN ESCALATE
```

```text
IF required_fields_missing != []
THEN ASK_MISSING_DATA
```

```text
IF coverage = false
THEN DO_NOT_QUOTE
```

```text
IF discount_requested = true
THEN ESCALATE
```

```text
IF availability = false
THEN FILTER_OPTION
```

---

## 3.4 Utility-Based Agent — ranking

Solo debe ejecutarse después de aplicar filtros obligatorios.

Pesos iniciales:

```yaml
occasion_compatibility: 0.30
capacity_fit: 0.20
availability: 0.20
user_preferences: 0.15
budget_fit: 0.10
operational_simplicity: 0.05
```

Fórmula:

```text
utility_score =
occasion_compatibility * 0.30 +
capacity_fit * 0.20 +
availability * 0.20 +
user_preferences * 0.15 +
budget_fit * 0.10 +
operational_simplicity * 0.05
```

Cada criterio debe tomar valores de `0..100`.

El LLM NO puede alterar:

- pesos;
- puntuaciones calculadas;
- opciones descartadas.

---

# 4. Communication Layer

## 4.1 Conversacional

Canal inicial:

```text
WhatsApp / Web Chat
```

Responsabilidades:

- recibir mensaje;
- asociar `session_id`;
- identificar `user_id`;
- enviar mensaje al Agent Harness;
- devolver respuesta final.

## 4.2 No conversacional

Procesos autorizados:

- recordatorios con consentimiento;
- seguimiento de cotizaciones;
- consulta de fechas importantes;
- recuperación de preferencias;
- tareas programadas de seguimiento.

Todo proceso saliente debe verificar consentimiento.

---

# 5. Agent Harness

El agente debe ejecutarse dentro de un Agent Harness con los siguientes componentes:

```text
Agent Harness
├── System Prompt
├── State Manager
├── Prompt Router
├── Tool Registry
├── RAG Retriever
├── Memory Manager
├── Policy Engine
├── Structured Output Validator
├── Retry / Error Manager
├── Security Layer
├── Logging & Tracing
└── Evaluation Hooks
```

## 5.1 Responsabilidades

### System Prompt

Define:

- rol;
- alcance;
- prohibiciones;
- prioridad de fuentes;
- criterios de derivación;
- política de memoria;
- reglas de uso de tools.

### State Manager

Responsable de:

- crear estado;
- actualizar estado;
- validar transición;
- persistir short-term memory.

### Tool Registry

Contiene únicamente herramientas autorizadas.

El LLM no puede ejecutar funciones fuera del registro.

### Policy Engine

Ejecuta reglas determinísticas antes y después del LLM.

### Structured Output Validator

Todo resultado interno relevante del LLM debe cumplir un esquema JSON.

### Retry / Error Manager

Controla:

- retries;
- timeout;
- fallback;
- escalamiento.

### Logging & Tracing

Registra:

- decisiones;
- tools;
- errores;
- latencia;
- outcome.

---

# 6. Prompting Strategy

No utilizar una única técnica de prompting para todo.

## 6.1 Técnicas seleccionadas

| Tarea | Técnica |
|---|---|
| Clasificar intención | Few-Shot |
| Extraer entidades | Few-Shot + Structured Output |
| Detectar ambigüedad | Zero-Shot controlado |
| Decidir siguiente acción | ReAct controlado |
| Consultar conocimiento estable | RAG |
| Uso de herramientas | ReAct / Tool Calling |
| Comparar alternativas | Cálculo determinístico, no LLM |
| Explicar recomendación | Zero-Shot grounded |
| Evaluar respuestas offline | LLM-as-a-Judge + tests determinísticos |

## 6.2 Técnicas NO requeridas en V1

No usar por defecto:

- Tree of Thoughts;
- Self-Consistency;
- ART autónomo;
- aprendizaje autónomo.

Solo incorporar si una evaluación futura demuestra necesidad.

---

# 7. Patrón ReAct controlado

El razonamiento no debe exponerse al usuario.

Ciclo lógico:

```text
OBSERVE
↓
UPDATE STATE
↓
IDENTIFY GOAL
↓
DECIDE ACTION
↓
CALL TOOL OR ASK USER
↓
OBSERVE RESULT
↓
VALIDATE
↓
CONTINUE OR RESPOND
```

Ejemplo conceptual:

```text
User:
"Necesito algo para 20 personas este sábado en Miraflores."

Internal state:
attendees = 20
date = resolved_date
location = Miraflores

Action:
validate_coverage

Observation:
covered = true

Action:
check_availability

Observation:
3 valid options

Action:
rank_options

Final:
present recommendation
```

Máximo recomendado de iteraciones automáticas por turno:

```yaml
max_agent_steps: 8
```

Si se supera:

```text
ESCALATE_OR_SAFE_STOP
```

---

# 8. State Contract

Implementar un único estado tipado.

```python
class AgentState(TypedDict, total=False):
    session_id: str
    user_id: str | None

    intent: str | None
    confidence: float | None

    occasion: str | None
    attendees: int | None
    event_date: str | None
    location: str | None
    budget_min: float | None
    budget_max: float | None

    current_preferences: list[str]
    persistent_preferences: list[str]

    missing_fields: list[str]

    coverage_status: str | None
    feasibility_status: str | None

    candidate_options: list[dict]
    valid_options: list[dict]
    rejected_options: list[dict]

    recommended_option: dict | None
    quote: dict | None

    conversation_state: str
    current_goal: str
    next_action: str | None

    requires_human: bool
    escalation_reason: str | None

    memory_consent: bool | None

    tool_history: list[dict]
    errors: list[dict]
```

---

# 9. Conversation State Machine

Estados permitidos:

```text
START
IDENTIFYING_INTENT
COLLECTING_DATA
VALIDATING_CONDITIONS
RETRIEVING_OPTIONS
FILTERING_OPTIONS
RANKING_OPTIONS
PRESENTING_RECOMMENDATION
PREPARING_QUOTE
WAITING_CONFIRMATION
ESCALATING
COMPLETED
ERROR_SAFE_STOP
```

Transiciones:

```text
START
→ IDENTIFYING_INTENT

IDENTIFYING_INTENT
→ COLLECTING_DATA
→ ESCALATING

COLLECTING_DATA
→ VALIDATING_CONDITIONS

VALIDATING_CONDITIONS
→ COLLECTING_DATA
→ RETRIEVING_OPTIONS
→ ESCALATING

RETRIEVING_OPTIONS
→ FILTERING_OPTIONS

FILTERING_OPTIONS
→ RANKING_OPTIONS
→ ESCALATING

RANKING_OPTIONS
→ PRESENTING_RECOMMENDATION

PRESENTING_RECOMMENDATION
→ PREPARING_QUOTE
→ COMPLETED

PREPARING_QUOTE
→ WAITING_CONFIRMATION
→ ESCALATING

WAITING_CONFIRMATION
→ COMPLETED
→ ESCALATING
```

No permitir transiciones arbitrarias.

---

# 10. Required Data Policy

Campos mínimos para recomendación:

```yaml
occasion: required
attendees: required
event_date: required
location: required
```

Campos opcionales:

```yaml
budget: optional
preferences: optional
```

Campos mínimos para cotización:

```yaml
occasion: required
attendees: required
event_date: required
location: required
selected_option: required
coverage_validated: required
availability_validated: required
```

Regla:

```text
ASK ONLY FOR MISSING REQUIRED FIELDS.
```

No volver a solicitar datos ya válidos.

---

# 11. Structured LLM Outputs

## 11.1 Intent + Entity Extraction

El LLM debe devolver únicamente:

```json
{
  "intent": "request_recommendation",
  "confidence": 0.94,
  "entities": {
    "occasion": "birthday",
    "attendees": 20,
    "event_date": null,
    "location": "Miraflores",
    "budget_min": null,
    "budget_max": null,
    "preferences": ["practical"]
  },
  "ambiguities": [],
  "human_requested": false
}
```

Valores permitidos de `intent`:

```text
request_information
request_recommendation
request_quote
modify_request
request_human
complaint
memory_request
unknown
```

Si:

```text
confidence < 0.70
```

entonces:

```text
ASK_CLARIFICATION
```

No asumir intención.

---

# 12. Knowledge Architecture

## 12.1 RAG

Utilizar RAG exclusivamente para información relativamente estable:

- descripción de categorías;
- características;
- FAQ;
- políticas generales;
- casos de uso;
- mensajes aprobados;
- restricciones documentales.

Pipeline:

```text
Query
↓
Query normalization
↓
Retriever
↓
Top-K
↓
Metadata filter
↓
Context
↓
LLM grounded answer
```

Configuración inicial:

```yaml
top_k: 5
minimum_similarity: configurable
citations_internal: true
```

## 12.2 Ground Truth

Información dinámica debe consultarse siempre mediante fuente estructurada:

```text
precio
stock
disponibilidad
cobertura
capacidad
reglas comerciales
calendario
restricciones operativas
```

Prioridad:

```text
API / DB / SYSTEM OF RECORD
>
RAG
>
LLM prior knowledge
```

El conocimiento interno del LLM nunca es fuente de verdad comercial.

---

# 13. Tool Contracts

Todas las herramientas deben:

- usar inputs tipados;
- devolver JSON;
- manejar timeout;
- declarar errores;
- ser idempotentes cuando sea posible;
- registrar trace.

---

## 13.1 consultar_catalogo

Input:

```json
{
  "occasion": "birthday",
  "attendees": 20
}
```

Output:

```json
{
  "success": true,
  "options": []
}
```

Errores:

```text
CATALOG_UNAVAILABLE
INVALID_INPUT
```

---

## 13.2 consultar_alternativa

Input:

```json
{
  "option_id": "OPT-001"
}
```

Output:

```json
{
  "success": true,
  "option": {}
}
```

---

## 13.3 validar_cobertura

Input:

```json
{
  "location": "Miraflores"
}
```

Output:

```json
{
  "success": true,
  "covered": true,
  "zone_id": "ZONE-001",
  "restrictions": []
}
```

Failure:

```json
{
  "success": false,
  "error_code": "LOCATION_NOT_FOUND"
}
```

---

## 13.4 validar_factibilidad

Input:

```json
{
  "event_date": "2026-08-15",
  "attendees": 20,
  "location": "Miraflores"
}
```

Output:

```json
{
  "success": true,
  "feasible": true,
  "restrictions": []
}
```

---

## 13.5 consultar_disponibilidad

Input:

```json
{
  "option_ids": ["OPT-001", "OPT-002"],
  "event_date": "2026-08-15"
}
```

Output:

```json
{
  "success": true,
  "availability": [
    {
      "option_id": "OPT-001",
      "available": true
    }
  ]
}
```

---

## 13.6 evaluar_alternativas

Debe ser código determinístico.

Input:

```json
{
  "options": [],
  "user_context": {}
}
```

Output:

```json
{
  "success": true,
  "ranked_options": [
    {
      "option_id": "OPT-001",
      "utility_score": 88.4,
      "score_breakdown": {
        "occasion_compatibility": 95,
        "capacity_fit": 100,
        "availability": 100,
        "user_preferences": 70,
        "budget_fit": 60,
        "operational_simplicity": 80
      }
    }
  ]
}
```

---

## 13.7 calcular_cotizacion

Input:

```json
{
  "option_id": "OPT-001",
  "attendees": 20,
  "event_date": "2026-08-15",
  "location": "Miraflores"
}
```

Output:

```json
{
  "success": true,
  "quote_id": "QUOTE-001",
  "currency": "PEN",
  "subtotal": 0,
  "tax": 0,
  "total": 0,
  "valid_until": "2026-08-10",
  "conditions": []
}
```

El LLM no calcula precios.

---

## 13.8 consultar_preferencias

Input:

```json
{
  "user_id": "USER-001"
}
```

Output:

```json
{
  "success": true,
  "preferences": []
}
```

---

## 13.9 guardar_preferencia

Precondición obligatoria:

```text
memory_consent = true
```

Input:

```json
{
  "user_id": "USER-001",
  "preference": {
    "type": "style",
    "value": "practical"
  },
  "consent_reference": "SESSION-001"
}
```

---

## 13.10 derivar_a_asesor

Input:

```json
{
  "user_id": "USER-001",
  "session_id": "SESSION-001",
  "reason": "discount_request",
  "summary": {},
  "priority": "normal"
}
```

Output:

```json
{
  "success": true,
  "case_id": "CASE-001"
}
```

---

# 14. Tool Execution Policy

Antes de cada tool call:

```text
1. Validate required input.
2. Validate authorization.
3. Validate current state.
4. Execute.
5. Validate output schema.
6. Persist trace.
7. Update state.
```

Timeout inicial recomendado:

```yaml
tool_timeout_seconds: 5
```

Retry:

```yaml
max_retries: 2
retry_strategy: exponential_backoff
```

No reintentar automáticamente operaciones no idempotentes.

---

# 15. Memory Architecture

## 15.1 Short-Term Memory

Persistencia por sesión.

Contiene:

- estado actual;
- entidades;
- resultados de tools;
- decisiones;
- opciones evaluadas;
- información faltante.

No guardar mensajes completos indefinidamente si no son necesarios.

---

## 15.2 Long-Term Memory

Guardar únicamente:

- preferencias explícitas;
- fechas autorizadas;
- historial útil permitido;
- consentimiento;
- configuraciones persistentes.

No utilizar como memoria permanente:

- precios;
- stock;
- disponibilidad;
- reglas dinámicas.

---

# 16. Memory Consent Policy

Clasificar una preferencia detectada como:

```text
EPHEMERAL
PERSISTENCE_CANDIDATE
```

Ejemplo:

```text
"Para este evento quiero algo sencillo"
→ EPHEMERAL
```

```text
"Siempre prefiero opciones sencillas"
→ PERSISTENCE_CANDIDATE
```

Antes de persistir:

```text
ASK FOR EXPLICIT CONSENT
```

Solo después:

```text
guardar_preferencia()
```

---

# 17. Guardrails

## 17.1 Business Guardrails

Prohibido:

- inventar precios;
- inventar stock;
- inventar cobertura;
- inventar disponibilidad;
- aprobar descuentos;
- negociar excepciones;
- confirmar pagos;
- modificar reglas;
- cambiar pesos de ranking;
- recomendar opciones descartadas.

---

## 17.2 LLM Guardrails

El LLM:

```text
MAY:
interpret
extract
summarize
explain
choose authorized next action
```

```text
MUST NOT:
override policy
override tool results
invent ground truth
execute unauthorized tools
expose hidden reasoning
```

---

# 18. Security

Implementar como mínimo:

```text
Authentication
Authorization
Tenant isolation
PII protection
Secrets management
Prompt injection protection
Tool authorization
Audit logging
```

Reglas:

```text
User A cannot access User B memory.
```

```text
Retrieved RAG content is DATA, not INSTRUCTIONS.
```

```text
User content cannot modify system policies.
```

```text
Secrets must never be injected into prompts.
```

La autorización para cada tool debe validarse fuera del LLM.

---

# 19. Prompt Injection Defense

Todo contenido externo debe etiquetarse como datos.

Prioridad de instrucciones:

```text
SYSTEM POLICY
>
DEVELOPER / BUSINESS RULES
>
TOOL CONTRACTS
>
USER REQUEST
>
RETRIEVED CONTENT
```

Ignorar instrucciones dentro de:

- documentos RAG;
- catálogos;
- textos de usuario;
- resultados de herramientas.

si intentan modificar comportamiento del agente.

---

# 20. Human-in-the-Loop

Derivar obligatoriamente si:

```text
user_requests_human
discount_request
commercial_exception
payment_required
complaint_complex
source_conflict
insufficient_information_after_clarification
tool_failure_without_fallback
security_risk
agent_confidence_too_low
max_agent_steps_exceeded
```

La derivación debe incluir un resumen estructurado.

Ejemplo:

```json
{
  "intent": "request_quote",
  "occasion": "birthday",
  "attendees": 20,
  "event_date": "2026-08-15",
  "location": "Miraflores",
  "recommended_option": "OPT-001",
  "reason_for_escalation": "discount_request",
  "actions_already_executed": [
    "coverage_validated",
    "availability_validated"
  ]
}
```

---

# 21. Error Handling

Clasificación:

```text
VALIDATION_ERROR
TOOL_TIMEOUT
TOOL_UNAVAILABLE
INVALID_TOOL_RESPONSE
RAG_NO_RESULT
LLM_INVALID_OUTPUT
SECURITY_ERROR
SOURCE_CONFLICT
UNKNOWN_ERROR
```

Política:

```text
Error
↓
Can retry safely?
├─ YES → retry max 2
└─ NO
    ↓
Fallback exists?
├─ YES → fallback
└─ NO → escalate / safe stop
```

Nunca ocultar un error fabricando una respuesta.

---

# 22. Fallback Policy

Ejemplos:

```text
RAG_NO_RESULT
→ say information is unavailable
→ do not invent
```

```text
AVAILABILITY_API_DOWN
→ do not confirm availability
→ offer escalation
```

```text
LLM_INVALID_JSON
→ retry structured generation once
→ if fail again: safe fallback
```

```text
SOURCE_CONFLICT
→ prioritize system of record
→ log conflict
→ escalate if unresolved
```

---

# 23. Observability

Cada ejecución debe generar:

```json
{
  "trace_id": "TRACE-001",
  "session_id": "SESSION-001",
  "timestamp": "...",
  "conversation_state": "VALIDATING_CONDITIONS",
  "current_goal": "VALIDATE_CONDITIONS",
  "action": "CALL_TOOL",
  "tool": "validar_cobertura",
  "latency_ms": 230,
  "status": "SUCCESS"
}
```

Registrar:

- trace_id;
- session_id;
- user_id anonimizado cuando aplique;
- estado;
- objetivo;
- tool;
- input sanitizado;
- output sanitizado;
- error;
- latencia;
- tokens;
- modelo;
- versión de prompt;
- versión del agente;
- resultado final.

No registrar secretos ni PII innecesaria.

---

# 24. Evaluation Strategy

## 24.1 Tests determinísticos

Crear dataset con casos esperados.

Evaluar:

```text
intent classification
entity extraction
missing-field detection
state transitions
tool selection
rule compliance
filtering
ranking
memory consent
escalation
```

---

## 24.2 LLM-as-a-Judge

Usar únicamente para criterios cualitativos:

- claridad;
- relevancia;
- naturalidad;
- explicación;
- consistencia con contexto.

Nunca usar como único evaluador de:

- precio;
- reglas;
- tools;
- seguridad;
- estados.

---

# 25. Métricas mínimas

```text
Intent Accuracy
Entity Extraction Accuracy
State Transition Accuracy
Tool Selection Accuracy
Tool Success Rate
Repeated Question Rate
Hallucination Rate
Ground Truth Accuracy
Valid Recommendation Rate
Escalation Accuracy
Memory Consent Compliance
Average Latency
Task Completion Rate
User Satisfaction
```

Objetivos iniciales sugeridos para MVP:

```yaml
hallucination_rate: "< 1%"
memory_consent_compliance: "100%"
invalid_option_recommendation: "0%"
business_rule_violation: "0%"
```

---

# 26. Arquitectura técnica propuesta

```text
WhatsApp / Web
      │
      ▼
API Gateway
      │
      ▼
Session / Identity Layer
      │
      ▼
Agent Service
      │
      ├── LangGraph State Machine
      │
      ├── LLM
      │
      ├── Policy Engine
      │
      ├── Structured Validators
      │
      └── Tool Registry
      │
      ├───────────────┐
      ▼               ▼
Vector DB          Operational APIs
RAG                Catalog
Policies           Coverage
FAQ                Availability
                   Pricing
                   CRM
                   Memory Store
      │
      ▼
Observability
Logs / Traces / Metrics
```

---

# 27. Implementación recomendada

Stack inicial:

```yaml
language: Python 3.11+
agent_orchestration: LangGraph
llm_framework: LangChain
api: FastAPI
validation: Pydantic
short_term_state: Redis or persistent checkpoint store
long_term_memory: PostgreSQL
vector_store: pgvector / Qdrant / equivalent
observability: structured logging + tracing
tests: pytest
```

No acoplar la lógica de negocio directamente al framework del LLM.

Crear capas:

```text
domain/
agent/
tools/
memory/
rag/
policies/
api/
observability/
tests/
```

---

# 28. Estructura de proyecto sugerida para Codex

```text
src/
├── api/
│   ├── main.py
│   └── schemas.py
│
├── agent/
│   ├── graph.py
│   ├── nodes.py
│   ├── state.py
│   ├── prompts.py
│   └── router.py
│
├── domain/
│   ├── models.py
│   ├── enums.py
│   └── scoring.py
│
├── tools/
│   ├── catalog.py
│   ├── coverage.py
│   ├── feasibility.py
│   ├── availability.py
│   ├── pricing.py
│   ├── memory.py
│   └── escalation.py
│
├── rag/
│   ├── retriever.py
│   └── knowledge_service.py
│
├── memory/
│   ├── short_term.py
│   └── long_term.py
│
├── policies/
│   ├── business_rules.py
│   ├── security.py
│   └── guardrails.py
│
├── observability/
│   ├── logging.py
│   └── tracing.py
│
└── tests/
    ├── test_intent.py
    ├── test_state.py
    ├── test_rules.py
    ├── test_tools.py
    ├── test_ranking.py
    ├── test_memory.py
    └── test_end_to_end.py
```

---

# 29. Graph inicial

Nodos:

```text
receive_message
↓
extract_intent_entities
↓
update_state
↓
evaluate_policies
↓
determine_next_goal
↓
route_action
```

Rutas:

```text
ASK_MISSING_DATA
CALL_COVERAGE
CALL_FEASIBILITY
CALL_CATALOG
CALL_AVAILABILITY
FILTER_OPTIONS
RANK_OPTIONS
GENERATE_RECOMMENDATION
PREPARE_QUOTE
ASK_MEMORY_CONSENT
SAVE_MEMORY
ESCALATE
FINISH
```

---

# 30. Pseudoflujo principal

```python
def handle_message(message, state):

    extracted = extract_intent_entities(message)

    state = update_state(state, extracted)

    policy_result = evaluate_policies(state)

    if policy_result.requires_human:
        return escalate(state)

    if state.missing_fields:
        return ask_missing_fields(state)

    if not state.coverage_status:
        state = call_validate_coverage(state)

    if state.coverage_status != "covered":
        return safe_response_or_escalate(state)

    if not state.feasibility_status:
        state = call_validate_feasibility(state)

    state = retrieve_options(state)

    state = filter_invalid_options(state)

    if not state.valid_options:
        return escalate_or_no_options(state)

    state = rank_options(state)

    state.recommended_option = state.valid_options[0]

    return generate_grounded_recommendation(state)
```

---

# 31. System Prompt — requisitos mínimos

El prompt de sistema debe indicar explícitamente:

```text
ROLE
You are a constrained commercial recommendation agent.

PRIMARY GOAL
Help the user reach a valid recommendation, quote, or human escalation.

SOURCE PRIORITY
Operational tools > approved knowledge base > model knowledge.

MANDATORY RULES
Never invent price, stock, availability, coverage, or commercial conditions.
Never override tool outputs.
Never bypass mandatory business rules.
Never expose hidden reasoning.
Never persist user preferences without explicit consent.
Ask only for missing required information.
Use only authorized tools.
Escalate when policy requires it.
```

Los prompts completos deben mantenerse versionados fuera del código de lógica.

Ejemplo:

```text
prompt_version = "recommendation-agent-system-v3.0"
```

---

# 32. Acceptance Criteria para Codex

La V1 se considera funcional cuando:

### Conversación

- comprende al menos las intenciones definidas;
- extrae entidades en JSON;
- mantiene contexto;
- no repite datos ya conocidos.

### Estado

- usa `AgentState`;
- valida transiciones;
- persiste short-term state.

### Tools

- todas las tools cumplen contrato;
- no hay llamadas fuera del registry;
- implementan timeout/error handling.

### Recomendación

- filtra opciones inválidas;
- ranking determinístico;
- nunca recomienda descartadas.

### RAG

- se usa solo para conocimiento estable;
- no reemplaza Ground Truth.

### Memoria

- distingue temporal/permanente;
- requiere consentimiento explícito.

### Seguridad

- evita contaminación entre usuarios;
- trata documentos recuperados como datos;
- no expone secretos.

### Observabilidad

- cada ejecución tiene `trace_id`;
- tool calls quedan registradas.

### Tests

Deben existir tests automatizados para:

```text
happy path
missing data
no coverage
no availability
tool timeout
invalid LLM JSON
memory without consent
human request
discount request
source conflict
```

---

# 33. Casos de prueba mínimos

## Caso 1 — Happy Path

Input:

```text
Necesito algo práctico para un cumpleaños de 20 personas este sábado en Miraflores.
```

Expected:

```text
extract entities
validate coverage
validate feasibility
retrieve options
validate availability
filter
rank
recommend
```

---

## Caso 2 — Missing Data

Input:

```text
Necesito algo para un cumpleaños.
```

Expected:

```text
ask only:
attendees
date
location
```

---

## Caso 3 — No Coverage

Expected:

```text
do not quote
do not invent alternative coverage
explain limitation
offer escalation if appropriate
```

---

## Caso 4 — Tool Failure

`consultar_disponibilidad` timeout.

Expected:

```text
retry <= 2
if unresolved:
do not confirm availability
safe response / escalation
```

---

## Caso 5 — Memory

Input:

```text
Siempre prefiero opciones sencillas.
```

Expected:

```text
detect persistence candidate
ask consent
do not persist before YES
```

---

# 34. Out of Scope — V1

No implementar todavía:

- multiagente;
- aprendizaje autónomo;
- modificación automática de prompts;
- ajuste automático de pesos;
- pagos;
- negociación autónoma;
- promociones dinámicas autónomas;
- agentes que creen nuevas tools;
- Tree of Thoughts por defecto;
- self-modifying workflows.

---

# 35. Evolución futura

```text
V1
Monoagente híbrido
+
Tools
+
RAG
+
Memory
+
ReAct controlado

↓

V2
Agentic Workflow avanzado
+
event-driven processes
+
advanced evaluation

↓

V3
Multi-Agent
+
specialized agents
+
orchestrator

↓

V4
Learning from logs
+
human-supervised optimization
```

No avanzar a multiagente hasta demostrar que la separación produce un beneficio medible.

---

# 36. Definition of Done

El agente se considera listo para MVP cuando:

```text
[ ] State machine implementada
[ ] Structured outputs validados
[ ] Tool registry implementado
[ ] Tool contracts implementados
[ ] RAG separado de Ground Truth
[ ] ReAct controlado implementado
[ ] Guardrails implementados
[ ] Memory consent implementado
[ ] Human escalation implementado
[ ] Retry/error handling implementado
[ ] Logging/tracing implementado
[ ] Security baseline implementado
[ ] Unit tests implementados
[ ] End-to-end tests implementados
[ ] README de ejecución creado
[ ] .env.example creado
[ ] Dockerfile creado
```

---

# 37. Instrucción directa para Codex

Implementar una primera versión funcional siguiendo esta especificación.

Prioridades de desarrollo:

```text
1. Models + State
2. State Machine / LangGraph
3. Structured Extraction
4. Policy Engine
5. Tool Registry + Mock Tools
6. Recommendation Workflow
7. Utility Ranking
8. Memory
9. RAG
10. Error Handling
11. Security
12. Observability
13. Tests
```

Para servicios externos aún no disponibles:

```text
crear interfaces + mocks
```

No inventar integraciones reales.

Usar configuración desacoplada mediante variables de entorno.

Entregar:

```text
source code
tests
README
.env.example
Dockerfile
sample conversations
architecture notes
```

El código debe permitir reemplazar mocks por APIs reales sin modificar la lógica central del agente.

---

# 38. Resumen ejecutivo

```text
TIPO
Monoagente híbrido

CORE
Model-Based Reflex

GOALS
Goal-Based

RULES
Simple Reflex

RANKING
Utility-Based

REASONING PATTERN
ReAct controlado

KNOWLEDGE
RAG para información estable

GROUND TRUTH
APIs / DB

MEMORY
Short-Term + Long-Term con consentimiento

HARNESS
State + Tools + Policies + Validation + Security + Observability

AUTONOMY
Semiautónomo constreñido

ESCALATION
Human-in-the-loop

IMPLEMENTATION
Python + LangGraph + LangChain + FastAPI + Pydantic
```

---

## Principio final

El LLM no es el agente completo.

```text
AGENT =
LLM
+ STATE
+ GOALS
+ TOOLS
+ MEMORY
+ RAG
+ POLICIES
+ GUARDRAILS
+ OBSERVABILITY
+ EVALUATION
```

La implementación debe priorizar comportamiento verificable, trazabilidad y control por encima de autonomía innecesaria.
