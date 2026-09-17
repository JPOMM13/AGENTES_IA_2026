// ============================================================
//  GRAFO VISUAL DEL AGENTE COTIZADOR — estilo profesor
//
//  Archivo recomendado para Neo4j Browser.
//  Limpia la base y crea una red compacta con instancias concretas.
//
//  Premisa:
//    (:Cuenta)-[:YAPEO {fecha, monto, operacion}]->(:Cuenta)
//
//  Adaptacion:
//    (:Cliente|Evento|Producto|Lugar|Cotizacion|Asesor|Regla)
//      -[:COTIZA {tipo, detalle}]->
//    (:Cliente|Evento|Producto|Lugar|Cotizacion|Asesor|Regla)
// ============================================================

MATCH (n) DETACH DELETE n;

CREATE
  (acme:Cliente {id:"cli-acme", nombre:"ACME Peru", tipo:"Empresa"}),
  (ramos:Cliente {id:"cli-ramos", nombre:"Familia Ramos", tipo:"Persona"}),
  (startup:Cliente {id:"cli-startup", nombre:"Startup Andina", tipo:"Empresa"}),

  (lanzamiento:Evento {id:"evt-lanzamiento", nombre:"Lanzamiento de producto", tipo:"Corporativo", asistentes:110, estado:"Emitible"}),
  (boda:Evento {id:"evt-boda", nombre:"Boda Ramos", tipo:"Social", asistentes:75, estado:"Pendiente"}),
  (demo:Evento {id:"evt-demo", nombre:"Demo Day", tipo:"Corporativo", asistentes:160, estado:"Observado"}),

  (miraflores:Lugar {id:"lugar-miraflores", nombre:"Salon Miraflores", distrito:"Miraflores", cobertura:"Activa"}),
  (surco:Lugar {id:"lugar-surco", nombre:"Casa Surco", distrito:"Santiago de Surco", cobertura:"Activa"}),
  (chosica:Lugar {id:"lugar-chosica", nombre:"Club Chosica", distrito:"Chosica", cobertura:"Condicionada"}),

  (sonido:Producto {id:"prod-sonido", nombre:"Sistema de sonido profesional", categoria:"Audio", precio:1800, disponibilidad:"Disponible"}),
  (luces:Producto {id:"prod-luces", nombre:"Luces LED ambientales", categoria:"Iluminacion", precio:950, disponibilidad:"Disponible"}),
  (mesas:Producto {id:"prod-mesas", nombre:"Pack mesas y sillas", categoria:"Mobiliario", precio:1200, disponibilidad:"Limitado"}),
  (buffet:Producto {id:"prod-buffet", nombre:"Buffet ejecutivo", categoria:"Catering", precio:95, disponibilidad:"Disponible"}),
  (cocteles:Producto {id:"prod-cocteles", nombre:"Bar de cocteles", categoria:"Bebidas", precio:2400, disponibilidad:"No disponible"}),

  (cot1:Cotizacion {id:"cot-001", nombre:"COT-001 Emitida", estado:"Emitida", total:13200, moneda:"PEN"}),
  (cot2:Cotizacion {id:"cot-002", nombre:"COT-002 Pendiente", estado:"Pendiente", total:8325, moneda:"PEN"}),
  (cot3:Cotizacion {id:"cot-003", nombre:"COT-003 Observada", estado:"Observada", total:20150, moneda:"PEN"}),

  (ana:Asesor {id:"ase-ana", nombre:"Ana Torres", especialidad:"Eventos corporativos"}),
  (luis:Asesor {id:"ase-luis", nombre:"Luis Medina", especialidad:"Eventos sociales"}),

  (regDisp:Regla {id:"reg-disponibilidad", nombre:"Regla: disponibilidad", descripcion:"No cotizar si un producto esta no disponible"}),
  (regCov:Regla {id:"reg-cobertura", nombre:"Regla: cobertura", descripcion:"Observar eventos con cobertura condicionada"}),
  (regAforo:Regla {id:"reg-aforo", nombre:"Regla: aforo", descripcion:"El lugar debe soportar asistentes"}),

  (acme)-[:COTIZA {tipo:"DESCRIBE", detalle:"cliente solicita evento"}]->(lanzamiento),
  (ramos)-[:COTIZA {tipo:"DESCRIBE", detalle:"cliente solicita evento"}]->(boda),
  (startup)-[:COTIZA {tipo:"DESCRIBE", detalle:"cliente solicita evento"}]->(demo),

  (lanzamiento)-[:COTIZA {tipo:"ES_EN_LUGAR", detalle:"evento se realiza en salon"}]->(miraflores),
  (boda)-[:COTIZA {tipo:"ES_EN_LUGAR", detalle:"evento se realiza en casa"}]->(surco),
  (demo)-[:COTIZA {tipo:"ES_EN_LUGAR", detalle:"evento se realiza en club"}]->(chosica),

  (lanzamiento)-[:COTIZA {tipo:"REQUIERE", cantidad:1, detalle:"audio para evento corporativo"}]->(sonido),
  (lanzamiento)-[:COTIZA {tipo:"REQUIERE", cantidad:1, detalle:"ambientacion del evento"}]->(luces),
  (lanzamiento)-[:COTIZA {tipo:"REQUIERE", cantidad:110, detalle:"catering por asistente"}]->(buffet),

  (boda)-[:COTIZA {tipo:"REQUIERE", cantidad:1, detalle:"mobiliario para invitados"}]->(mesas),
  (boda)-[:COTIZA {tipo:"REQUIERE", cantidad:75, detalle:"buffet para invitados"}]->(buffet),
  (boda)-[:COTIZA {tipo:"REQUIERE", cantidad:1, detalle:"servicio solicitado pero no disponible"}]->(cocteles),

  (demo)-[:COTIZA {tipo:"REQUIERE", cantidad:1, detalle:"audio para presentaciones"}]->(sonido),
  (demo)-[:COTIZA {tipo:"REQUIERE", cantidad:1, detalle:"iluminacion de escenario"}]->(luces),
  (demo)-[:COTIZA {tipo:"REQUIERE", cantidad:160, detalle:"catering por asistente"}]->(buffet),
  (demo)-[:COTIZA {tipo:"REQUIERE", cantidad:1, detalle:"bar solicitado pero no disponible"}]->(cocteles),

  (lanzamiento)-[:COTIZA {tipo:"GENERA_COTIZACION", detalle:"cumple condiciones principales"}]->(cot1),
  (boda)-[:COTIZA {tipo:"GENERA_COTIZACION", detalle:"pendiente por producto limitado/no disponible"}]->(cot2),
  (demo)-[:COTIZA {tipo:"GENERA_COTIZACION", detalle:"observada por cobertura y disponibilidad"}]->(cot3),

  (cot1)-[:COTIZA {tipo:"ASIGNADA_A", detalle:"cierre comercial"}]->(ana),
  (cot2)-[:COTIZA {tipo:"ASIGNADA_A", detalle:"cierre comercial"}]->(luis),
  (cot3)-[:COTIZA {tipo:"ASIGNADA_A", detalle:"cierre comercial"}]->(ana),

  (cocteles)-[:COTIZA {tipo:"INCUMPLE", detalle:"No disponible"}]->(regDisp),
  (mesas)-[:COTIZA {tipo:"CONDICIONA", detalle:"Stock limitado"}]->(regDisp),
  (chosica)-[:COTIZA {tipo:"CONDICIONA", detalle:"Cobertura condicionada"}]->(regCov),
  (demo)-[:COTIZA {tipo:"DEBE_CUMPLIR", detalle:"validar aforo y logistica"}]->(regAforo);

// Consultas recomendadas en Neo4j Browser:
//
// MATCH p=()-[:COTIZA]->()
// RETURN p;
//
// MATCH p=(:Evento)-[:COTIZA]->(:Producto)-[r:COTIZA]->(:Regla)
// WHERE r.tipo IN ["INCUMPLE", "CONDICIONA"]
// RETURN p;
//
// MATCH p=(:Cliente {nombre:"Startup Andina"})-[:COTIZA*1..3]->(:Regla)
// RETURN p;
