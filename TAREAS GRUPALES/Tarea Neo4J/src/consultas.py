from neo4j_client import run_read


def imprimir_titulo(texto):
    print("\n" + "=" * 80)
    print(texto)
    print("=" * 80)


def listar_resumen_del_grafo():
    imprimir_titulo("Resumen de nodos por etiqueta")
    rows = run_read(
        """
        MATCH (n)
        UNWIND labels(n) AS etiqueta
        RETURN etiqueta, count(*) AS total
        ORDER BY total DESC, etiqueta
        """
    )
    for row in rows:
        print(f"{row['etiqueta']}: {row['total']}")

    imprimir_titulo("Resumen de relaciones")
    rows = run_read(
        """
        MATCH ()-[r]->()
        RETURN type(r) AS relacion, count(*) AS total
        ORDER BY total DESC, relacion
        """
    )
    for row in rows:
        print(f"{row['relacion']}: {row['total']}")


def analizar_cotizaciones():
    imprimir_titulo("Eventos, cliente, lugar y cotizacion")
    rows = run_read(
        """
        MATCH (c:Cliente)-[:DESCRIBE]->(e:Evento)-[:ES_EN_LUGAR]->(l:Lugar)
        MATCH (e)-[:ES_EN_FECHA]->(f:Fecha)
        MATCH (e)-[:SI_CUMPLE_TIENE]->(q:Cotizacion)
        RETURN c.nombre AS cliente, e.nombre AS evento, e.asistentes AS asistentes,
               l.nombre AS lugar, l.distrito AS distrito, f.valor AS fecha,
               q.estado AS estadoCotizacion, q.total AS total
        ORDER BY fecha
        """
    )
    for row in rows:
        print(
            f"- {row['cliente']} solicita '{row['evento']}' para {row['asistentes']} "
            f"asistentes en {row['lugar']} ({row['distrito']}) el {row['fecha']}. "
            f"Cotizacion: {row['estadoCotizacion']} por S/ {row['total']}."
        )


def detectar_riesgos():
    imprimir_titulo("Productos no disponibles o limitados")
    rows = run_read(
        """
        MATCH (e:Evento)-[req:REQUIERE]->(p:Producto)-[:TIENE_DISPONIBILIDAD]->(d:Disponibilidad)
        WHERE d.estado <> "Disponible"
        RETURN e.nombre AS evento, p.nombre AS producto, req.cantidad AS cantidad,
               d.estado AS disponibilidad, d.stock AS stock
        ORDER BY evento, producto
        """
    )
    if not rows:
        print("No se encontraron productos con riesgo de disponibilidad.")
    for row in rows:
        print(
            f"- {row['evento']} requiere {row['cantidad']} de '{row['producto']}', "
            f"pero su estado es {row['disponibilidad']} con stock {row['stock']}."
        )

    imprimir_titulo("Cobertura operativa condicionada")
    rows = run_read(
        """
        MATCH (e:Evento)-[:ES_EN_LUGAR]->(l:Lugar)-[:TIENE_COBERTURA]->(c:Cobertura)
        WHERE c.estado <> "Activa"
        RETURN e.nombre AS evento, l.nombre AS lugar, l.distrito AS distrito,
               c.nombre AS cobertura, c.estado AS estado
        """
    )
    if not rows:
        print("Todos los eventos estan dentro de cobertura activa.")
    for row in rows:
        print(
            f"- {row['evento']} sera en {row['lugar']} ({row['distrito']}), "
            f"cobertura {row['cobertura']} en estado {row['estado']}."
        )


def calcular_totales_por_evento():
    imprimir_titulo("Total calculado desde productos")
    rows = run_read(
        """
        MATCH (e:Evento)-[req:REQUIERE]->(p:Producto)-[:TIENE_PRECIO]->(pr:Precio)
        WITH e, sum(req.cantidad * pr.monto) AS totalCalculado
        MATCH (e)-[:SI_CUMPLE_TIENE]->(q:Cotizacion)
        RETURN e.nombre AS evento, totalCalculado, q.total AS totalCotizado,
               q.total - totalCalculado AS diferencia
        ORDER BY evento
        """
    )
    for row in rows:
        print(
            f"- {row['evento']}: total calculado S/ {row['totalCalculado']}, "
            f"total registrado S/ {row['totalCotizado']}, diferencia S/ {row['diferencia']}."
        )


if __name__ == "__main__":
    listar_resumen_del_grafo()
    analizar_cotizaciones()
    detectar_riesgos()
    calcular_totales_por_evento()
