-- Crea las tablas PostgreSQL para reemplazar datos_mock.py y mock_calendario_eventos.json.
-- Ejecutar sobre la base existente: eventos.
-- Schema elegido: negocio, para agrupar datos operativos de negocio del cotizador.

CREATE SCHEMA IF NOT EXISTS negocio;
SET search_path TO negocio, public;

CREATE TABLE IF NOT EXISTS jpomm_productos (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    categoria TEXT NOT NULL,
    familia TEXT NOT NULL,
    unidad TEXT NOT NULL,
    precio_unitario NUMERIC(12, 2) NOT NULL CHECK (precio_unitario >= 0),
    moneda TEXT NOT NULL DEFAULT 'PEN',
    tipos_evento TEXT[] NOT NULL DEFAULT '{}',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jpomm_paquetes (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    servicio TEXT NOT NULL,
    tipos_evento TEXT[] NOT NULL DEFAULT '{}',
    capacidad_min INTEGER NOT NULL CHECK (capacidad_min >= 0),
    capacidad_max INTEGER NOT NULL CHECK (capacidad_max >= capacidad_min),
    precio_base NUMERIC(12, 2) NOT NULL CHECK (precio_base >= 0),
    moneda TEXT NOT NULL DEFAULT 'PEN',
    imagen TEXT,
    afinidad_evento JSONB NOT NULL DEFAULT '{}'::jsonb,
    incluye TEXT[] NOT NULL DEFAULT '{}',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jpomm_paquete_productos (
    paquete_id TEXT NOT NULL REFERENCES jpomm_paquetes(id) ON DELETE CASCADE,
    item_nombre TEXT NOT NULL,
    producto_id TEXT REFERENCES jpomm_productos(id) ON DELETE SET NULL,
    orden INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (paquete_id, item_nombre)
);

CREATE TABLE IF NOT EXISTS jpomm_stock_productos (
    clave_stock TEXT PRIMARY KEY,
    producto_id TEXT NOT NULL REFERENCES jpomm_productos(id) ON DELETE CASCADE,
    fecha_evento DATE,
    stock INTEGER NOT NULL CHECK (stock >= 0),
    fuente TEXT NOT NULL DEFAULT 'mock',
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jpomm_disponibilidad_paquetes (
    paquete_id TEXT NOT NULL REFERENCES jpomm_paquetes(id) ON DELETE CASCADE,
    fecha_evento DATE NOT NULL,
    cupos INTEGER NOT NULL CHECK (cupos >= 0),
    fuente TEXT NOT NULL DEFAULT 'mock',
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (paquete_id, fecha_evento)
);

CREATE TABLE IF NOT EXISTS jpomm_categoria_alternativas (
    categoria TEXT NOT NULL,
    categoria_alternativa TEXT NOT NULL,
    prioridad INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (categoria, categoria_alternativa)
);

CREATE TABLE IF NOT EXISTS jpomm_cobertura_distritos (
    distrito TEXT PRIMARY KEY,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jpomm_rag_documentos (
    id TEXT PRIMARY KEY,
    titulo TEXT NOT NULL,
    texto TEXT NOT NULL,
    palabras_clave TEXT[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jpomm_fechas_no_disponibles (
    fecha_evento DATE PRIMARY KEY,
    motivo TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jpomm_configuracion_calendario (
    clave TEXT PRIMARY KEY,
    valor JSONB NOT NULL,
    descripcion TEXT,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS jpomm_reservas_eventos (
    id_reserva TEXT PRIMARY KEY,
    id_sesion TEXT,
    quote_id TEXT,
    nombre_cliente TEXT,
    contacto TEXT,
    tipo_evento TEXT,
    asistentes INTEGER CHECK (asistentes IS NULL OR asistentes >= 0),
    fecha_evento DATE NOT NULL,
    distrito TEXT NOT NULL,
    productos_solicitados TEXT[] NOT NULL DEFAULT '{}',
    registrado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    estado TEXT NOT NULL DEFAULT 'reservado'
);

CREATE INDEX IF NOT EXISTS idx_jpomm_productos_categoria ON jpomm_productos (categoria);
CREATE INDEX IF NOT EXISTS idx_jpomm_productos_familia ON jpomm_productos (familia);
CREATE INDEX IF NOT EXISTS idx_jpomm_productos_tipos_evento ON jpomm_productos USING GIN (tipos_evento);

CREATE INDEX IF NOT EXISTS idx_jpomm_paquetes_servicio ON jpomm_paquetes (servicio);
CREATE INDEX IF NOT EXISTS idx_jpomm_paquetes_tipos_evento ON jpomm_paquetes USING GIN (tipos_evento);
CREATE INDEX IF NOT EXISTS idx_jpomm_paquetes_capacidad ON jpomm_paquetes (capacidad_min, capacidad_max);

CREATE INDEX IF NOT EXISTS idx_jpomm_stock_producto_fecha ON jpomm_stock_productos (producto_id, fecha_evento);
CREATE INDEX IF NOT EXISTS idx_jpomm_disponibilidad_paquete_fecha ON jpomm_disponibilidad_paquetes (paquete_id, fecha_evento);
CREATE INDEX IF NOT EXISTS idx_jpomm_cobertura_activo ON jpomm_cobertura_distritos (activo);
CREATE INDEX IF NOT EXISTS idx_jpomm_rag_keywords ON jpomm_rag_documentos USING GIN (palabras_clave);
CREATE INDEX IF NOT EXISTS idx_jpomm_fechas_no_disponibles_activo ON jpomm_fechas_no_disponibles (activo);
CREATE INDEX IF NOT EXISTS idx_jpomm_reservas_fecha_distrito_estado ON jpomm_reservas_eventos (fecha_evento, distrito, estado);
CREATE INDEX IF NOT EXISTS idx_jpomm_reservas_contacto ON jpomm_reservas_eventos (contacto);
