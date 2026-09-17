# Agente de cotizaciones de eventos con Neo4j

Proyecto sencillo para la tarea de razonamiento simbolico y grafos con Neo4j.
Modela las relaciones de un agente de cotizaciones de eventos usando la
estructura propuesta: cliente, evento, fecha, lugar, cobertura, productos,
catalogo, precio, disponibilidad, cotizacion, asesor y reglas de negocio.

## Requisitos

- Podman Desktop o Docker Desktop.
- Python 3.10 o superior.

## 1. Levantar Neo4j con Podman

Desde esta carpeta:

```bash
podman compose up -d
podman ps
```

Neo4j quedara disponible en:

- Browser: <http://localhost:7474>
- Bolt: `bolt://localhost:7687`
- Usuario: `neo4j`
- Password: `password`

Si tu instalacion usa `podman-compose`, ejecuta:

```bash
podman-compose up -d
```

## 2. Cargar la base de conocimiento visual del agente cotizador

Esta es la parte equivalente al ejemplo del profesor: no es solo un diagrama,
sino una base con instancias concretas y relaciones con significado de negocio.

Para una visualizacion parecida al ejemplo del profesor en Neo4j Browser, carga
esta version compacta. Es el archivo recomendado para la presentacion:

```bash
podman exec -i neo4j_eventos cypher-shell -u neo4j -p password < data/cotizador_browser_profesor.cypher
```

Luego en Neo4j Browser ejecuta:

```cypher
MATCH p=(:NodoCotizador)-[:COTIZA]->(:NodoCotizador)
RETURN p;
```

Esa vista usa una relacion principal `COTIZA`, similar a como el ejemplo del
profesor usa `YAPEO`. El significado de cada enlace esta en la propiedad
`tipo`: `DESCRIBE`, `REQUIERE`, `GENERA_COTIZACION`, `INCUMPLE`, etc.

Validacion esperada despues de cargar:

```cypher
MATCH (n)
RETURN labels(n) AS labels, count(n) AS total
ORDER BY total DESC;
```

Debe mostrar 5 productos, 3 clientes, 3 eventos, 3 lugares, 3 cotizaciones, 3
reglas y 2 asesores.

```cypher
MATCH ()-[r]->()
RETURN type(r) AS relacion, r.tipo AS tipo, count(r) AS total
ORDER BY total DESC;
```

Debe mostrar 26 relaciones `COTIZA`.

Si quieres cargar el modelo mas normalizado, usa:

```bash
podman exec -i neo4j_eventos cypher-shell -u neo4j -p password < data/eventos_cotizaciones.cypher
```

Verificacion rapida:

```bash
podman exec -it neo4j_eventos cypher-shell -u neo4j -p password "MATCH (n) RETURN labels(n) AS etiquetas, count(*) AS total ORDER BY total DESC"
podman exec -it neo4j_eventos cypher-shell -u neo4j -p password "MATCH ()-[r]->() RETURN type(r) AS relacion, count(*) AS total ORDER BY total DESC"
```

## 3. Preparar Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

En Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

## 4. Ejecutar el analisis

```bash
python src/consultas.py
```

El script imprime:

- conteo de nodos por etiqueta;
- conteo de relaciones;
- eventos con cliente, fecha, lugar y cotizacion;
- riesgos por disponibilidad;
- riesgos por cobertura;
- comparacion entre total calculado y total cotizado.

Tambien puedes ejecutar las tools simbolicas del agente cotizador:

```bash
python src/tools_cotizaciones.py
```

Estas tools cumplen el mismo rol conceptual que las tools del ejemplo del
profesor: encapsulan consultas Cypher para que el agente responda usando datos
del grafo.

## 5. Verlo visualmente en Neo4j Browser, como el profesor

Abre:

<http://localhost:7474/browser/>

Usuario:

```text
neo4j
```

Password:

```text
password
```

Ejecuta esta consulta para ver la red completa de instancias:

```cypher
MATCH p=()-[]->()
RETURN p
LIMIT 80;
```

Para ver el flujo principal del agente cotizador:

```cypher
MATCH p=(c:Cliente)-[:DESCRIBE]->(e:Evento)-[]->()
RETURN p
UNION
MATCH p=(e:Evento)-[:REQUIERE]->(pdt:Producto)-[]->()
RETURN p
UNION
MATCH p=(e:Evento)-[:SI_CUMPLE_TIENE]->(q:Cotizacion)-[]->()
RETURN p;
```

Para ver el razonamiento simbolico sobre disponibilidad:

```cypher
MATCH p=(e:Evento)-[:REQUIERE]->(pdt:Producto)-[:TIENE_DISPONIBILIDAD]->(d:Disponibilidad)
WHERE d.estado <> "Disponible"
RETURN p;
```

Para ver el razonamiento simbolico sobre cobertura:

```cypher
MATCH p=(e:Evento)-[:ES_EN_LUGAR]->(l:Lugar)-[:TIENE_COBERTURA]->(c:Cobertura)
WHERE c.estado <> "Activa"
RETURN p;
```

Tambien deje estas consultas listas en:

```text
data/consultas_browser.cypher
```

La validacion contra la premisa del ZIP del profesor esta documentada en:

```text
docs/VALIDACION_PREMISA_PROFESOR.md
```

## 6. Generar una visualizacion HTML conceptual

```bash
python src/visualizar.py
```

Se generara el archivo:

```text
docs/grafo_eventos.html
```

Esta visualizacion es complementaria. Sirve para el reporte porque representa el
modelo conceptual como en el diagrama base, pero la vista equivalente al ejemplo
del profesor es la de Neo4j Browser usando la base cargada en
`data/eventos_cotizaciones.cypher`.

Abre ese HTML en el navegador. Si quieres verlo desde una URL local:

```bash
python3 -m http.server 8000
```

Luego entra a <http://localhost:8000/docs/grafo_eventos.html>.

Si tambien quieres ver las instancias reales cargadas en Neo4j:

```bash
python src/visualizar.py --datos
```

Ese comando genera:

```text
docs/grafo_eventos_datos.html
```

## 7. Consultas Cypher utiles adicionales

Ver todo el grafo con relaciones:

```cypher
MATCH p=()-[]->()
RETURN p;
```

Eventos con productos requeridos:

```cypher
MATCH p=(c:Cliente)-[:DESCRIBE]->(:Evento)-[:REQUIERE]->(:Producto)
RETURN p;
```

Productos con problemas de disponibilidad:

```cypher
MATCH p=(:Evento)-[:REQUIERE]->(:Producto)-[:TIENE_DISPONIBILIDAD]->(d:Disponibilidad)
WHERE d.estado <> "Disponible"
RETURN p;
```

Eventos con cobertura condicionada:

```cypher
MATCH p=(:Evento)-[:ES_EN_LUGAR]->(:Lugar)-[:TIENE_COBERTURA]->(c:Cobertura)
WHERE c.estado <> "Activa"
RETURN p;
```

## 8. Apagar Neo4j

```bash
podman compose down
```

Si quieres borrar tambien la data local:

```bash
podman compose down -v
rm -rf neo4j
```
