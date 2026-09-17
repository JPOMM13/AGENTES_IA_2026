-- =============================================================================
-- DDL — Base de datos del Agente de Eventos (Grupo 5)
-- Instancia: utec-eventos-lab (Cloud SQL PostgreSQL 16) · base: eventos
-- Extraído de lo DESPLEGADO. Generado 14-set-2026.
--
-- Contenido: 3 esquemas, 16 tablas, índices. Las reglas de negocio van como
-- CHECK inline en cada tabla.
--
-- NO incluido aquí (vive en schema.sql, misma carpeta):
--   · Funciones: fn_parametro, fn_motivo_no_cotizable, fn_hash_celular,
--     rag.fn_buscar, memory.fn_recordar
--   · TRIGGER validar_antes_de_cotizar en core.cotizaciones (BLOQUEA cotizar
--     si viola cobertura / anticipacion 72h / piso>3 sin ascensor)
--   · Datos semilla de core.parametros
-- Las tablas del checkpointer las crea LangGraph en runtime (PostgresSaver.setup()).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS core;

CREATE SCHEMA IF NOT EXISTS rag;

CREATE SCHEMA IF NOT EXISTS memory;

CREATE TABLE core.parametros (
  clave text NOT NULL,
  valor_num numeric,
  valor_texto text,
  descripcion text NOT NULL,
  vigente_desde timestamptz NOT NULL DEFAULT now(),
  vigente_hasta timestamptz,
  PRIMARY KEY (clave, vigente_desde),
  CHECK (valor_num IS NOT NULL
      OR valor_texto IS NOT NULL)
);

CREATE TABLE core.clientes (
  id bigserial PRIMARY KEY,
  celular_hash text NOT NULL UNIQUE,
  celular_ultimos4 char(4) NOT NULL,
  nombre text,
  creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.tipos_evento (
  id smallserial PRIMARY KEY,
  nombre text NOT NULL UNIQUE
);

CREATE TABLE core.productos (
  id bigserial PRIMARY KEY,
  sku text NOT NULL UNIQUE,
  servicio text NOT NULL CHECK (servicio IN ('barril', 'eventos', 'botellas')),
  nombre text NOT NULL,
  capacidad_l numeric CHECK (capacidad_l IS NULL
                          OR capacidad_l > 0),
  unidades integer CHECK (unidades IS NULL
                       OR unidades > 0),
  precio_base numeric(12, 2) NOT NULL CHECK (precio_base >= 0),
  moneda char(3) NOT NULL DEFAULT 'PEN',
  activo boolean NOT NULL DEFAULT TRUE
);

CREATE TABLE core.producto_evento (
  producto_id bigint NOT NULL REFERENCES core.productos (id) ON DELETE CASCADE,
  tipo_evento_id smallint NOT NULL REFERENCES core.tipos_evento (id) ON DELETE CASCADE,
  afinidad numeric NOT NULL CHECK (afinidad BETWEEN 0 AND 1),
  PRIMARY KEY (producto_id, tipo_evento_id)
);

CREATE TABLE core.cobertura (
  id bigserial PRIMARY KEY,
  distrito text NOT NULL,
  servicio text NOT NULL CHECK (servicio IN ('barril', 'eventos', 'botellas')),
  activo boolean NOT NULL DEFAULT TRUE,
  UNIQUE (distrito, servicio)
);

CREATE TABLE core.disponibilidad (
  producto_id bigint NOT NULL REFERENCES core.productos (id) ON DELETE CASCADE,
  fecha date NOT NULL,
  cupos_total integer NOT NULL CHECK (cupos_total >= 0),
  cupos_usados integer NOT NULL DEFAULT 0 CHECK (cupos_usados >= 0),
  PRIMARY KEY (producto_id, fecha),
  CHECK (cupos_usados <= cupos_total)
);

CREATE TABLE core.solicitudes (
  id bigserial PRIMARY KEY,
  cliente_id bigint NOT NULL REFERENCES core.clientes (id) ON DELETE CASCADE,
  tipo_evento_id smallint REFERENCES core.tipos_evento (id),
  servicio text NOT NULL CHECK (servicio IN ('barril', 'eventos', 'botellas')),
  asistentes integer CHECK (asistentes IS NULL
                         OR asistentes > 0),
  fecha_evento date NOT NULL,
  distrito text NOT NULL,
  piso smallint NOT NULL DEFAULT 1 CHECK (piso >= 1),
  tiene_ascensor boolean NOT NULL DEFAULT TRUE,
  presupuesto numeric(12, 2) CHECK (presupuesto IS NULL
                                 OR presupuesto >= 0),
  estado text NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta', 'cotizada', 'derivada', 'cerrada', 'abandonada')),
  thread_id text,
  creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX 
  ON core.solicitudes (cliente_id,
                       creado_en DESC);

CREATE INDEX 
  ON core.solicitudes (estado)
  WHERE estado = 'abierta';

CREATE TABLE core.cotizaciones (
  id bigserial PRIMARY KEY,
  solicitud_id bigint NOT NULL REFERENCES core.solicitudes (id) ON DELETE CASCADE,
  moneda char(3) NOT NULL DEFAULT 'PEN',
  subtotal numeric(12, 2) NOT NULL CHECK (subtotal >= 0),
  impuestos numeric(12, 2) NOT NULL CHECK (impuestos >= 0),
  total numeric(12, 2) NOT NULL,
  vigencia_hasta timestamptz NOT NULL,
  estado text NOT NULL DEFAULT 'emitida' CHECK (estado IN ('emitida', 'aceptada', 'vencida', 'anulada')),
  creado_en timestamptz NOT NULL DEFAULT now(),
  CHECK (total = (subtotal + impuestos))
);

CREATE TABLE core.cotizacion_detalle (
  id bigserial PRIMARY KEY,
  cotizacion_id bigint NOT NULL REFERENCES core.cotizaciones (id) ON DELETE CASCADE,
  producto_id bigint REFERENCES core.productos (id),
  concepto text NOT NULL,
  cantidad numeric NOT NULL CHECK (cantidad > 0),
  precio_unitario numeric(12, 2) NOT NULL CHECK (precio_unitario >= 0),
  subtotal numeric(12, 2) NOT NULL CHECK (subtotal >= 0)
);

CREATE TABLE core.derivaciones (
  id bigserial PRIMARY KEY,
  solicitud_id bigint REFERENCES core.solicitudes (id) ON DELETE CASCADE,
  cliente_id bigint NOT NULL REFERENCES core.clientes (id) ON DELETE CASCADE,
  motivo text NOT NULL,
  prioridad text NOT NULL DEFAULT 'normal' CHECK (prioridad IN ('baja', 'normal', 'alta')),
  estado text NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'tomada', 'resuelta')),
  contexto jsonb NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),
  CHECK (contexto ? 'intencion'
     AND contexto ? 'datos_capturados'
     AND contexto ? 'resumen')
);

CREATE INDEX 
  ON core.derivaciones (estado,
                        prioridad)
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
  document_id text NOT NULL REFERENCES rag.documents (document_id) ON DELETE CASCADE,
  categoria text NOT NULL,
  servicio text NOT NULL DEFAULT 'general' CHECK (servicio IN ('general', 'barril', 'eventos', 'botellas')),
  tipo_contenido text NOT NULL CHECK (tipo_contenido IN ('politica', 'faq', 'regla', 'descripcion', 'objecion', 'arquitectura')),
  texto text NOT NULL,
  embedding vector(768),
  version text NOT NULL DEFAULT '1.0',
  estado text NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'obsoleto')),
  actualizado_en timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX 
  ON rag.chunks (servicio,
                 categoria)
  WHERE estado = 'activo';

CREATE INDEX 
  ON rag.chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE memory.consentimientos (
  id bigserial PRIMARY KEY,
  cliente_id bigint NOT NULL REFERENCES core.clientes (id) ON DELETE CASCADE,
  tipo text NOT NULL CHECK (tipo IN ('obligatorio', 'promocional')),
  otorgado boolean NOT NULL,
  evidencia text NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),
  revocado_en timestamptz,
  UNIQUE (cliente_id, tipo, creado_en)
);

CREATE TABLE memory.preferencias_cliente (
  id bigserial PRIMARY KEY,
  cliente_id bigint NOT NULL REFERENCES core.clientes (id) ON DELETE CASCADE,
  consent_id bigint NOT NULL REFERENCES memory.consentimientos (id),
  categoria text NOT NULL CHECK (categoria IN ('preferencia_producto', 'restriccion_logistica', 'tipo_ocasion', 'sensibilidad_precio')),
  contenido text NOT NULL,
  embedding vector(768) NOT NULL,
  confianza text NOT NULL CHECK (confianza IN ('alta', 'media', 'baja')),
  vigente boolean NOT NULL DEFAULT TRUE,
  superseded_by bigint REFERENCES memory.preferencias_cliente (id),
  creado_en timestamptz NOT NULL DEFAULT now(),
  expira_en timestamptz DEFAULT now() + CAST('12 months' AS interval)
);

CREATE INDEX 
  ON memory.preferencias_cliente (cliente_id,
                                  vigente);

CREATE INDEX 
  ON memory.preferencias_cliente USING hnsw (embedding vector_cosine_ops);

CREATE TABLE memory.episodios (
  id bigserial PRIMARY KEY,
  cliente_id bigint REFERENCES core.clientes (id) ON DELETE CASCADE,
  thread_id text NOT NULL,
  etapa text NOT NULL CHECK (etapa IN ('inicio', 'intencion', 'recoleccion', 'cotizacion', 'aceptacion', 'derivacion', 'cierre')),
  desenlace text NOT NULL CHECK (desenlace IN ('completado', 'abandonado', 'derivado')),
  resumen text,
  creado_en timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX 
  ON memory.episodios (cliente_id,
                       creado_en DESC);
