# Validacion contra la premisa del ejemplo del profesor

## Referencia del ZIP

El ejemplo del profesor en `agents26_m9s25.zip` usa el caso Yape con esta idea:

- Nodos concretos: `Cuenta`, con etiquetas secundarias `Persona` o `Negocio`.
- Relacion principal: `(:Cuenta)-[:YAPEO]->(:Cuenta)`.
- Propiedades en la relacion: fecha, operacion y monto.
- Dataset sintetico, pero con situaciones reconocibles.
- Consultas que revelan patrones: negocios con mayores ingresos, cuentas
  concentradoras, reenvios inmediatos, ciclos y rutas del dinero.
- Tools Python para que un agente consulte Neo4j y no invente respuestas.

## Equivalencia en el agente cotizador

Nuestro proyecto sigue la misma premisa, pero aplicada a cotizaciones de eventos.

| Premisa del profesor | Caso Yape | Caso agente cotizador |
|---|---|---|
| Nodos concretos | Personas y negocios | Clientes, eventos, productos, lugares, precios, disponibilidad, cotizaciones |
| Relacion central | `YAPEO` | `DESCRIBE`, `REQUIERE`, `TIENE_DISPONIBILIDAD`, `SI_CUMPLE_TIENE` |
| Hechos con significado | Quien pago a quien | Que cliente pide que evento, que productos requiere y si se puede cotizar |
| Visualizacion en Browser | Red de cuentas y pagos | Red de eventos, productos, disponibilidad, cobertura y cotizaciones |
| Razonamiento simbolico | Detectar concentracion, ciclos, ruta de dinero | Detectar bloqueos por disponibilidad, cobertura y diferencias de cotizacion |
| Tools | `tools_yape.py` | `src/tools_cotizaciones.py` |

## Datos concretos que se pueden mostrar

El archivo principal es:

```text
data/eventos_cotizaciones.cypher
```

Contiene instancias concretas como:

- `ACME Peru` describe `Lanzamiento de producto`.
- `Familia Ramos` describe `Boda Ramos`.
- `Startup Andina` describe `Demo Day`.
- `Boda Ramos` requiere `Bar de cocteles`.
- `Bar de cocteles` tiene disponibilidad `No disponible`.
- `Demo Day` se realiza en `Club Chosica`.
- `Club Chosica` tiene cobertura `Condicionada`.
- `Demo Day` tiene cotizacion `COT-003 Observada`.
- `COT-003 Observada` tiene cierre asignado a `Ana Torres`.

## Consultas visuales en Neo4j Browser

Vista general:

```cypher
MATCH p=()-[]->()
RETURN p
LIMIT 80;
```

Flujo del agente cotizador:

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

Razonamiento por disponibilidad:

```cypher
MATCH p=(e:Evento)-[:REQUIERE]->(pdt:Producto)-[:TIENE_DISPONIBILIDAD]->(d:Disponibilidad)
WHERE d.estado <> "Disponible"
RETURN p;
```

Razonamiento por cobertura:

```cypher
MATCH p=(e:Evento)-[:ES_EN_LUGAR]->(l:Lugar)-[:TIENE_COBERTURA]->(c:Cobertura)
WHERE c.estado <> "Activa"
RETURN p;
```

Explicacion visual de una cotizacion observada:

```cypher
MATCH p=(cliente:Cliente {nombre: "Startup Andina"})-[:DESCRIBE]->(:Evento)-[]->()
RETURN p
UNION
MATCH p=(:Evento {nombre: "Demo Day"})-[:REQUIERE]->(:Producto)-[]->()
RETURN p
UNION
MATCH p=(:Evento {nombre: "Demo Day"})-[:SI_CUMPLE_TIENE]->(:Cotizacion)-[]->()
RETURN p;
```

## Conclusion

El proyecto esta alineado con la premisa del profesor porque no se queda en un
diagrama conceptual. Carga una base de conocimiento con instancias concretas,
relaciones consultables y reglas de analisis que permiten explicar por que una
cotizacion se emite, queda pendiente u observada.

La diferencia principal es el dominio:

- En Yape, el razonamiento sigue el movimiento del dinero.
- En el agente cotizador, el razonamiento sigue la viabilidad de una cotizacion.
