// 1. Vista general parecida al ejemplo del profesor.
// Muestra clientes, eventos, productos, precios, disponibilidad,
// cobertura, cotizaciones y asesores conectados.
MATCH p=()-[]->()
RETURN p
LIMIT 80;

// 2. Flujo principal del agente cotizador:
// cliente describe evento, evento requiere productos,
// productos tienen precio/disponibilidad, evento genera cotizacion.
MATCH p=(c:Cliente)-[:DESCRIBE]->(e:Evento)-[]->()
RETURN p
UNION
MATCH p=(e:Evento)-[:REQUIERE]->(pdt:Producto)-[]->()
RETURN p
UNION
MATCH p=(e:Evento)-[:SI_CUMPLE_TIENE]->(q:Cotizacion)-[]->()
RETURN p;

// 3. Razonamiento simbolico: productos que bloquean o condicionan cotizaciones.
MATCH p=(e:Evento)-[:REQUIERE]->(pdt:Producto)-[:TIENE_DISPONIBILIDAD]->(d:Disponibilidad)
WHERE d.estado <> "Disponible"
RETURN p;

// 4. Razonamiento simbolico: eventos fuera de cobertura activa.
MATCH p=(e:Evento)-[:ES_EN_LUGAR]->(l:Lugar)-[:TIENE_COBERTURA]->(c:Cobertura)
WHERE c.estado <> "Activa"
RETURN p;

// 5. Explicacion de una cotizacion observada de inicio a fin.
MATCH p=(cliente:Cliente {nombre: "Startup Andina"})-[:DESCRIBE]->(:Evento)-[]->()
RETURN p
UNION
MATCH p=(:Evento {nombre: "Demo Day"})-[:REQUIERE]->(:Producto)-[]->()
RETURN p
UNION
MATCH p=(:Evento {nombre: "Demo Day"})-[:SI_CUMPLE_TIENE]->(:Cotizacion)-[]->()
RETURN p;
