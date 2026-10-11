-- Consultas de validacion para confirmar que PostgreSQL quedo cargado.
-- Ejecutar sobre la base eventos. Las tablas viven en el schema negocio.

SET search_path TO negocio, public;

SELECT 'productos' AS tabla, count(*) AS total FROM jpomm_productos;
SELECT id, nombre, categoria, familia, precio_unitario, tipos_evento FROM jpomm_productos ORDER BY id;

SELECT 'paquetes' AS tabla, count(*) AS total FROM jpomm_paquetes;
SELECT id, nombre, servicio, capacidad_min, capacidad_max, precio_base, tipos_evento FROM jpomm_paquetes ORDER BY id;

SELECT 'paquete_productos' AS tabla, count(*) AS total FROM jpomm_paquete_productos;
SELECT paquete_id, item_nombre, producto_id, orden FROM jpomm_paquete_productos ORDER BY paquete_id, orden;

SELECT 'stock_productos' AS tabla, count(*) AS total FROM jpomm_stock_productos;
SELECT producto_id, fecha_evento, stock FROM jpomm_stock_productos ORDER BY producto_id, fecha_evento NULLS FIRST;

SELECT 'disponibilidad_paquetes' AS tabla, count(*) AS total FROM jpomm_disponibilidad_paquetes;
SELECT paquete_id, fecha_evento, cupos FROM jpomm_disponibilidad_paquetes ORDER BY fecha_evento, paquete_id;

SELECT 'cobertura_distritos' AS tabla, count(*) AS total FROM jpomm_cobertura_distritos WHERE activo = true;
SELECT distrito FROM jpomm_cobertura_distritos WHERE activo = true ORDER BY distrito;

SELECT 'rag_documentos' AS tabla, count(*) AS total FROM jpomm_rag_documentos WHERE activo = true;
SELECT id, titulo, palabras_clave FROM jpomm_rag_documentos WHERE activo = true ORDER BY id;

SELECT 'fechas_no_disponibles' AS tabla, count(*) AS total FROM jpomm_fechas_no_disponibles WHERE activo = true;
SELECT fecha_evento, motivo FROM jpomm_fechas_no_disponibles WHERE activo = true ORDER BY fecha_evento;

SELECT 'configuracion_calendario' AS tabla, count(*) AS total FROM jpomm_configuracion_calendario;
SELECT clave, valor FROM jpomm_configuracion_calendario ORDER BY clave;

SELECT 'reservas_eventos' AS tabla, count(*) AS total FROM jpomm_reservas_eventos;
SELECT id_reserva, contacto, fecha_evento, distrito, estado FROM jpomm_reservas_eventos ORDER BY registrado_en;

-- Validacion puntual de cruce de agenda: cada fecha/distrito no debe superar la capacidad configurada.
WITH capacidad AS (
    SELECT COALESCE((valor ->> 'valor')::int, 1) AS max_eventos
    FROM jpomm_configuracion_calendario
    WHERE clave = 'MAX_EVENTOS_POR_DISTRITO_DIA'
),
reservas AS (
    SELECT fecha_evento, lower(trim(distrito)) AS distrito, count(*) AS total
    FROM jpomm_reservas_eventos
    WHERE estado IN ('reservado', 'confirmado')
    GROUP BY fecha_evento, lower(trim(distrito))
)
SELECT reservas.fecha_evento, reservas.distrito, reservas.total, capacidad.max_eventos,
       reservas.total <= capacidad.max_eventos AS dentro_de_capacidad
FROM reservas
CROSS JOIN capacidad
ORDER BY reservas.fecha_evento, reservas.distrito;
