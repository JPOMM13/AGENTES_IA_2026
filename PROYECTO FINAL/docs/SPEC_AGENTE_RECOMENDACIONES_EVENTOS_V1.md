# Spec v1 - Agente de recomendaciones y cotizacion para ocasiones de consumo

## 0. Proposito del documento

Este spec define el primer desarrollo del agente de recomendaciones y cotizacion para eventos y ocasiones de consumo, tomando como base:

- el Profile Card final v3.2;
- la arquitectura objetivo adjunta;
- el analisis de los PDFs del curso;
- el DDL propuesto para la base de datos;
- la decision de despliegue en cluster on-premise k3s;
- multimodalidad limitada a la presentacion visual del evento en Streamlit.

El objetivo es construir un agente demostrable, controlado y auditable. El LLM entiende y conversa; las herramientas, reglas y base de datos resuelven los datos comerciales criticos.

---

## 1. Alcance funcional

### 1.1 Nombre del agente

Agente IA de recomendaciones y cotizacion para eventos y ocasiones de consumo.

### 1.2 Responsabilidad principal

El agente acompana al usuario desde una necesidad inicial hasta una de estas salidas:

1. recomendacion explicable;
2. cotizacion verificada;
3. derivacion humana por WhatsApp, solo cuando el usuario la solicite o cuando el flujo detecte una condicion que lo impide y el usuario acepte continuar con asesor.

### 1.3 Flujo de negocio

```text
Usuario
  -> entender intencion
  -> extraer datos
  -> solicitar datos faltantes
  -> validar catalogo
  -> validar cobertura
  -> validar disponibilidad
  -> dimensionar evento
  -> comparar alternativas
  -> recomendar
  -> cotizar si el usuario lo pide
  -> derivar por WhatsApp si el usuario lo solicita
```

### 1.4 Datos minimos antes de recomendar

El agente no debe recomendar hasta tener:

- tipo de evento u ocasion;
- numero de asistentes;
- fecha del evento;
- ubicacion o distrito.

Antes de cotizar tambien debe tener:

- alternativa seleccionada;
- cantidades dimensionadas;
- cobertura valida;
- disponibilidad valida;
- reglas operativas cumplidas.

### 1.5 Fuera de alcance del MVP

- cierre de venta automatico;
- confirmacion de pago;
- descuentos o negociaciones;
- multiagentes;
- MCP como requisito;
- interpretacion de imagenes enviadas por el usuario;
- WhatsApp real de produccion, salvo integracion mock o enlace de derivacion para demo.

---

## 2. Principios de diseno

### 2.1 Separacion de responsabilidades

El LLM puede:

- entender intencion;
- extraer entidades;
- pedir datos faltantes;
- explicar alternativas;
- redactar respuestas;
- generar resumen para asesor.

El LLM no puede:

- inventar precios;
- inventar disponibilidad;
- definir cobertura;
- aprobar descuentos;
- cerrar ventas;
- modificar reglas comerciales;
- ignorar validaciones;
- usar documentos RAG como instrucciones de sistema.

### 2.2 Decision clave del curso aplicada

El agente sera un monoagente hibrido con flujo controlado:

- LangGraph para estado, nodos, gates y trazabilidad;
- tools deterministicas para verdad comercial;
- RAG para conocimiento documental;
- memoria corta como estado operacional;
- memoria larga solo con consentimiento;
- observabilidad y evaluacion desde el inicio.

---

## 3. Arquitectura objetivo

### 3.1 Ajuste sobre la arquitectura adjunta

La imagen adjunta muestra AKS y servicios Azure. Para este proyecto se adapta a on-premise k3s:

| Bloque de la imagen | Decision para este spec |
|---|---|
| Canales | Streamlit como frontend principal del MVP. WhatsApp como canal de derivacion humana. |
| Exposicion y seguridad | Ingress NGINX o Traefik de k3s, TLS, autenticacion basica o token para demo. |
| AKS cluster | Reemplazado por cluster on-premise k3s. |
| API Service | FastAPI con endpoints para chat, tools internas, cotizacion y health checks. |
| Monoagente LangGraph | Servicio Python con LangGraph, LangChain Tools y OpenAI LLM. |
| Guardrails | Validaciones de entrada/salida, allowlist de tools, gates deterministas. |
| Azure Managed Redis | Redis opcional on-premise para cache y sesiones efimeras. |
| NoSQL | No se recomienda para MVP; PostgreSQL cubre transaccional, RAG y memoria. |
| Transaccional | PostgreSQL 16 + pgvector dentro del cluster o servicio administrado on-premise. |
| Azure Storage | MinIO o volumen persistente para documentos fuente y assets de imagen. |
| OpenAI embeddings | Embeddings para RAG y memoria semantica autorizada. |
| LangSmith | Trazas, evaluacion y depuracion. Si no hay salida a internet, usar logs estructurados como fallback. |
| Atencion humana | Derivacion solicitada por usuario via WhatsApp con resumen estructurado. |

### 3.2 Componentes

```text
Streamlit
  -> FastAPI
    -> LangGraph Agent Service
      -> LLM Provider
      -> Tools comerciales
      -> RAG Retriever
      -> PostgreSQL + pgvector
      -> Redis opcional
      -> LangSmith / logs
      -> WhatsApp handoff link/mock
```

### 3.3 Despliegue k3s

Namespaces sugeridos:

- `agent-app`: Streamlit, FastAPI, LangGraph worker.
- `agent-data`: PostgreSQL, Redis, MinIO.
- `agent-observability`: dashboards/logs si se implementan localmente.

Servicios minimos:

- `streamlit-ui`;
- `api-service`;
- `agent-worker`;
- `postgres`;
- `redis` opcional;
- `minio` opcional para documentos y assets.

Secrets:

- `OPENAI_API_KEY`;
- `DATABASE_URL`;
- `LANGSMITH_API_KEY` si aplica;
- `WHATSAPP_PHONE_NUMBER` o URL de derivacion;
- credenciales de PostgreSQL.

---

## 4. Workflow LangGraph

### 4.1 Estado operacional

El centro del agente es `RequestState`, no el historial completo de chat.

```python
class RequestState(TypedDict):
    request_id: str
    customer_id: str | None
    channel: Literal["streamlit", "whatsapp"]
    intent: str | None
    stage: str

    event_type: str | None
    attendees: int | None
    event_date: str | None
    district: str | None
    address_reference: str | None
    budget: float | None
    preferences: list[str]
    product_categories: list[str]

    missing_fields: list[str]
    catalog_validated: bool
    coverage_validated: bool
    availability_validated: bool
    policy_validated: bool

    candidate_options: list[dict]
    discarded_options: list[dict]
    selected_option: dict | None
    dimensioning: dict | None
    quote_id: str | None
    quote_status: str | None

    consent_preferences: bool
    requires_human: bool
    handoff_requested_by_user: bool
    handoff_reason: str | None
    tool_retries: dict[str, int]
    last_error: str | None
```

### 4.2 Nodos

1. `classify_and_extract`
   - LLM extrae intencion y campos.
   - Salida estructurada JSON.

2. `merge_state`
   - Codigo combina datos nuevos con estado existente.
   - Normaliza fecha, distrito, asistentes y presupuesto.

3. `required_fields_gate`
   - Codigo valida datos minimos.
   - Si faltan datos, va a `ask_missing_fields`.

4. `ask_missing_fields`
   - LLM redacta pregunta breve solo por campos faltantes.

5. `catalog_validation`
   - Tool `buscar_catalogo`.

6. `coverage_validation`
   - Tool `validar_cobertura`.

7. `availability_validation`
   - Tool `consultar_disponibilidad`.

8. `policy_validation`
   - Regla deterministica: anticipacion minima, piso, ascensor, restricciones.

9. `dimension_event`
   - Tool `dimensionar_evento`.

10. `compare_options`
    - Tool `comparar_alternativas`.

11. `recommendation_response`
    - LLM explica la recomendacion sin revelar razonamiento interno.

12. `quote_gate`
    - Si el usuario pide precio/cotizacion, pasa a cotizar.

13. `generate_quote`
    - Tool `generar_cotizacion`.

14. `quote_response`
    - LLM presenta subtotal, impuestos, total, vigencia y condiciones.

15. `handoff_gate`
    - Solo deriva si el usuario solicita asesor o acepta derivacion tras bloqueo.

16. `human_handoff`
    - Tool `crear_derivacion_whatsapp`.

### 4.3 Reintentos

Maximo 2 reintentos por tool. Si persiste el fallo:

- no inventar resultado;
- informar que no se puede confirmar el dato;
- ofrecer derivacion humana;
- derivar solo si el usuario lo solicita.

---

## 5. Tools

### 5.1 `buscar_catalogo`

Entrada:

```json
{
  "event_type": "matrimonio",
  "attendees": 100,
  "categories": ["cerveza", "vino"],
  "budget": 2500
}
```

Salida:

```json
{
  "options": [
    {
      "product_id": 12,
      "sku": "PACK-BAR-100",
      "name": "Bar para eventos 100 personas",
      "service": "eventos",
      "capacity_min": 80,
      "capacity_max": 120,
      "active": true
    }
  ]
}
```

### 5.2 `validar_cobertura`

Valida distrito, servicio y restricciones operativas. No usa LLM.

### 5.3 `consultar_disponibilidad`

Consulta cupos por producto y fecha. Una opcion sin cupo se descarta.

### 5.4 `dimensionar_evento`

Calcula cantidades comerciales con reglas versionadas.

Entrada:

```json
{
  "event_type": "matrimonio",
  "attendees": 100,
  "duration_hours": 5,
  "categories": ["cerveza", "vino", "gaseosas"]
}
```

Salida:

```json
{
  "items": [
    {
      "concept": "cerveza",
      "quantity": 120,
      "unit": "botella"
    }
  ],
  "rule_id": "DIM-EVENT-04",
  "rule_version": "2026-09"
}
```

### 5.5 `comparar_alternativas`

Aplica scoring deterministico:

```text
score = afinidad_evento * 0.30
      + ajuste_capacidad * 0.25
      + disponibilidad * 0.20
      + ajuste_presupuesto * 0.15
      + preferencia_usuario * 0.10
```

Los pesos deben estar versionados en base de datos.

### 5.6 `generar_cotizacion`

Genera cotizacion desde precios oficiales. Devuelve moneda, subtotal, impuestos, total, vigencia y condiciones.

### 5.7 `rag_buscar_politicas`

Busca politicas, FAQs y condiciones documentales. No recupera precios vivos ni disponibilidad.

### 5.8 `obtener_preferencias` y `guardar_preferencia`

Solo se guarda memoria larga con consentimiento explicito.

### 5.9 `crear_derivacion_whatsapp`

Genera una derivacion con:

- resumen de la conversacion;
- datos capturados;
- validaciones realizadas;
- motivo;
- cotizacion si existe;
- link o instruccion para continuar por WhatsApp.

La derivacion humana debe ser solicitada por el usuario. Si existe un bloqueo, el agente puede ofrecerla, pero no crearla sin confirmacion.

---

## 6. RAG

### 6.1 Uso correcto

RAG se usa para conocimiento documental:

- politicas comerciales;
- restricciones;
- condiciones de servicio;
- preguntas frecuentes;
- procedimientos;
- descripciones de productos;
- terminos y condiciones.

### 6.2 No usar RAG para

- precio vigente;
- stock;
- disponibilidad;
- cobertura actual;
- impuestos;
- total de cotizacion;
- confirmacion de venta.

### 6.3 Ingesta

Pipeline:

```text
PDF/MD/documento
  -> extraccion texto
  -> chunking
  -> metadatos
  -> embeddings
  -> rag.chunks
```

Metadatos minimos:

- documento;
- version;
- categoria;
- servicio;
- tipo de contenido;
- confidencialidad;
- estado.

---

## 7. Multimodalidad

La multimodalidad del MVP se limita a la presentacion visual en Streamlit.

### 7.1 Alcance

El agente podra mostrar una imagen representativa del posible evento o paquete recomendado:

- imagen del paquete;
- mock visual del montaje;
- imagen referencial por tipo de evento;
- tarjeta visual con recomendacion y cotizacion.

### 7.2 Fuente de imagenes

Prioridad:

1. imagen guardada en catalogo;
2. asset local en MinIO/volumen;
3. placeholder por tipo de evento;
4. generacion manual posterior, no automatica en el flujo critico.

### 7.3 Restriccion

La imagen no decide:

- precio;
- disponibilidad;
- cobertura;
- capacidad;
- cantidades.

Solo mejora la presentacion en Streamlit.

---

## 8. Redis

Redis es recomendado, pero no obligatorio para el MVP.

### 8.1 Usos recomendados

- cache de respuestas de catalogo poco cambiantes;
- cache de politicas RAG frecuentes;
- rate limiting por sesion;
- almacenamiento efimero de estado de UI;
- lock corto para evitar doble cotizacion simultanea de la misma solicitud.

### 8.2 No usar Redis para

- fuente de verdad transaccional;
- precios;
- disponibilidad definitiva;
- memoria larga;
- auditoria.

TTL sugeridos:

- catalogo: 15 minutos;
- cobertura: 60 minutos;
- estado efimero de UI: 30 minutos;
- rate limit: ventana de 1 a 5 minutos.

---

## 9. Modelo de datos propuesto

### 9.1 Decision

PostgreSQL 16 + pgvector sera la base principal para:

- datos transaccionales;
- catalogo;
- disponibilidad;
- cotizaciones;
- derivaciones;
- RAG;
- memoria autorizada.

Se mejora el DDL original para:

- quitar dependencia conceptual de Cloud SQL;
- agregar reglas de dimensionamiento;
- agregar scoring versionado;
- agregar imagenes de catalogo;
- registrar validaciones;
- soportar derivacion por WhatsApp;
- reforzar auditoria;
- separar datos vivos de conocimiento documental.

### 9.2 DDL propuesto

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS rag;
CREATE SCHEMA IF NOT EXISTS memory;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE core.parametros (
  clave text NOT NULL,
  valor_num numeric,
  valor_texto text,
  descripcion text NOT NULL,
  vigente_desde timestamptz NOT NULL DEFAULT now(),
  vigente_hasta timestamptz,
  PRIMARY KEY (clave, vigente_desde),
  CHECK (valor_num IS NOT NULL OR valor_texto IS NOT NULL)
);

CREATE TABLE core.clientes (
  id bigserial PRIMARY KEY,
  celular_hash text UNIQUE,
  celular_ultimos4 char(4),
  nombre text,
  email_hash text,
  creado_en timestamptz NOT NULL DEFAULT now(),
  actualizado_en timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.tipos_evento (
  id smallserial PRIMARY KEY,
  nombre text NOT NULL UNIQUE,
  activo boolean NOT NULL DEFAULT true
);

CREATE TABLE core.productos (
  id bigserial PRIMARY KEY,
  sku text NOT NULL UNIQUE,
  servicio text NOT NULL CHECK (servicio IN ('barril', 'eventos', 'botellas')),
  nombre text NOT NULL,
  descripcion text,
  capacidad_min integer CHECK (capacidad_min IS NULL OR capacidad_min > 0),
  capacidad_max integer CHECK (capacidad_max IS NULL OR capacidad_max > 0),
  capacidad_l numeric CHECK (capacidad_l IS NULL OR capacidad_l > 0),
  unidades integer CHECK (unidades IS NULL OR unidades > 0),
  precio_base numeric(12, 2) NOT NULL CHECK (precio_base >= 0),
  moneda char(3) NOT NULL DEFAULT 'PEN',
  imagen_url text,
  activo boolean NOT NULL DEFAULT true,
  creado_en timestamptz NOT NULL DEFAULT now(),
  CHECK (capacidad_min IS NULL OR capacidad_max IS NULL OR capacidad_min <= capacidad_max)
);

CREATE TABLE core.producto_evento (
  producto_id bigint NOT NULL REFERENCES core.productos(id) ON DELETE CASCADE,
  tipo_evento_id smallint NOT NULL REFERENCES core.tipos_evento(id) ON DELETE CASCADE,
  afinidad numeric NOT NULL CHECK (afinidad BETWEEN 0 AND 1),
  PRIMARY KEY (producto_id, tipo_evento_id)
);

CREATE TABLE core.cobertura (
  id bigserial PRIMARY KEY,
  distrito text NOT NULL,
  servicio text NOT NULL CHECK (servicio IN ('barril', 'eventos', 'botellas')),
  activo boolean NOT NULL DEFAULT true,
  restricciones jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (distrito, servicio)
);

CREATE TABLE core.disponibilidad (
  producto_id bigint NOT NULL REFERENCES core.productos(id) ON DELETE CASCADE,
  fecha date NOT NULL,
  cupos_total integer NOT NULL CHECK (cupos_total >= 0),
  cupos_usados integer NOT NULL DEFAULT 0 CHECK (cupos_usados >= 0),
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (producto_id, fecha),
  CHECK (cupos_usados <= cupos_total)
);

CREATE TABLE core.reglas_dimensionamiento (
  id text PRIMARY KEY,
  version text NOT NULL,
  tipo_evento_id smallint REFERENCES core.tipos_evento(id),
  servicio text NOT NULL CHECK (servicio IN ('barril', 'eventos', 'botellas')),
  categoria text NOT NULL,
  formula jsonb NOT NULL,
  activo boolean NOT NULL DEFAULT true,
  vigente_desde timestamptz NOT NULL DEFAULT now(),
  vigente_hasta timestamptz
);

CREATE TABLE core.scoring_config (
  id text PRIMARY KEY,
  version text NOT NULL,
  pesos jsonb NOT NULL,
  activo boolean NOT NULL DEFAULT true,
  creado_en timestamptz NOT NULL DEFAULT now(),
  CHECK (pesos ? 'afinidad_evento'
     AND pesos ? 'ajuste_capacidad'
     AND pesos ? 'disponibilidad'
     AND pesos ? 'ajuste_presupuesto'
     AND pesos ? 'preferencia_usuario')
);

CREATE TABLE core.solicitudes (
  id bigserial PRIMARY KEY,
  request_id uuid NOT NULL DEFAULT gen_random_uuid(),
  cliente_id bigint REFERENCES core.clientes(id) ON DELETE SET NULL,
  canal text NOT NULL DEFAULT 'streamlit' CHECK (canal IN ('streamlit', 'whatsapp')),
  tipo_evento_id smallint REFERENCES core.tipos_evento(id),
  servicio text CHECK (servicio IN ('barril', 'eventos', 'botellas')),
  asistentes integer CHECK (asistentes IS NULL OR asistentes > 0),
  fecha_evento date,
  distrito text,
  direccion_referencia text,
  piso smallint DEFAULT 1 CHECK (piso IS NULL OR piso >= 1),
  tiene_ascensor boolean DEFAULT true,
  presupuesto numeric(12, 2) CHECK (presupuesto IS NULL OR presupuesto >= 0),
  preferencias jsonb NOT NULL DEFAULT '[]'::jsonb,
  estado text NOT NULL DEFAULT 'abierta'
    CHECK (estado IN ('abierta', 'recomendada', 'cotizada', 'derivada', 'cerrada', 'abandonada')),
  thread_id text,
  creado_en timestamptz NOT NULL DEFAULT now(),
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (request_id)
);

CREATE INDEX idx_solicitudes_cliente_creado ON core.solicitudes(cliente_id, creado_en DESC);
CREATE INDEX idx_solicitudes_abiertas ON core.solicitudes(estado) WHERE estado = 'abierta';

CREATE TABLE core.solicitud_validaciones (
  id bigserial PRIMARY KEY,
  solicitud_id bigint NOT NULL REFERENCES core.solicitudes(id) ON DELETE CASCADE,
  tipo text NOT NULL CHECK (tipo IN ('catalogo', 'cobertura', 'disponibilidad', 'politica', 'dimensionamiento', 'precio')),
  estado text NOT NULL CHECK (estado IN ('aprobada', 'rechazada', 'error')),
  detalle jsonb NOT NULL DEFAULT '{}'::jsonb,
  creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.recomendaciones (
  id bigserial PRIMARY KEY,
  solicitud_id bigint NOT NULL REFERENCES core.solicitudes(id) ON DELETE CASCADE,
  producto_id bigint NOT NULL REFERENCES core.productos(id),
  score numeric NOT NULL CHECK (score BETWEEN 0 AND 1),
  scoring_config_id text REFERENCES core.scoring_config(id),
  razones jsonb NOT NULL,
  descartes jsonb NOT NULL DEFAULT '[]'::jsonb,
  seleccionado boolean NOT NULL DEFAULT false,
  creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.cotizaciones (
  id bigserial PRIMARY KEY,
  solicitud_id bigint NOT NULL REFERENCES core.solicitudes(id) ON DELETE CASCADE,
  moneda char(3) NOT NULL DEFAULT 'PEN',
  subtotal numeric(12, 2) NOT NULL CHECK (subtotal >= 0),
  impuestos numeric(12, 2) NOT NULL CHECK (impuestos >= 0),
  total numeric(12, 2) NOT NULL CHECK (total >= 0),
  vigencia_hasta timestamptz NOT NULL,
  condiciones text,
  estado text NOT NULL DEFAULT 'emitida' CHECK (estado IN ('emitida', 'aceptada', 'vencida', 'anulada')),
  creado_en timestamptz NOT NULL DEFAULT now(),
  CHECK (total = subtotal + impuestos)
);

CREATE TABLE core.cotizacion_detalle (
  id bigserial PRIMARY KEY,
  cotizacion_id bigint NOT NULL REFERENCES core.cotizaciones(id) ON DELETE CASCADE,
  producto_id bigint REFERENCES core.productos(id),
  concepto text NOT NULL,
  cantidad numeric NOT NULL CHECK (cantidad > 0),
  unidad text NOT NULL DEFAULT 'unidad',
  precio_unitario numeric(12, 2) NOT NULL CHECK (precio_unitario >= 0),
  subtotal numeric(12, 2) NOT NULL CHECK (subtotal >= 0)
);

CREATE TABLE core.derivaciones (
  id bigserial PRIMARY KEY,
  solicitud_id bigint REFERENCES core.solicitudes(id) ON DELETE CASCADE,
  cliente_id bigint REFERENCES core.clientes(id) ON DELETE SET NULL,
  canal text NOT NULL DEFAULT 'whatsapp' CHECK (canal IN ('whatsapp')),
  solicitado_por_usuario boolean NOT NULL DEFAULT true,
  motivo text NOT NULL,
  prioridad text NOT NULL DEFAULT 'normal' CHECK (prioridad IN ('baja', 'normal', 'alta')),
  estado text NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'tomada', 'resuelta', 'cancelada')),
  whatsapp_url text,
  contexto jsonb NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),
  CHECK (contexto ? 'intencion'
     AND contexto ? 'datos_capturados'
     AND contexto ? 'resumen')
);

CREATE INDEX idx_derivaciones_pendientes ON core.derivaciones(estado, prioridad)
WHERE estado = 'pendiente';

CREATE TABLE rag.documents (
  document_id text PRIMARY KEY,
  titulo text NOT NULL,
  version text NOT NULL,
  estado text NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'obsoleto')),
  confidencialidad text NOT NULL DEFAULT 'anonimizado',
  origen text,
  creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag.chunks (
  chunk_id text PRIMARY KEY,
  document_id text NOT NULL REFERENCES rag.documents(document_id) ON DELETE CASCADE,
  categoria text NOT NULL,
  servicio text NOT NULL DEFAULT 'general' CHECK (servicio IN ('general', 'barril', 'eventos', 'botellas')),
  tipo_contenido text NOT NULL CHECK (tipo_contenido IN ('politica', 'faq', 'regla', 'descripcion', 'objecion', 'arquitectura')),
  texto text NOT NULL,
  embedding vector(1536),
  version text NOT NULL DEFAULT '1.0',
  estado text NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'obsoleto')),
  actualizado_en timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_chunks_servicio_categoria ON rag.chunks(servicio, categoria)
WHERE estado = 'activo';
CREATE INDEX idx_chunks_embedding ON rag.chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE memory.consentimientos (
  id bigserial PRIMARY KEY,
  cliente_id bigint NOT NULL REFERENCES core.clientes(id) ON DELETE CASCADE,
  tipo text NOT NULL CHECK (tipo IN ('obligatorio', 'preferencias', 'promocional')),
  otorgado boolean NOT NULL,
  evidencia text NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),
  revocado_en timestamptz
);

CREATE TABLE memory.preferencias_cliente (
  id bigserial PRIMARY KEY,
  cliente_id bigint NOT NULL REFERENCES core.clientes(id) ON DELETE CASCADE,
  consent_id bigint NOT NULL REFERENCES memory.consentimientos(id),
  categoria text NOT NULL CHECK (categoria IN ('preferencia_producto', 'restriccion_logistica', 'tipo_ocasion', 'sensibilidad_precio')),
  contenido text NOT NULL,
  embedding vector(1536),
  confianza text NOT NULL CHECK (confianza IN ('alta', 'media', 'baja')),
  vigente boolean NOT NULL DEFAULT true,
  superseded_by bigint REFERENCES memory.preferencias_cliente(id),
  creado_en timestamptz NOT NULL DEFAULT now(),
  expira_en timestamptz DEFAULT now() + interval '12 months'
);

CREATE INDEX idx_preferencias_cliente ON memory.preferencias_cliente(cliente_id, vigente);
CREATE INDEX idx_preferencias_embedding ON memory.preferencias_cliente USING hnsw (embedding vector_cosine_ops);

CREATE TABLE memory.episodios (
  id bigserial PRIMARY KEY,
  cliente_id bigint REFERENCES core.clientes(id) ON DELETE CASCADE,
  solicitud_id bigint REFERENCES core.solicitudes(id) ON DELETE SET NULL,
  thread_id text NOT NULL,
  etapa text NOT NULL CHECK (etapa IN ('inicio', 'intencion', 'recoleccion', 'recomendacion', 'cotizacion', 'derivacion', 'cierre')),
  desenlace text NOT NULL CHECK (desenlace IN ('completado', 'abandonado', 'derivado')),
  resumen text,
  creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_episodios_cliente ON memory.episodios(cliente_id, creado_en DESC);

CREATE TABLE audit.agent_events (
  id bigserial PRIMARY KEY,
  request_id uuid NOT NULL,
  node_name text NOT NULL,
  event_type text NOT NULL CHECK (event_type IN ('state_before', 'tool_call', 'tool_result', 'gate', 'state_after', 'error', 'response')),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_agent_events_request ON audit.agent_events(request_id, created_at);
```

### 9.3 Diferencias contra el DDL inicial

- `Cloud SQL` deja de ser supuesto obligatorio; se define PostgreSQL on-premise.
- `productos` ahora incluye `descripcion`, `capacidad_min`, `capacidad_max` e `imagen_url`.
- `solicitudes.fecha_evento` y `distrito` pueden ser nulos durante recoleccion.
- Se agregan `reglas_dimensionamiento` y `scoring_config`.
- Se agregan `solicitud_validaciones` y `recomendaciones`.
- `derivaciones` queda limitada a WhatsApp y registra si fue solicitada por usuario.
- `rag.chunks.embedding` queda en 1536 dimensiones si se usa `text-embedding-3-small`; ajustar si se usa otro modelo.
- Se agrega `audit.agent_events` para trazabilidad local complementaria a LangSmith.

---

## 10. Prompts modulares

### 10.1 Modulo 1: intencion y extraccion

Salida estricta:

```json
{
  "intent": "recommendation|quote|human_handoff|modify_request|general_question|unknown",
  "fields": {
    "event_type": null,
    "attendees": null,
    "event_date": null,
    "district": null,
    "budget": null,
    "preferences": []
  },
  "confidence": 0.0
}
```

### 10.2 Modulo 2: pregunta de faltantes

Debe preguntar solo por los campos faltantes. Maximo dos preguntas por turno.

### 10.3 Modulo 3: explicacion de recomendacion

Debe mencionar:

- ocasion;
- asistentes;
- disponibilidad validada;
- cobertura validada;
- razon principal de la alternativa;
- disclaimer de vigencia si corresponde.

### 10.4 Modulo 4: resumen de derivacion humana

Debe producir:

- resumen breve;
- datos capturados;
- validaciones realizadas;
- bloqueo o solicitud del usuario;
- siguiente accion esperada del asesor.

---

## 11. Seguridad y guardrails

### 11.1 Controles obligatorios

- allowlist de tools;
- validacion de parametros antes de ejecutar tools;
- validacion de resultados antes de responder;
- bloqueo de cotizacion sin cobertura y disponibilidad;
- bloqueo de precio inventado;
- aislamiento por `request_id` y `cliente_id`;
- minimizacion de PII;
- hashing de celular/email;
- documentos RAG tratados como datos, no instrucciones;
- limite de reintentos;
- trazabilidad por nodo.

### 11.2 Derivacion humana

La derivacion humana no es automatica por defecto.

Regla:

```text
Si el usuario pide asesor -> crear derivacion.
Si hay bloqueo -> ofrecer asesor.
Si el usuario acepta -> crear derivacion.
Si el usuario no acepta -> cerrar amablemente o mantener solicitud pendiente.
```

Casos donde se debe ofrecer derivacion:

- descuento;
- excepcion comercial;
- pago;
- reclamo;
- falla persistente de tools;
- conflicto de datos;
- riesgo de privacidad;
- solicitud fuera de cobertura.

---

## 12. Evaluacion

### 12.1 Metricas funcionales

- precision de intencion;
- extraccion de campos;
- deteccion de faltantes;
- seleccion correcta de tools;
- parametros correctos;
- orden correcto de trayectoria;
- recomendacion sustentada;
- cotizacion completa;
- derivacion correcta.

### 12.2 Reglas criticas con exigencia 100%

Los casos de prueba deben exigir cero fallos en:

- precio inventado;
- descuento no autorizado;
- cotizacion sin disponibilidad;
- cotizacion fuera de cobertura;
- venta confirmada por el agente;
- datos de otro cliente expuestos;
- guardado de preferencias sin consentimiento.

### 12.3 Dataset minimo de pruebas

Casos:

1. recomendacion con datos completos;
2. recomendacion con datos faltantes;
3. cotizacion solicitada despues de recomendacion;
4. distrito sin cobertura;
5. fecha sin disponibilidad;
6. solicitud de descuento;
7. solicitud explicita de asesor;
8. prompt injection del usuario;
9. documento RAG con instruccion maliciosa;
10. preferencia guardada con y sin consentimiento.

---

## 13. Plan de desarrollo por partes

### Parte 1 - Base del proyecto

Entregables:

- estructura Python;
- FastAPI;
- Streamlit;
- conexion PostgreSQL;
- variables de entorno;
- docker compose local;
- manifests base k3s.

Criterio de aceptacion:

- UI envia mensaje;
- API responde health check;
- BD inicializa DDL.

### Parte 2 - Modelo de datos y seeds

Entregables:

- DDL aplicado;
- datos semilla de eventos, productos, cobertura, disponibilidad y parametros;
- funciones de consulta basicas.

Criterio de aceptacion:

- se puede consultar catalogo, cobertura y disponibilidad sin LLM.

### Parte 3 - Tools deterministicas

Entregables:

- `buscar_catalogo`;
- `validar_cobertura`;
- `consultar_disponibilidad`;
- `dimensionar_evento`;
- `comparar_alternativas`;
- `generar_cotizacion`.

Criterio de aceptacion:

- todas las tools tienen tests unitarios.

### Parte 4 - LangGraph

Entregables:

- `RequestState`;
- nodos;
- gates;
- persistencia de checkpoints;
- manejo de errores y reintentos.

Criterio de aceptacion:

- una conversacion completa llega a recomendacion sin cotizar.

### Parte 5 - Cotizacion

Entregables:

- generacion de cotizacion;
- detalle de cotizacion;
- vigencia y condiciones;
- disclaimer.

Criterio de aceptacion:

- no existe cotizacion sin validaciones previas.

### Parte 6 - RAG

Entregables:

- pipeline de ingesta;
- chunks con metadatos;
- retriever;
- tool `rag_buscar_politicas`.

Criterio de aceptacion:

- responde preguntas de politicas sin mezclar precios vivos.

### Parte 7 - Streamlit multimodal

Entregables:

- vista conversacional;
- card de recomendacion;
- imagen del paquete/evento;
- card de cotizacion.

Criterio de aceptacion:

- la recomendacion muestra imagen referencial sin afectar la decision comercial.

### Parte 8 - Derivacion WhatsApp

Entregables:

- resumen para asesor;
- registro en `core.derivaciones`;
- link de WhatsApp o mock;
- confirmacion previa del usuario.

Criterio de aceptacion:

- el sistema no deriva sin solicitud o aceptacion del usuario.

### Parte 9 - Seguridad, observabilidad y evals

Entregables:

- logs estructurados;
- LangSmith si esta disponible;
- dataset de evaluacion;
- pruebas de prompt injection;
- reporte de metricas.

Criterio de aceptacion:

- pasan las reglas criticas al 100% en el dataset definido.

---

## 14. Demo sugerido

Conversacion principal:

```text
Usuario: Necesito bebidas para un matrimonio.
Agente: pregunta asistentes, fecha y ubicacion.
Usuario: 100 personas, 25 de octubre, Miraflores.
Agente: valida catalogo, cobertura, disponibilidad y dimensionamiento.
Agente: recomienda dos alternativas y explica la mejor.
Usuario: Cuanto cuesta?
Agente: genera cotizacion verificada.
Usuario: Me haces 15% de descuento?
Agente: indica que no puede aprobar descuentos y pregunta si desea derivacion por WhatsApp.
Usuario: Si, derivame.
Agente: crea derivacion por WhatsApp con resumen para asesor.
```

Esta demo muestra:

- prompt engineering;
- memoria de estado;
- LangGraph;
- tools;
- RAG;
- reglas;
- guardrails;
- HITL;
- multimodalidad de presentacion;
- evaluacion;
- observabilidad.

---

## 15. Criterios de exito del MVP

El MVP se considera listo cuando:

- recopila datos minimos sin repreguntar innecesariamente;
- valida catalogo, cobertura y disponibilidad antes de recomendar;
- dimensiona con reglas externas al LLM;
- cotiza solo con datos oficiales;
- muestra imagen referencial en Streamlit;
- deriva por WhatsApp solo si el usuario lo solicita o acepta;
- registra trazabilidad de nodos, tools y errores;
- pasa pruebas criticas de seguridad y reglas comerciales.

