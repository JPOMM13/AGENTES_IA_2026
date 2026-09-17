# Reporte: Analisis de relaciones para agente de cotizaciones de eventos

## 1. Objetivo

El objetivo del proyecto es representar en Neo4j las relaciones principales de
un agente de cotizaciones de eventos. El grafo permite responder preguntas como:
que cliente solicita un evento, en que fecha y lugar se realizara, que productos
requiere, si existe cobertura, si hay disponibilidad, cuanto cuesta cada
producto y que asesor queda asociado a la propuesta.

La entrega sigue la premisa del ejemplo del profesor: se construye una base de
conocimiento con instancias concretas y relaciones consultables, no solamente un
diagrama conceptual.

## 2. Modelo de grafo

El nodo central del modelo es `Evento`. Desde el evento se conectan las
entidades necesarias para decidir si se puede generar una cotizacion.

Entidades modeladas:

- `Cliente`: persona o empresa que describe la necesidad del evento.
- `Evento`: solicitud principal que concentra tipo de evento, asistentes y
  estado.
- `Fecha`: dia planificado para el evento.
- `Lugar`: sede donde se realizara el evento.
- `Cobertura`: zona operativa asociada al lugar.
- `Producto`: recurso requerido por el evento.
- `Catalogo`: agrupacion comercial de productos.
- `Precio`: precio unitario de cada producto.
- `Disponibilidad`: stock o estado operativo del producto.
- `Cotizacion`: propuesta economica generada para el evento.
- `Asesor`: responsable comercial del cierre de la propuesta.
- `ReglaNegocio`: restricciones que deben cumplirse.

Relaciones principales:

- `(:Cliente)-[:DESCRIBE]->(:Evento)`
- `(:Evento)-[:ES_EN_FECHA]->(:Fecha)`
- `(:Evento)-[:ES_EN_LUGAR]->(:Lugar)`
- `(:Lugar)-[:TIENE_COBERTURA]->(:Cobertura)`
- `(:Evento)-[:REQUIERE]->(:Producto)`
- `(:Producto)-[:SALE_DE]->(:Catalogo)`
- `(:Producto)-[:TIENE_PRECIO]->(:Precio)`
- `(:Producto)-[:TIENE_DISPONIBILIDAD]->(:Disponibilidad)`
- `(:Evento)-[:SI_CUMPLE_TIENE]->(:Cotizacion)`
- `(:Cotizacion)-[:CIERRE_DE_PROPUESTA]->(:Asesor)`
- `(:Fecha|Lugar|Producto)-[:DEBE_CUMPLIR]->(:ReglaNegocio)`

## 3. Data de prueba

Se cargaron tres solicitudes de evento:

- `Lanzamiento de producto`, solicitado por `ACME Peru`, con estado aprobado.
- `Boda Ramos`, solicitada por `Familia Ramos`, con estado aprobado.
- `Demo Day`, solicitado por `Startup Andina`, con estado observado.

Tambien se cargaron productos de audio, iluminacion, mobiliario, catering y
bebidas. Cada producto tiene precio, disponibilidad y catalogo asociado.

Ejemplos de hechos representados en el grafo:

- `Familia Ramos` describe `Boda Ramos`.
- `Boda Ramos` requiere `Bar de cocteles`.
- `Bar de cocteles` tiene disponibilidad `No disponible`.
- `Startup Andina` describe `Demo Day`.
- `Demo Day` se realiza en `Club Chosica`.
- `Club Chosica` tiene cobertura `Condicionada`.
- `Demo Day` tiene cotizacion `COT-003 Observada`.

## 4. Analisis de relaciones

El grafo muestra que el evento funciona como punto de integracion entre la
necesidad del cliente y las condiciones de negocio. Una tabla plana podria
listar cliente, fecha, lugar y productos, pero el grafo permite recorrer
relaciones en varias direcciones: desde un cliente hacia sus productos, desde un
producto hacia los eventos que lo requieren, o desde un lugar hacia su cobertura.

La relacion `REQUIERE` es la mas importante para la cotizacion, porque conecta
el evento con los productos necesarios e incluye la cantidad requerida. A partir
de esa relacion se puede calcular el costo esperado multiplicando cantidad por
precio unitario.

La relacion `TIENE_DISPONIBILIDAD` permite encontrar riesgos operativos. En la
data de prueba, el producto `Bar de cocteles` aparece como no disponible. Esto
afecta a `Boda Ramos` y `Demo Day`, por lo que esas cotizaciones no deberian
cerrarse sin una alternativa.

La relacion `TIENE_COBERTURA` permite evaluar si el lugar se encuentra dentro
de una zona activa. `Club Chosica` esta asociado a una cobertura condicionada,
por lo que el evento `Demo Day` queda observado por logistica.

Las relaciones `DEBE_CUMPLIR` conectan fechas, lugares y productos con reglas de
negocio. Esto ayuda a documentar por que una cotizacion se emite, queda
pendiente o se observa.

## 5. Visualizacion

La visualizacion principal de la base de conocimiento se realiza directamente en
Neo4j Browser, igual que en el ejemplo del profesor. La consulta recomendada es:

```cypher
MATCH p=()-[]->()
RETURN p
LIMIT 80;
```

Para visualizar el razonamiento simbolico sobre disponibilidad:

```cypher
MATCH p=(e:Evento)-[:REQUIERE]->(pdt:Producto)-[:TIENE_DISPONIBILIDAD]->(d:Disponibilidad)
WHERE d.estado <> "Disponible"
RETURN p;
```

La visualizacion conceptual se genera con:

```bash
python src/visualizar.py
```

El archivo resultante es:

```text
docs/grafo_eventos.html
```

Esta vista representa el modelo de relaciones del agente, no cada registro
individual de la base de datos. Por eso se parece al diagrama inicial: `Evento`
aparece al centro y desde ahi se conectan cliente, fecha, lugar, productos y
cotizacion.

Si se desea visualizar las instancias reales cargadas en Neo4j, se puede usar:

```bash
python src/visualizar.py --datos
```

Ese comando genera `docs/grafo_eventos_datos.html`, donde aparecen los clientes,
eventos, productos, precios y reglas concretas del dataset.

En la visualizacion conceptual se observa que `Evento` y `Cotizacion` son nodos
de alto valor para el proceso. `Evento` concentra la informacion operativa y
`Cotizacion` representa la salida comercial del agente.

## 6. Hallazgos

- El modelo permite explicar de forma clara como una solicitud del cliente se
  transforma en una cotizacion.
- La disponibilidad de productos es un riesgo clave, especialmente para eventos
  que dependen de servicios con stock cero o limitado.
- La cobertura del lugar influye directamente en la viabilidad de la propuesta.
- El asesor se conecta al cierre de propuesta, no al cliente directamente, lo
  que permite reasignar clientes sin perder historial comercial.
- El grafo facilita consultas de impacto, por ejemplo: que eventos se ven
  afectados si un producto no esta disponible.

## 7. Conclusiones

Neo4j es adecuado para este proyecto porque las decisiones de cotizacion dependen
de varias relaciones conectadas: cliente, evento, fecha, lugar, productos,
precios, disponibilidad y reglas de negocio. El grafo permite visualizar estas
dependencias y detectar rapidamente problemas antes de emitir o cerrar una
propuesta.

Como siguiente mejora, el agente podria recibir una descripcion textual del
evento, crear el nodo `Evento`, buscar productos compatibles en el catalogo,
validar reglas de negocio y devolver una cotizacion sugerida con explicacion.
