# Spec POC - Workflow agentico para cotizaciones de eventos

## 0. Objetivo de este documento

Este documento define la primera POC desarrollable del **Workflow agentico para cotizaciones de eventos**.

La POC debe demostrar el funcionamiento completo de una atencion conversacional para recomendar y cotizar alternativas de eventos, usando datos mockeados y sin depender todavia de infraestructura real de datos.

Este spec reemplaza el enfoque anterior demasiado orientado a arquitectura productiva. Para esta primera version, los siguientes componentes deben implementarse como mock:

- RAG;
- base de datos transaccional;
- base NoSQL;
- base vectorial en PostgreSQL/pgvector;
- disponibilidad;
- catalogo;
- precios;
- memoria persistente;
- derivacion WhatsApp real.

La POC debe ser simple, verificable y suficiente para probar la logica principal del sistema.

---

## 1. Clasificacion correcta de la solucion

### 1.1 Tipo de solucion

La solucion debe definirse como:

```text
Workflow agentico conversacional para recomendacion y cotizacion de eventos.
```

Nombre completo recomendado:

```text
Workflow agentico transaccional asistido por LLM, con herramientas mockeadas, memoria de sesion, RAG simulado y derivacion humana simulada.
```

### 1.2 Es agente o workflow?

Para esta POC, **no debe presentarse como un agente autonomo puro**.

Debe presentarse como un **workflow agentico**:

- es **workflow** porque el proceso de negocio tiene etapas, validaciones y gates definidos;
- es **agentico** porque usa capacidades asociadas a agentes: LLM para interpretar intencion, estado de conversacion, uso de tools, memoria de sesion, recuperacion de conocimiento simulada y decision acotada sobre la siguiente accion conversacional;
- no es multiagente;
- no hay agentes especializados separados;
- los "nodos" no son agentes, son pasos funcionales del flujo.

Definicion para usar en la documentacion:

```text
La POC se define como un workflow agentico conversacional. Su estructura principal es un flujo controlado de negocio para recomendacion y cotizacion, pero incorpora capacidades agenticas acotadas: interpretacion de intencion con LLM, manejo de estado, uso de herramientas, memoria de sesion, recuperacion de conocimiento simulada y derivacion humana solicitada por el usuario.
```

### 1.3 Por que se usan nodos si no es multiagente?

Los nodos representan etapas del flujo, no agentes.

Ejemplo:

```text
Nodo extraer_intencion       -> usa LLM
Nodo validar_datos_minimos   -> usa reglas
Nodo buscar_catalogo_mock    -> usa datos mock
Nodo validar_cobertura_mock  -> usa datos mock
Nodo cotizar_mock            -> usa reglas y precios mock
Nodo responder               -> usa LLM o plantilla
```

Esto equivale a un proceso orquestado. Tener varios nodos no significa tener varios agentes.

---

## 2. Necesidad del negocio

Basado en el Profile Card v3.2, la necesidad es:

Una persona quiere organizar una reunion, celebracion o evento y necesita encontrar una alternativa adecuada considerando:

- tipo de evento;
- cantidad de asistentes;
- fecha;
- ubicacion;
- presupuesto;
- preferencias;
- cobertura;
- disponibilidad;
- reglas comerciales.

El sistema debe guiar la conversacion, pedir solo los datos faltantes, recomendar alternativas viables y generar una cotizacion clara con precio, impuestos, total, vigencia y condiciones.

El sistema no reemplaza al asesor comercial. Si el usuario pide atencion humana, descuento, negociacion, pago o excepcion, debe ofrecer derivacion por WhatsApp.

---

## 3. Alcance de la POC

### 3.1 Incluido

La POC debe incluir:

- frontend en Streamlit;
- backend o capa de servicios en Python;
- workflow agentico con estado;
- uso de LLM para intencion, extraccion y redaccion;
- tools mockeadas para catalogo, cobertura, disponibilidad, precios y cotizacion;
- RAG simulado con documentos mock;
- memoria de sesion en memoria local;
- datos mock en archivos JSON o estructuras Python;
- imagen referencial del evento o paquete en Streamlit;
- derivacion humana simulada por WhatsApp;
- logs simples para trazabilidad.

### 3.2 No incluido

No implementar en esta POC:

- PostgreSQL real;
- pgvector real;
- NoSQL real;
- Redis real;
- Kubernetes/k3s real;
- WhatsApp real;
- pagos;
- CRM real;
- autenticacion productiva;
- multiagentes;
- MCP;
- aprendizaje automatico desde logs;
- generacion automatica de imagenes en runtime.

### 3.3 Supuesto tecnico

Los datos mock deben simular la respuesta de sistemas reales. La interfaz de cada tool debe disenarse como si luego pudiera conectarse a BD, API o servicio real sin cambiar el workflow.

---

## 4. Arquitectura POC

```text
Usuario
  -> Streamlit UI
    -> Workflow agentico
      -> Estado de sesion
      -> LLM para intencion/extraccion/respuesta
      -> Tools mockeadas
        -> catalogo_mock
        -> cobertura_mock
        -> disponibilidad_mock
        -> precios_mock
        -> cotizacion_mock
        -> rag_mock
        -> derivacion_whatsapp_mock
      -> Respuesta final
```

### 4.1 Componentes

| Componente | Implementacion POC | Futuro productivo |
|---|---|---|
| UI | Streamlit | Streamlit, Web Chat o WhatsApp |
| Orquestacion | Python + LangGraph opcional | LangGraph persistente |
| LLM | OpenAI API o modelo configurado | OpenAI/LLM provider |
| Catalogo | JSON mock | BD/API catalogo |
| Cobertura | JSON mock | API operacion/cobertura |
| Disponibilidad | JSON mock | BD/API reservas |
| Precios | JSON mock | motor oficial de precios |
| Cotizaciones | objeto en memoria/JSON | PostgreSQL transaccional |
| RAG | busqueda por keywords en textos mock | pgvector/PostgreSQL |
| NoSQL | no implementado, mock conceptual | historiales/documentos |
| Memoria | `st.session_state` o dict Python | Redis/Postgres |
| WhatsApp | link simulado | API WhatsApp Business |

---

## 5. Flujo funcional

### 5.1 Flujo principal

```text
1. Usuario escribe necesidad.
2. Sistema interpreta intencion y extrae datos.
3. Sistema actualiza estado de solicitud.
4. Sistema identifica datos faltantes.
5. Si faltan datos, pregunta solo lo necesario.
6. Si hay datos minimos, consulta catalogo mock.
7. Valida cobertura mock.
8. Valida disponibilidad mock.
9. Dimensiona cantidades mock.
10. Compara alternativas.
11. Recomienda una o mas opciones.
12. Si el usuario pide precio, genera cotizacion mock.
13. Si el usuario pide asesor, descuento, pago o excepcion, ofrece derivacion WhatsApp.
14. Si el usuario confirma derivacion, genera resumen y link mock de WhatsApp.
```

### 5.2 Datos minimos

No recomendar hasta obtener:

- `event_type`;
- `attendees`;
- `event_date`;
- `district`.

No cotizar hasta obtener:

- recomendacion seleccionada o alternativa recomendada;
- cobertura valida;
- disponibilidad valida;
- dimensionamiento calculado.

---

## 6. Estado de sesion

Implementar un objeto de estado. Puede ser `TypedDict`, `dataclass` o `pydantic.BaseModel`.

```python
class QuoteState(BaseModel):
    session_id: str
    stage: str = "inicio"
    intent: str | None = None

    event_type: str | None = None
    attendees: int | None = None
    event_date: str | None = None
    district: str | None = None
    budget: float | None = None
    preferences: list[str] = []

    missing_fields: list[str] = []
    catalog_options: list[dict] = []
    valid_options: list[dict] = []
    discarded_options: list[dict] = []
    recommended_option: dict | None = None
    dimensioning: dict | None = None
    quote: dict | None = None

    coverage_ok: bool | None = None
    availability_ok: bool | None = None
    policy_ok: bool | None = None

    handoff_offered: bool = False
    handoff_confirmed: bool = False
    handoff_summary: dict | None = None

    messages: list[dict] = []
```

El estado reemplaza a la BD durante la POC.

---

## 7. Tools mockeadas

Todas las tools deben ser funciones Python. Deben recibir parametros estructurados y devolver diccionarios.

### 7.1 `extract_intent_and_fields`

Puede usar LLM. Si no hay API configurada, debe tener fallback por reglas simples.

Entrada:

```python
message: str
current_state: QuoteState
```

Salida:

```json
{
  "intent": "recommendation",
  "fields": {
    "event_type": "matrimonio",
    "attendees": 100,
    "event_date": "2026-10-25",
    "district": "Miraflores",
    "budget": null,
    "preferences": ["bebidas"]
  }
}
```

Intenciones soportadas:

- `recommendation`;
- `quote`;
- `human_handoff`;
- `discount_request`;
- `payment_request`;
- `modify_request`;
- `general_question`;
- `unknown`.

### 7.2 `find_missing_fields`

Regla deterministica.

```python
required = ["event_type", "attendees", "event_date", "district"]
```

### 7.3 `mock_catalog_search`

Simula catalogo comercial.

Entrada:

```json
{
  "event_type": "matrimonio",
  "attendees": 100,
  "preferences": ["bebidas"],
  "budget": null
}
```

Salida:

```json
{
  "options": [
    {
      "id": "PKG-BAR-100",
      "name": "Bar movil premium",
      "service": "eventos",
      "event_affinity": 0.95,
      "capacity_min": 80,
      "capacity_max": 130,
      "base_price": 2800,
      "currency": "PEN",
      "image": "assets/bar_movil_premium.png",
      "includes": ["barra movil", "bartender", "cristaleria", "bebidas base"]
    }
  ]
}
```

### 7.4 `mock_validate_coverage`

Distritos con cobertura para POC:

- Miraflores;
- San Isidro;
- Surco;
- Barranco;
- La Molina;
- San Borja.

Si el distrito no esta cubierto, no se recomienda ni se cotiza. Se ofrece derivacion humana.

### 7.5 `mock_check_availability`

Disponibilidad por fecha y paquete.

Reglas mock:

- `PKG-BAR-100` disponible para Miraflores el `2026-10-25`;
- `PKG-BASIC-50` disponible para eventos de hasta 60 asistentes;
- `PKG-CORP-150` no disponible el `2026-10-25`;
- cualquier fecha con menos de 72 horas desde el dia actual se rechaza por politica.

### 7.6 `mock_dimension_event`

Reglas ejemplo:

```text
cerveza: asistentes * 1.2 unidades
vino: asistentes * 0.35 botellas
gaseosa: asistentes * 0.5 botellas
hielo: asistentes * 0.4 kg
bartenders: ceil(asistentes / 50)
```

La salida debe incluir `rule_id` y `rule_version`.

### 7.7 `mock_compare_options`

Scoring:

```text
score = afinidad_evento * 0.35
      + ajuste_capacidad * 0.25
      + disponibilidad * 0.25
      + ajuste_presupuesto * 0.10
      + preferencia_usuario * 0.05
```

Debe devolver:

- opcion recomendada;
- ranking;
- razones;
- descartes.

### 7.8 `mock_generate_quote`

Debe calcular:

- subtotal;
- impuestos;
- total;
- vigencia;
- condiciones.

Reglas:

```text
igv = 18%
vigencia = 48 horas
moneda = PEN
```

Ejemplo:

```json
{
  "quote_id": "Q-POC-0001",
  "currency": "PEN",
  "subtotal": 2800.00,
  "taxes": 504.00,
  "total": 3304.00,
  "valid_until": "2026-09-20T23:59:00",
  "conditions": [
    "Precio referencial para POC.",
    "Sujeto a disponibilidad y confirmacion final.",
    "No incluye descuentos ni condiciones negociadas."
  ]
}
```

### 7.9 `mock_rag_search`

Simula RAG con una lista de documentos o textos en memoria.

Debe responder solo sobre:

- anticipacion minima;
- cobertura;
- feriados;
- recojo;
- condiciones generales;
- politicas de descuento;
- derivacion humana.

No debe devolver precios vivos ni disponibilidad.

### 7.10 `mock_handoff_whatsapp`

Genera un resumen y un link simulado.

Regla:

- si el usuario pide asesor directamente, crear handoff;
- si pide descuento, pago o excepcion, el sistema debe explicar limite y preguntar si desea derivacion;
- crear handoff solo despues de confirmacion.

Salida:

```json
{
  "handoff_id": "H-POC-0001",
  "channel": "whatsapp",
  "url": "https://wa.me/51999999999?text=Hola%2C%20necesito%20ayuda%20con%20mi%20cotizacion",
  "summary": {
    "intent": "discount_request",
    "captured_data": {
      "event_type": "matrimonio",
      "attendees": 100,
      "event_date": "2026-10-25",
      "district": "Miraflores"
    },
    "recommended_option": "Bar movil premium",
    "quote_total": 3304.00,
    "reason": "Usuario solicita descuento no autorizado para el workflow automatico."
  }
}
```

---

## 8. Datos mock

Crear los datos en `app/data/mock_data.py` o archivos JSON dentro de `app/data/`.

### 8.1 Catalogo

```json
[
  {
    "id": "PKG-BAR-100",
    "name": "Bar movil premium",
    "service": "eventos",
    "event_types": ["matrimonio", "cumpleanos", "corporativo"],
    "capacity_min": 80,
    "capacity_max": 130,
    "base_price": 2800,
    "currency": "PEN",
    "image": "assets/bar_movil_premium.png",
    "includes": ["barra movil", "bartender", "cristaleria", "bebidas base"]
  },
  {
    "id": "PKG-BASIC-50",
    "name": "Pack celebracion esencial",
    "service": "botellas",
    "event_types": ["cumpleanos", "reunion", "aniversario"],
    "capacity_min": 20,
    "capacity_max": 60,
    "base_price": 950,
    "currency": "PEN",
    "image": "assets/pack_celebracion_esencial.png",
    "includes": ["cervezas", "gaseosas", "hielo"]
  },
  {
    "id": "PKG-CORP-150",
    "name": "Servicio corporativo 150",
    "service": "eventos",
    "event_types": ["corporativo", "lanzamiento", "fin de ano"],
    "capacity_min": 100,
    "capacity_max": 180,
    "base_price": 4200,
    "currency": "PEN",
    "image": "assets/servicio_corporativo_150.png",
    "includes": ["barra movil", "2 bartenders", "bebidas premium", "coordinador"]
  }
]
```

### 8.2 Cobertura

```json
{
  "covered_districts": ["Miraflores", "San Isidro", "Surco", "Barranco", "La Molina", "San Borja"]
}
```

### 8.3 Disponibilidad

```json
{
  "2026-10-25": {
    "PKG-BAR-100": 2,
    "PKG-BASIC-50": 4,
    "PKG-CORP-150": 0
  },
  "2026-11-15": {
    "PKG-BAR-100": 1,
    "PKG-BASIC-50": 3,
    "PKG-CORP-150": 1
  }
}
```

### 8.4 Documentos RAG mock

```python
MOCK_KNOWLEDGE = [
    {
        "id": "POL-001",
        "title": "Anticipacion minima",
        "text": "Los pedidos deben realizarse con al menos 72 horas de anticipacion."
    },
    {
        "id": "POL-002",
        "title": "Feriados",
        "text": "En feriados, la entrega puede realizarse el dia habil anterior y el recojo el dia habil siguiente."
    },
    {
        "id": "POL-003",
        "title": "Descuentos",
        "text": "Los descuentos, convenios y excepciones comerciales deben ser aprobados por un asesor humano."
    }
]
```

---

## 9. Estructura sugerida del proyecto

```text
.
├── app/
│   ├── main.py                  # Entrada Streamlit
│   ├── workflow.py              # Orquestacion del workflow agentico
│   ├── state.py                 # QuoteState
│   ├── prompts.py               # Prompts modulares
│   ├── tools/
│   │   ├── extraction.py
│   │   ├── catalog.py
│   │   ├── coverage.py
│   │   ├── availability.py
│   │   ├── dimensioning.py
│   │   ├── pricing.py
│   │   ├── rag.py
│   │   └── handoff.py
│   ├── data/
│   │   ├── mock_data.py
│   │   └── assets/
│   └── ui/
│       └── components.py
├── tests/
│   ├── test_workflow.py
│   ├── test_tools.py
│   └── test_guardrails.py
├── requirements.txt
└── README.md
```

---

## 10. Logica del workflow

### 10.1 Pseudocodigo

```python
def handle_message(user_message: str, state: QuoteState) -> tuple[str, QuoteState]:
    extraction = extract_intent_and_fields(user_message, state)
    state = merge_extraction_into_state(state, extraction)

    if state.intent == "human_handoff":
        state.handoff_confirmed = True
        handoff = mock_handoff_whatsapp(state, reason="Solicitud explicita del usuario")
        return render_handoff_response(handoff), state

    if state.intent in ["discount_request", "payment_request"]:
        state.handoff_offered = True
        return ask_handoff_confirmation(state), state

    if is_handoff_confirmation(user_message, state):
        state.handoff_confirmed = True
        handoff = mock_handoff_whatsapp(state, reason="Usuario acepta derivacion")
        return render_handoff_response(handoff), state

    state.missing_fields = find_missing_fields(state)
    if state.missing_fields:
        return ask_missing_fields(state.missing_fields), state

    state.catalog_options = mock_catalog_search(state)
    coverage = mock_validate_coverage(state)
    if not coverage["ok"]:
        state.coverage_ok = False
        state.handoff_offered = True
        return explain_no_coverage_and_offer_handoff(state), state

    state.coverage_ok = True
    availability = mock_check_availability(state, state.catalog_options)
    state.valid_options = availability["available_options"]
    state.discarded_options = availability["discarded_options"]

    if not state.valid_options:
        state.availability_ok = False
        state.handoff_offered = True
        return explain_no_availability_and_offer_handoff(state), state

    state.availability_ok = True
    state.dimensioning = mock_dimension_event(state)
    comparison = mock_compare_options(state)
    state.recommended_option = comparison["recommended"]

    if state.intent == "quote":
        state.quote = mock_generate_quote(state)
        return render_quote_response(state), state

    return render_recommendation_response(state), state
```

### 10.2 Decision clave

El workflow no debe llamar todas las tools siempre. Debe avanzar segun el estado:

- si faltan datos, pregunta;
- si hay datos minimos, valida;
- si el usuario pide cotizacion, cotiza;
- si el usuario pide asesor, deriva;
- si pide descuento, ofrece derivacion.

Eso le da comportamiento agentico acotado sin convertirlo en agente autonomo.

---

## 11. UI en Streamlit

### 11.1 Pantalla principal

Debe tener:

- titulo: `Workflow agentico para cotizacion de eventos`;
- chat conversacional;
- panel lateral con estado actual;
- card de recomendacion;
- card de cotizacion si existe;
- imagen del paquete recomendado;
- boton opcional para reiniciar conversacion.

### 11.2 Imagen multimodal

La imagen es solo presentacion visual.

Regla:

```text
La imagen no decide precio, disponibilidad, cobertura ni recomendacion.
```

Si no existe imagen local, usar placeholder por tipo de evento.

---

## 12. Guardrails de POC

La POC debe bloquear:

- cotizar sin evento, asistentes, fecha y distrito;
- cotizar fuera de cobertura;
- cotizar sin disponibilidad;
- aprobar descuentos;
- confirmar pagos;
- cerrar ventas;
- inventar condiciones que no esten en mocks;
- guardar preferencias permanentes;
- derivar por WhatsApp sin solicitud o confirmacion del usuario.

Mensajes esperados:

- descuento: "No puedo aprobar descuentos desde el flujo automatico. Si deseas, puedo derivarte con un asesor por WhatsApp."
- pago: "No puedo confirmar pagos desde esta POC. Si deseas continuar, puedo derivarte con un asesor por WhatsApp."
- sin cobertura: "No tengo cobertura confirmada para ese distrito en esta POC. Puedo derivarte con un asesor si deseas revisar una excepcion."

---

## 13. Casos de prueba funcionales

### Caso 1: recomendacion completa

Usuario:

```text
Necesito bebidas para un matrimonio de 100 personas el 25 de octubre en Miraflores.
```

Esperado:

- extrae evento, asistentes, fecha y distrito;
- valida cobertura;
- valida disponibilidad;
- dimensiona;
- recomienda `Bar movil premium`;
- muestra imagen.

### Caso 2: datos faltantes

Usuario:

```text
Quiero organizar un cumpleanos.
```

Esperado:

- pregunta cantidad de asistentes, fecha y distrito;
- no recomienda todavia.

### Caso 3: cotizacion

Usuario:

```text
Cuanto cuesta?
```

Esperado:

- genera cotizacion solo si ya hay recomendacion valida;
- muestra subtotal, IGV, total, vigencia y condiciones.

### Caso 4: descuento

Usuario:

```text
Me haces 15% de descuento?
```

Esperado:

- no modifica precio;
- explica limite;
- ofrece derivacion por WhatsApp.

### Caso 5: derivacion

Usuario:

```text
Si, derivame con un asesor.
```

Esperado:

- crea resumen mock;
- genera link mock de WhatsApp;
- muestra datos capturados.

### Caso 6: sin cobertura

Usuario:

```text
Necesito bebidas para 80 personas el 25 de octubre en Chosica.
```

Esperado:

- detecta no cobertura;
- no cotiza;
- ofrece derivacion humana.

---

## 14. Criterios de aceptacion

La POC esta completa cuando:

- corre localmente con Streamlit;
- mantiene estado durante la conversacion;
- pide solo datos faltantes;
- recomienda usando catalogo mock;
- valida cobertura y disponibilidad mock;
- dimensiona cantidades con reglas mock;
- cotiza con precios mock;
- muestra imagen referencial;
- simula RAG para politicas;
- bloquea descuentos, pagos y cierres de venta;
- deriva por WhatsApp solo si el usuario lo solicita o acepta;
- incluye tests unitarios para tools y guardrails principales.

---

## 15. Comando esperado de ejecucion

```bash
streamlit run app/main.py
```

Si se usa archivo `.env`, variables sugeridas:

```text
OPENAI_API_KEY=
USE_LLM=true
MOCK_WHATSAPP_NUMBER=51999999999
```

Si `USE_LLM=false`, la POC debe funcionar con extraccion basica por reglas.

---

## 16. Nota para implementacion en Codex

Implementar primero la POC local con mocks. No conectar bases reales ni servicios externos.

Orden recomendado:

1. crear estructura de archivos;
2. crear `QuoteState`;
3. crear datos mock;
4. crear tools mock;
5. crear workflow;
6. crear UI Streamlit;
7. agregar imagenes placeholder;
8. agregar tests;
9. documentar ejecucion en README.

La prioridad es que el flujo funcione completo de punta a punta con datos mockeados.

