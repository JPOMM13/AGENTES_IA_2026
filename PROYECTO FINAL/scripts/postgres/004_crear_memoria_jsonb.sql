-- Crea memoria persistente tipo NoSQL en PostgreSQL para reemplazar mock_session_memory.json.
-- Ejecutar sobre la base existente: eventos.

CREATE SCHEMA IF NOT EXISTS memory;

CREATE TABLE IF NOT EXISTS memory.jpomm_memoria_cotizaciones (
    id BIGSERIAL PRIMARY KEY,
    contacto TEXT NOT NULL,
    nombre_cliente TEXT,
    clave_cliente TEXT NOT NULL,
    estado_cotizacion JSONB NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_jpomm_memoria_cotizaciones_contacto
    ON memory.jpomm_memoria_cotizaciones (contacto);

CREATE INDEX IF NOT EXISTS idx_jpomm_memoria_cotizaciones_nombre_cliente
    ON memory.jpomm_memoria_cotizaciones (nombre_cliente);

CREATE INDEX IF NOT EXISTS idx_jpomm_memoria_cotizaciones_clave_cliente
    ON memory.jpomm_memoria_cotizaciones (clave_cliente);

CREATE INDEX IF NOT EXISTS idx_jpomm_memoria_cotizaciones_actualizado_en
    ON memory.jpomm_memoria_cotizaciones (actualizado_en DESC);

CREATE INDEX IF NOT EXISTS idx_jpomm_memoria_cotizaciones_estado_gin
    ON memory.jpomm_memoria_cotizaciones USING GIN (estado_cotizacion);

CREATE OR REPLACE FUNCTION memory.jpomm_actualizar_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.actualizado_en = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_jpomm_memoria_cotizaciones_actualizado
ON memory.jpomm_memoria_cotizaciones;

CREATE TRIGGER trg_jpomm_memoria_cotizaciones_actualizado
BEFORE UPDATE ON memory.jpomm_memoria_cotizaciones
FOR EACH ROW
EXECUTE FUNCTION memory.jpomm_actualizar_timestamp();
