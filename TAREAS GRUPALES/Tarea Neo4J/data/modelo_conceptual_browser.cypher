MATCH (n:ModeloConceptual) DETACH DELETE n;

CREATE
  (reglas:ModeloConceptual:ReglasNegocio {
    id: "modelo-reglas",
    nombre: "Reglas Negocio",
    orden: 1
  }),
  (fecha:ModeloConceptual:Fecha {
    id: "modelo-fecha",
    nombre: "Fecha",
    orden: 2
  }),
  (cliente:ModeloConceptual:Cliente {
    id: "modelo-cliente",
    nombre: "Cliente",
    orden: 3
  }),
  (evento:ModeloConceptual:Evento {
    id: "modelo-evento",
    nombre: "Evento",
    orden: 4
  }),
  (lugar:ModeloConceptual:Lugar {
    id: "modelo-lugar",
    nombre: "Lugar",
    orden: 5
  }),
  (cobertura:ModeloConceptual:Cobertura {
    id: "modelo-cobertura",
    nombre: "Cobertura",
    orden: 6
  }),
  (producto:ModeloConceptual:Producto {
    id: "modelo-producto",
    nombre: "Producto",
    orden: 7
  }),
  (catalogo:ModeloConceptual:Catalogo {
    id: "modelo-catalogo",
    nombre: "Catalogo",
    orden: 8
  }),
  (precio:ModeloConceptual:Precio {
    id: "modelo-precio",
    nombre: "Precio",
    orden: 9
  }),
  (disponibilidad:ModeloConceptual:Disponibilidad {
    id: "modelo-disponibilidad",
    nombre: "Disponibilidad",
    orden: 10
  }),
  (cotizacion:ModeloConceptual:Cotizacion {
    id: "modelo-cotizacion",
    nombre: "Cotizacion",
    orden: 11
  }),
  (asesor:ModeloConceptual:Asesor {
    id: "modelo-asesor",
    nombre: "Asesor",
    orden: 12
  }),
  (cliente)-[:DESCRIBE_UN]->(evento),
  (evento)-[:ES_EN_UNA]->(fecha),
  (fecha)-[:DEBE_CUMPLIR]->(reglas),
  (evento)-[:ES_EN_UN]->(lugar),
  (lugar)-[:TIENE_UNA]->(cobertura),
  (evento)-[:REQUIERE_UN]->(producto),
  (producto)-[:SALE_DE_UN]->(catalogo),
  (producto)-[:TIENE_UN]->(precio),
  (producto)-[:TIENE_UNA]->(disponibilidad),
  (evento)-[:SI_CUMPLE_TIENE_UNA]->(cotizacion),
  (cotizacion)-[:CIERRE_DE_LA_PROPUESTA]->(asesor);
