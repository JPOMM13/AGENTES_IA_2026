-- Consultas de validacion para memoria persistente JSONB.
-- Ejecutar sobre la base eventos.

SELECT count(*) AS total_memorias
FROM memory.jpomm_memoria_cotizaciones;

SELECT id, contacto, nombre_cliente, clave_cliente, creado_en, actualizado_en
FROM memory.jpomm_memoria_cotizaciones
ORDER BY actualizado_en DESC;

SELECT contacto, estado_cotizacion
FROM memory.jpomm_memoria_cotizaciones
ORDER BY actualizado_en DESC
LIMIT 5;

SELECT
    contacto,
    nombre_cliente,
    estado_cotizacion ->> 'tipo_evento' AS tipo_evento,
    estado_cotizacion ->> 'fecha_evento' AS fecha_evento,
    estado_cotizacion ->> 'distrito' AS distrito,
    estado_cotizacion -> 'productos_solicitados' AS productos_servicios
FROM memory.jpomm_memoria_cotizaciones
ORDER BY actualizado_en DESC;

-- Reemplaza el contacto para validar una memoria puntual.
SELECT *
FROM memory.jpomm_memoria_cotizaciones
WHERE contacto = '989515182';
