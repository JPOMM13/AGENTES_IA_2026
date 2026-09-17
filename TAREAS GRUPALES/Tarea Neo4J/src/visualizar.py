import argparse
import html
import json
from pathlib import Path


OUTPUT_SCHEMA = Path("docs/grafo_eventos.html")
OUTPUT_DATA = Path("docs/grafo_eventos_datos.html")

BLUE = {
    "background": "#dbeafe",
    "border": "#6b8fc9",
    "highlight": {"background": "#bfdbfe", "border": "#4169a8"},
}
WHITE = {
    "background": "#ffffff",
    "border": "#111111",
    "highlight": {"background": "#f8fafc", "border": "#111111"},
}
YELLOW = {
    "background": "#fff3bf",
    "border": "#d6b84d",
    "highlight": {"background": "#ffe899", "border": "#b99522"},
}


def main():
    parser = argparse.ArgumentParser(
        description="Genera la visualizacion del grafo de cotizaciones de eventos."
    )
    parser.add_argument(
        "--datos",
        action="store_true",
        help="Dibuja las instancias reales cargadas en Neo4j en vez del modelo conceptual.",
    )
    args = parser.parse_args()

    if args.datos:
        html_doc = build_data_graph_html()
        write_output(OUTPUT_DATA, html_doc)
    else:
        html_doc = build_schema_graph_html()
        write_output(OUTPUT_SCHEMA, html_doc)


def write_output(path, html_doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_doc, encoding="utf-8")
    print(f"Visualizacion generada en {path.resolve()}")


def build_schema_graph_html():
    nodes = [
        node("reglas", "Reglas Negocio", -520, -250, BLUE),
        node("fecha", "Fecha", -180, -150, WHITE),
        node("cliente", "Cliente", -420, 50, WHITE),
        node("evento", "Evento", 0, 50, YELLOW),
        node("lugar", "Lugar", 320, -150, WHITE),
        node("cobertura", "Cobertura", 650, -270, BLUE),
        node("producto", "Producto", 320, 280, WHITE),
        node("catalogo", "Catalogo", 650, 110, BLUE),
        node("precio", "Precio", 650, 360, BLUE),
        node("disponibilidad", "Disponibilidad", 320, 480, BLUE),
        node("cotizacion", "Cotizacion", -180, 280, WHITE),
        node("asesor", "Asesor", -180, 520, WHITE),
    ]
    edges = [
        edge("cliente", "evento", "Describe un"),
        edge("evento", "fecha", "es en una"),
        edge("fecha", "reglas", "debe cumplir"),
        edge("evento", "lugar", "es en un"),
        edge("lugar", "cobertura", "tiene una"),
        edge("evento", "producto", "requiere un"),
        edge("producto", "catalogo", "sale de un"),
        edge("producto", "precio", "tiene un"),
        edge("producto", "disponibilidad", "Tiene una"),
        edge("evento", "cotizacion", "si cumple tiene una"),
        edge("cotizacion", "asesor", "cierre de la propuesta"),
    ]
    return build_html(
        title="Modelo de relaciones para cotizaciones de eventos",
        subtitle="Visualizacion conceptual basada en la estructura propuesta para el agente.",
        nodes=nodes,
        edges=edges,
        fixed=True,
    )


def node(node_id, label, x, y, color):
    return {
        "id": node_id,
        "label": label,
        "x": x,
        "y": y,
        "fixed": True,
        "shape": "box",
        "color": color,
        "widthConstraint": {"minimum": 165, "maximum": 185},
        "heightConstraint": {"minimum": 72},
        "font": {"size": 21, "face": "Arial", "color": "#111827"},
        "margin": {"top": 18, "right": 18, "bottom": 18, "left": 18},
    }


def edge(source, target, label):
    return {
        "from": source,
        "to": target,
        "label": label,
        "arrows": {"to": {"enabled": True, "scaleFactor": 0.9}},
        "font": {
            "size": 17,
            "face": "Arial",
            "align": "middle",
            "background": "rgba(255,255,255,0.92)",
        },
        "color": {"color": "#111111", "highlight": "#111111"},
        "width": 1.5,
        "smooth": {"enabled": False},
    }


def build_data_graph_html():
    from neo4j_client import run_read

    rows = run_read(
        """
        MATCH (a)-[r]->(b)
        RETURN elementId(a) AS sourceId,
               labels(a) AS sourceLabels,
               coalesce(a.nombre, toString(a.valor), a.id, "Nodo") AS sourceName,
               elementId(b) AS targetId,
               labels(b) AS targetLabels,
               coalesce(b.nombre, toString(b.valor), b.id, "Nodo") AS targetName,
               type(r) AS relation
        ORDER BY relation
        """
    )

    nodes = {}
    edges = []
    for row in rows:
        add_data_node(nodes, row["sourceId"], row["sourceLabels"], row["sourceName"])
        add_data_node(nodes, row["targetId"], row["targetLabels"], row["targetName"])
        edges.append(edge(row["sourceId"], row["targetId"], row["relation"]))

    return build_html(
        title="Instancias reales del grafo de cotizaciones",
        subtitle="Nodos y relaciones cargados en Neo4j desde data/eventos_cotizaciones.cypher.",
        nodes=list(nodes.values()),
        edges=edges,
        fixed=False,
    )


def add_data_node(nodes, node_id, labels, name):
    main_label = labels[0] if labels else "Nodo"
    nodes[node_id] = {
        "id": node_id,
        "label": str(name),
        "title": f"{main_label}: {html.escape(str(name))}",
        "shape": "box",
        "color": color_for_label(main_label),
        "font": {"size": 14, "face": "Arial"},
        "margin": 10,
    }


def color_for_label(label):
    if label == "Evento":
        return YELLOW
    if label in {"Cobertura", "Catalogo", "Precio", "Disponibilidad", "ReglaNegocio"}:
        return BLUE
    return WHITE


def build_html(title, subtitle, nodes, edges, fixed):
    physics = (
        "false"
        if fixed
        else "{ stabilization: true, barnesHut: { gravitationalConstant: -9000, springLength: 180 } }"
    )
    interaction = (
        "{ dragNodes: false, zoomView: true, dragView: true }"
        if fixed
        else "{ zoomView: true, dragView: true }"
    )
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>{html.escape(title)}</title>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #111827; background: #ffffff; }}
    header {{ padding: 16px 24px; border-bottom: 1px solid #d9e2ec; }}
    h1 {{ font-size: 22px; margin: 0 0 4px; }}
    p {{ margin: 0; color: #52606d; font-size: 15px; }}
    #network {{ height: calc(100vh - 78px); width: 100vw; }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(title)}</h1>
    <p>{html.escape(subtitle)}</p>
  </header>
  <main id="network"></main>
  <script>
    const nodes = new vis.DataSet({json.dumps(nodes, ensure_ascii=False)});
    const edges = new vis.DataSet({json.dumps(edges, ensure_ascii=False)});
    const container = document.getElementById("network");
    const options = {{
      layout: {{ improvedLayout: false }},
      physics: {physics},
      interaction: {interaction},
      edges: {{ chosen: false }},
      nodes: {{ borderWidth: 1.5, shapeProperties: {{ borderRadius: 8 }} }}
    }};
    const network = new vis.Network(container, {{ nodes, edges }}, options);
    network.once("afterDrawing", () => network.fit({{ animation: false, minZoomLevel: 0.55, maxZoomLevel: 1.2 }}));
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
