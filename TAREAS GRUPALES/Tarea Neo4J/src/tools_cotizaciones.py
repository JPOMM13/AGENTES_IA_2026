"""
Tools sencillas para consultar la base de conocimiento del agente cotizador.

Modelo principal:
    (:Cliente)-[:DESCRIBE]->(:Evento)
    (:Evento)-[:REQUIERE {cantidad}]->(:Producto)
    (:Producto)-[:TIENE_PRECIO]->(:Precio)
    (:Producto)-[:TIENE_DISPONIBILIDAD]->(:Disponibilidad)
    (:Evento)-[:ES_EN_LUGAR]->(:Lugar)-[:TIENE_COBERTURA]->(:Cobertura)
    (:Evento)-[:SI_CUMPLE_TIENE]->(:Cotizacion)

Estas funciones representan la capa simbolica: el agente no inventa la respuesta,
consulta el grafo y explica con relaciones concretas.
"""

from neo4j_client import run_read


def buscar_evento(texto, limit=10):
    """Busca eventos por nombre, tipo o estado."""
    return run_read(
        """
        MATCH (e:Evento)
        WHERE toLower(e.nombre) CONTAINS toLower($texto)
           OR toLower(e.tipo) CONTAINS toLower($texto)
           OR toLower(e.estado) CONTAINS toLower($texto)
        RETURN e.id AS id, e.nombre AS evento, e.tipo AS tipo,
               e.asistentes AS asistentes, e.estado AS estado
        ORDER BY e.nombre
        LIMIT $limit
        """,
        texto=texto,
        limit=limit,
    )


def detalle_cotizacion(evento):
    """Explica una cotizacion desde cliente, fecha, lugar, cobertura y asesor."""
    return run_read(
        """
        MATCH (c:Cliente)-[:DESCRIBE]->(e:Evento)
        MATCH (e)-[:ES_EN_FECHA]->(f:Fecha)
        MATCH (e)-[:ES_EN_LUGAR]->(l:Lugar)-[:TIENE_COBERTURA]->(cov:Cobertura)
        MATCH (e)-[:SI_CUMPLE_TIENE]->(q:Cotizacion)-[:CIERRE_DE_PROPUESTA]->(a:Asesor)
        WHERE toLower(e.nombre) CONTAINS toLower($evento)
        RETURN c.nombre AS cliente, e.nombre AS evento, e.tipo AS tipo,
               e.asistentes AS asistentes, f.nombre AS fecha,
               l.nombre AS lugar, l.distrito AS distrito,
               cov.nombre AS cobertura, cov.estado AS estadoCobertura,
               q.nombre AS cotizacion, q.estado AS estadoCotizacion,
               q.total AS total, q.moneda AS moneda,
               a.nombre AS asesor
        ORDER BY e.nombre
        """,
        evento=evento,
    )


def productos_de_evento(evento):
    """Lista los productos requeridos por un evento con cantidad, precio y disponibilidad."""
    return run_read(
        """
        MATCH (e:Evento)-[req:REQUIERE]->(p:Producto)
        MATCH (p)-[:TIENE_PRECIO]->(precio:Precio)
        MATCH (p)-[:TIENE_DISPONIBILIDAD]->(disp:Disponibilidad)
        MATCH (p)-[:SALE_DE]->(cat:Catalogo)
        WHERE toLower(e.nombre) CONTAINS toLower($evento)
        RETURN e.nombre AS evento, p.nombre AS producto, cat.nombre AS catalogo,
               req.cantidad AS cantidad, precio.nombre AS precio,
               precio.monto AS montoUnitario, disp.nombre AS disponibilidad,
               disp.estado AS estadoDisponibilidad, disp.stock AS stock
        ORDER BY producto
        """,
        evento=evento,
    )


def riesgos_de_cotizacion():
    """Detecta eventos con productos no disponibles/limitados o cobertura no activa."""
    return run_read(
        """
        MATCH (e:Evento)
        OPTIONAL MATCH (e)-[:REQUIERE]->(p:Producto)-[:TIENE_DISPONIBILIDAD]->(d:Disponibilidad)
        WHERE d.estado <> "Disponible"
        WITH e, collect({
            tipo: "Disponibilidad",
            detalle: p.nombre + " esta " + d.estado,
            severidad: CASE d.estado WHEN "No disponible" THEN "Alta" ELSE "Media" END
        }) AS riesgosProducto
        OPTIONAL MATCH (e)-[:ES_EN_LUGAR]->(l:Lugar)-[:TIENE_COBERTURA]->(c:Cobertura)
        WHERE c.estado <> "Activa"
        WITH e, riesgosProducto + collect({
            tipo: "Cobertura",
            detalle: l.nombre + " tiene cobertura " + c.estado,
            severidad: "Media"
        }) AS riesgos
        UNWIND riesgos AS riesgo
        WITH e, riesgo
        WHERE riesgo.detalle IS NOT NULL
        RETURN e.nombre AS evento, e.estado AS estadoEvento,
               riesgo.tipo AS tipoRiesgo, riesgo.detalle AS detalle,
               riesgo.severidad AS severidad
        ORDER BY evento, severidad DESC
        """
    )


def eventos_bloqueados_por_producto(producto):
    """Encuentra que eventos dependen de un producto especifico."""
    return run_read(
        """
        MATCH (e:Evento)-[req:REQUIERE]->(p:Producto)-[:TIENE_DISPONIBILIDAD]->(d:Disponibilidad)
        WHERE toLower(p.nombre) CONTAINS toLower($producto)
        RETURN p.nombre AS producto, d.estado AS disponibilidad,
               e.nombre AS evento, req.cantidad AS cantidad, e.estado AS estadoEvento
        ORDER BY evento
        """,
        producto=producto,
    )


def total_calculado_por_evento():
    """Calcula el total esperado desde las relaciones REQUIERE y TIENE_PRECIO."""
    return run_read(
        """
        MATCH (e:Evento)-[req:REQUIERE]->(p:Producto)-[:TIENE_PRECIO]->(precio:Precio)
        WITH e, sum(req.cantidad * precio.monto) AS totalCalculado
        MATCH (e)-[:SI_CUMPLE_TIENE]->(q:Cotizacion)
        RETURN e.nombre AS evento, totalCalculado,
               q.total AS totalCotizado,
               q.total - totalCalculado AS diferencia,
               q.estado AS estadoCotizacion
        ORDER BY evento
        """
    )


if __name__ == "__main__":
    print("Riesgos detectados:")
    for row in riesgos_de_cotizacion():
        print(row)
