CREATE CONSTRAINT cliente_id IF NOT EXISTS FOR (n:Cliente) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT evento_id IF NOT EXISTS FOR (n:Evento) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT fecha_id IF NOT EXISTS FOR (n:Fecha) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT lugar_id IF NOT EXISTS FOR (n:Lugar) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT cobertura_id IF NOT EXISTS FOR (n:Cobertura) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT catalogo_id IF NOT EXISTS FOR (n:Catalogo) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT producto_id IF NOT EXISTS FOR (n:Producto) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT precio_id IF NOT EXISTS FOR (n:Precio) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT disponibilidad_id IF NOT EXISTS FOR (n:Disponibilidad) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT cotizacion_id IF NOT EXISTS FOR (n:Cotizacion) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT asesor_id IF NOT EXISTS FOR (n:Asesor) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT regla_id IF NOT EXISTS FOR (n:ReglaNegocio) REQUIRE n.id IS UNIQUE;

MATCH (n) DETACH DELETE n;

MERGE (catalogoAudio:Catalogo {id: "cat-audio"})
  SET catalogoAudio.nombre = "Audio e iluminacion", catalogoAudio.version = "2026.09";
MERGE (catalogoMobiliario:Catalogo {id: "cat-mobiliario"})
  SET catalogoMobiliario.nombre = "Mobiliario y ambientacion", catalogoMobiliario.version = "2026.09";
MERGE (catalogoCatering:Catalogo {id: "cat-catering"})
  SET catalogoCatering.nombre = "Catering y bebidas", catalogoCatering.version = "2026.09";

MERGE (p1:Producto {id: "prod-sonido-pro"})
  SET p1.nombre = "Sistema de sonido profesional", p1.categoria = "Audio", p1.capacidad = "Hasta 200 asistentes";
MERGE (p2:Producto {id: "prod-luces-led"})
  SET p2.nombre = "Luces LED ambientales", p2.categoria = "Iluminacion", p2.capacidad = "Salon mediano";
MERGE (p3:Producto {id: "prod-mesas-sillas"})
  SET p3.nombre = "Pack mesas y sillas", p3.categoria = "Mobiliario", p3.capacidad = "100 personas";
MERGE (p4:Producto {id: "prod-buffet"})
  SET p4.nombre = "Buffet ejecutivo", p4.categoria = "Catering", p4.capacidad = "Por persona";
MERGE (p5:Producto {id: "prod-cocteles"})
  SET p5.nombre = "Bar de cocteles", p5.categoria = "Bebidas", p5.capacidad = "3 horas";

MERGE (p1)-[:SALE_DE]->(catalogoAudio);
MERGE (p2)-[:SALE_DE]->(catalogoAudio);
MERGE (p3)-[:SALE_DE]->(catalogoMobiliario);
MERGE (p4)-[:SALE_DE]->(catalogoCatering);
MERGE (p5)-[:SALE_DE]->(catalogoCatering);

MERGE (precio1:Precio {id: "precio-sonido-pro"}) SET precio1.nombre = "S/ 1800", precio1.moneda = "PEN", precio1.monto = 1800;
MERGE (precio2:Precio {id: "precio-luces-led"}) SET precio2.nombre = "S/ 950", precio2.moneda = "PEN", precio2.monto = 950;
MERGE (precio3:Precio {id: "precio-mesas-sillas"}) SET precio3.nombre = "S/ 1200", precio3.moneda = "PEN", precio3.monto = 1200;
MERGE (precio4:Precio {id: "precio-buffet"}) SET precio4.nombre = "S/ 95 por persona", precio4.moneda = "PEN", precio4.monto = 95;
MERGE (precio5:Precio {id: "precio-cocteles"}) SET precio5.nombre = "S/ 2400", precio5.moneda = "PEN", precio5.monto = 2400;

MERGE (disp1:Disponibilidad {id: "disp-sonido-2026-09"}) SET disp1.nombre = "Disponible: 2", disp1.estado = "Disponible", disp1.stock = 2;
MERGE (disp2:Disponibilidad {id: "disp-luces-2026-09"}) SET disp2.nombre = "Disponible: 4", disp2.estado = "Disponible", disp2.stock = 4;
MERGE (disp3:Disponibilidad {id: "disp-mesas-2026-09"}) SET disp3.nombre = "Limitado: 1", disp3.estado = "Limitado", disp3.stock = 1;
MERGE (disp4:Disponibilidad {id: "disp-buffet-2026-09"}) SET disp4.nombre = "Disponible: 300", disp4.estado = "Disponible", disp4.stock = 300;
MERGE (disp5:Disponibilidad {id: "disp-cocteles-2026-09"}) SET disp5.nombre = "No disponible", disp5.estado = "No disponible", disp5.stock = 0;

MERGE (p1)-[:TIENE_PRECIO]->(precio1);
MERGE (p2)-[:TIENE_PRECIO]->(precio2);
MERGE (p3)-[:TIENE_PRECIO]->(precio3);
MERGE (p4)-[:TIENE_PRECIO]->(precio4);
MERGE (p5)-[:TIENE_PRECIO]->(precio5);
MERGE (p1)-[:TIENE_DISPONIBILIDAD]->(disp1);
MERGE (p2)-[:TIENE_DISPONIBILIDAD]->(disp2);
MERGE (p3)-[:TIENE_DISPONIBILIDAD]->(disp3);
MERGE (p4)-[:TIENE_DISPONIBILIDAD]->(disp4);
MERGE (p5)-[:TIENE_DISPONIBILIDAD]->(disp5);

MERGE (r1:ReglaNegocio {id: "reg-min-48h"})
  SET r1.nombre = "Anticipacion minima", r1.descripcion = "La fecha del evento debe permitir al menos 48 horas para preparar proveedores.";
MERGE (r2:ReglaNegocio {id: "reg-cobertura"})
  SET r2.nombre = "Cobertura geografica", r2.descripcion = "El lugar debe estar dentro de la cobertura operativa.";
MERGE (r3:ReglaNegocio {id: "reg-disponibilidad"})
  SET r3.nombre = "Disponibilidad de productos", r3.descripcion = "Una cotizacion solo se emite si los productos requeridos tienen disponibilidad.";

MERGE (fecha1:Fecha {id: "fecha-2026-10-04"}) SET fecha1.nombre = "04/10/2026", fecha1.valor = date("2026-10-04"), fecha1.diaSemana = "Domingo";
MERGE (fecha2:Fecha {id: "fecha-2026-10-11"}) SET fecha2.nombre = "11/10/2026", fecha2.valor = date("2026-10-11"), fecha2.diaSemana = "Domingo";
MERGE (fecha3:Fecha {id: "fecha-2026-10-18"}) SET fecha3.nombre = "18/10/2026", fecha3.valor = date("2026-10-18"), fecha3.diaSemana = "Domingo";

MERGE (lugar1:Lugar {id: "lugar-miraflores"}) SET lugar1.nombre = "Salon Miraflores", lugar1.distrito = "Miraflores", lugar1.aforo = 120;
MERGE (lugar2:Lugar {id: "lugar-surco"}) SET lugar2.nombre = "Casa Surco", lugar2.distrito = "Santiago de Surco", lugar2.aforo = 80;
MERGE (lugar3:Lugar {id: "lugar-chosica"}) SET lugar3.nombre = "Club Chosica", lugar3.distrito = "Chosica", lugar3.aforo = 180;

MERGE (cov1:Cobertura {id: "cov-lima-centro"}) SET cov1.nombre = "Lima centro y moderna", cov1.estado = "Activa";
MERGE (cov2:Cobertura {id: "cov-lima-este"}) SET cov2.nombre = "Lima este", cov2.estado = "Condicionada";
MERGE (lugar1)-[:TIENE_COBERTURA]->(cov1);
MERGE (lugar2)-[:TIENE_COBERTURA]->(cov1);
MERGE (lugar3)-[:TIENE_COBERTURA]->(cov2);

MERGE (cliente1:Cliente {id: "cli-acme"}) SET cliente1.nombre = "ACME Peru", cliente1.tipo = "Empresa";
MERGE (cliente2:Cliente {id: "cli-familia-ramos"}) SET cliente2.nombre = "Familia Ramos", cliente2.tipo = "Persona";
MERGE (cliente3:Cliente {id: "cli-startup"}) SET cliente3.nombre = "Startup Andina", cliente3.tipo = "Empresa";

MERGE (evento1:Evento {id: "evt-lanzamiento"}) SET evento1.nombre = "Lanzamiento de producto", evento1.tipo = "Corporativo", evento1.asistentes = 110, evento1.estado = "Aprobado";
MERGE (evento2:Evento {id: "evt-boda"}) SET evento2.nombre = "Boda Ramos", evento2.tipo = "Social", evento2.asistentes = 75, evento2.estado = "Aprobado";
MERGE (evento3:Evento {id: "evt-demo-day"}) SET evento3.nombre = "Demo Day", evento3.tipo = "Corporativo", evento3.asistentes = 160, evento3.estado = "Observado";

MERGE (cliente1)-[:DESCRIBE]->(evento1);
MERGE (cliente2)-[:DESCRIBE]->(evento2);
MERGE (cliente3)-[:DESCRIBE]->(evento3);
MERGE (evento1)-[:ES_EN_FECHA]->(fecha1);
MERGE (evento2)-[:ES_EN_FECHA]->(fecha2);
MERGE (evento3)-[:ES_EN_FECHA]->(fecha3);
MERGE (evento1)-[:ES_EN_LUGAR]->(lugar1);
MERGE (evento2)-[:ES_EN_LUGAR]->(lugar2);
MERGE (evento3)-[:ES_EN_LUGAR]->(lugar3);
MERGE (fecha1)-[:DEBE_CUMPLIR]->(r1);
MERGE (fecha2)-[:DEBE_CUMPLIR]->(r1);
MERGE (fecha3)-[:DEBE_CUMPLIR]->(r1);
MERGE (lugar1)-[:DEBE_CUMPLIR]->(r2);
MERGE (lugar2)-[:DEBE_CUMPLIR]->(r2);
MERGE (lugar3)-[:DEBE_CUMPLIR]->(r2);

MERGE (evento1)-[:REQUIERE {cantidad: 1}]->(p1);
MERGE (evento1)-[:REQUIERE {cantidad: 1}]->(p2);
MERGE (evento1)-[:REQUIERE {cantidad: 110}]->(p4);
MERGE (evento2)-[:REQUIERE {cantidad: 1}]->(p3);
MERGE (evento2)-[:REQUIERE {cantidad: 75}]->(p4);
MERGE (evento2)-[:REQUIERE {cantidad: 1}]->(p5);
MERGE (evento3)-[:REQUIERE {cantidad: 1}]->(p1);
MERGE (evento3)-[:REQUIERE {cantidad: 1}]->(p2);
MERGE (evento3)-[:REQUIERE {cantidad: 160}]->(p4);
MERGE (evento3)-[:REQUIERE {cantidad: 1}]->(p5);
MERGE (p1)-[:DEBE_CUMPLIR]->(r3);
MERGE (p2)-[:DEBE_CUMPLIR]->(r3);
MERGE (p3)-[:DEBE_CUMPLIR]->(r3);
MERGE (p4)-[:DEBE_CUMPLIR]->(r3);
MERGE (p5)-[:DEBE_CUMPLIR]->(r3);

MERGE (cot1:Cotizacion {id: "cot-001"}) SET cot1.nombre = "COT-001 Emitida", cot1.estado = "Emitida", cot1.total = 13200, cot1.moneda = "PEN";
MERGE (cot2:Cotizacion {id: "cot-002"}) SET cot2.nombre = "COT-002 Pendiente", cot2.estado = "Pendiente", cot2.total = 8325, cot2.moneda = "PEN";
MERGE (cot3:Cotizacion {id: "cot-003"}) SET cot3.nombre = "COT-003 Observada", cot3.estado = "Observada", cot3.total = 20150, cot3.moneda = "PEN";
MERGE (asesor1:Asesor {id: "ase-ana"}) SET asesor1.nombre = "Ana Torres", asesor1.especialidad = "Eventos corporativos";
MERGE (asesor2:Asesor {id: "ase-luis"}) SET asesor2.nombre = "Luis Medina", asesor2.especialidad = "Eventos sociales";

MERGE (evento1)-[:SI_CUMPLE_TIENE]->(cot1);
MERGE (evento2)-[:SI_CUMPLE_TIENE]->(cot2);
MERGE (evento3)-[:SI_CUMPLE_TIENE]->(cot3);
MERGE (cot1)-[:CIERRE_DE_PROPUESTA]->(asesor1);
MERGE (cot2)-[:CIERRE_DE_PROPUESTA]->(asesor2);
MERGE (cot3)-[:CIERRE_DE_PROPUESTA]->(asesor1);
