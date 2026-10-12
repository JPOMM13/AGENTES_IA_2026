# Prompt para migrar memoria mock a PostgreSQL JSONB y Redis

```markdown
Quiero migrar la memoria del agente que todavía está en archivos mock.

Contexto:
- Ya se migró correctamente la capa de datos de negocio a PostgreSQL.
- Esa migración NO debe tocarse.
- Ahora quiero migrar específicamente:
  1. `app/data/mock_session_memory.json`
  2. `app/data/mock_redis_session.json`

Objetivo:
- `mock_session_memory.json` debe migrarse a PostgreSQL con formato tipo NoSQL usando `JSONB`.
- `mock_redis_session.json` debe migrarse a Redis real.
- Mantener exactamente el comportamiento actual del agente.
- NO modificar la lógica conversacional.
- NO modificar LangGraph.
- NO modificar prompts, guardrails, tools de negocio ni frontend.
- Solo cambiar la capa de persistencia de memoria.

Alcance:

1. Migrar `mock_session_memory.json`:
   - Actualmente representa memoria persistente entre sesiones.
   - Sirve para retomar cotizaciones anteriores por contacto/teléfono.
   - Debe guardarse en PostgreSQL dentro del schema `memory`.
   - Usar una tabla con prefijo `jpomm_`.
   - El almacenamiento debe ser tipo NoSQL usando columna `JSONB`.
   - La tabla sugerida es `memory.jpomm_memoria_cotizaciones`.
   - Debe guardar como mínimo:
     - `id`
     - `contacto`
     - `nombre_cliente`
     - `clave_cliente` si actualmente existe o se deriva
     - `estado_cotizacion` JSONB completo
     - `creado_en`
     - `actualizado_en`
   - Debe permitir upsert por contacto.
   - Debe permitir recuperar la última cotización por contacto.
   - No guardar aquí memoria temporal de sesión activa.

2. Migrar `mock_redis_session.json`:
   - Actualmente representa memoria corta tipo Redis por `session_id`.
   - Debe migrarse a Redis real.
   - Debe guardar el estado activo de la sesión por `id_sesion`.
   - Usar TTL configurable.
   - La key sugerida es `jpomm:sesion:{id_sesion}`.
   - El value puede ser JSON serializado.
   - Debe permitir:
     - obtener sesión por `id_sesion`
     - guardar sesión
     - reiniciar/eliminar sesión
   - Si no existe la key, debe crear un estado nuevo como ahora.

Variables de entorno:
Agregar al `.env.example` y usar desde código:

```env
# Memoria persistente tipo NoSQL en PostgreSQL
MEMORY_DATA_SOURCE=postgres
POSTGRES_MEMORY_SCHEMA=memory

# Memoria corta en Redis
SESSION_STORE=redis
REDIS_URL=redis://default:2yMpP1Ulp6a3BbHy4iK9aNqeSUqQVJfS@chalk-book-spa-44762.db.redis.io:13110
REDIS_SESSION_TTL_SECONDS=86400
```

Importante:
- No hardcodear la URL de Redis en código.
- Usar siempre `REDIS_URL` desde `.env`.
- No imprimir claves ni secretos en logs.
- Mantener fallback mock solo como modo desarrollo:
  - `MEMORY_DATA_SOURCE=mock`
  - `SESSION_STORE=mock`
- En modo operativo debe usarse:
  - `MEMORY_DATA_SOURCE=postgres`
  - `SESSION_STORE=redis`

Tareas:

1. Analizar:
   - `app/almacen_sesion.py`
   - `app/almacen_sesion_redis.py`
   - `app/repositorios.py`
   - cualquier lugar donde se lea/escriba `mock_session_memory.json`
   - cualquier lugar donde se lea/escriba `mock_redis_session.json`

2. Crear scripts PostgreSQL para ejecutar en DBeaver o psql:
   - `scripts/postgres/004_crear_memoria_jsonb.sql`
   - `scripts/postgres/006_validar_memoria_jsonb.sql`

   El script `004_crear_memoria_jsonb.sql` debe:
   - crear el schema `memory` si no existe;
   - crear la tabla `memory.jpomm_memoria_cotizaciones`;
   - definir primary key;
   - definir una restricción o índice único por `contacto`;
   - usar `JSONB` para guardar el estado completo de cotización;
   - crear índices útiles por:
     - `contacto`
     - `nombre_cliente`
     - `clave_cliente`
     - `actualizado_en`
     - índice `GIN` sobre `estado_cotizacion`;
   - crear un trigger o mecanismo equivalente para actualizar `actualizado_en` en cada update.

   El script `006_validar_memoria_jsonb.sql` debe:
   - contar memorias cargadas;
   - listar memorias por `actualizado_en DESC`;
   - mostrar `contacto`, `nombre_cliente`, `clave_cliente`;
   - mostrar campos relevantes extraídos desde `estado_cotizacion`, por ejemplo:
     - tipo de evento
     - fecha
     - distrito
     - productos/servicios
   - permitir validar rápidamente si una memoria por contacto existe.

3. Crear script de migración inicial:
   - `scripts/postgres/005_migrar_mock_session_memory.py`

   Este script debe:
   - leer `app/data/mock_session_memory.json` si existe;
   - insertar/upsert en `memory.jpomm_memoria_cotizaciones`;
   - ser idempotente;
   - usar la conexión PostgreSQL actual y respetar SSL/certificados ya configurados;
   - usar `POSTGRES_MEMORY_SCHEMA=memory`;
   - poder ejecutarse así:

   ```bash
   python scripts/postgres/005_migrar_mock_session_memory.py
   ```

4. Crear repositorio PostgreSQL para memoria persistente:
   - `app/repositorios_postgres/memoria_postgres.py`

   Debe exponer funciones equivalentes a las actuales:
   - guardar memoria por contacto
   - buscar memoria por contacto
   - actualizar memoria

   Requisitos:
   - usar `JSONB`;
   - respetar el contrato actual del agente;
   - no cambiar cómo el flujo llama a memoria;
   - no mezclar esta memoria con Redis.

5. Crear repositorio Redis para sesión activa:
   - `app/repositorios_redis/conexion.py`
   - `app/repositorios_redis/sesion_redis.py`

   Requisitos:
   - usar `redis-py`;
   - leer `REDIS_URL`;
   - aplicar TTL desde `REDIS_SESSION_TTL_SECONDS`;
   - serializar/deserializar `EstadoCotizacion` a JSON;
   - mantener el mismo comportamiento que `mock_redis_session.json`;
   - no guardar memoria persistente de cliente en Redis.

6. Modificar internamente la capa de repositorios:
   - Mantener las clases/nombres públicos actuales si existen.
   - Que `RepositorioMemoriaCotizacion` use PostgreSQL si `MEMORY_DATA_SOURCE=postgres`.
   - Que `RepositorioSesionActiva` use Redis si `SESSION_STORE=redis`.
   - Si las variables están en `mock`, usar comportamiento actual con JSON local.
   - No cambiar llamadas desde el flujo.

7. Agregar dependencias:
   - `redis>=5.0`
   - mantener `psycopg[binary]` y lo que ya exista para PostgreSQL.

8. Actualizar README:
   - Cómo ejecutar `004_crear_memoria_jsonb.sql` en DBeaver.
   - Cómo migrar datos mock existentes con `005_migrar_mock_session_memory.py`.
   - Cómo validar con `006_validar_memoria_jsonb.sql`.
   - Cómo configurar `.env`.
   - Cómo probar Redis con `redis-cli`.
   - Cómo validar que la sesión activa se guarda en Redis.
   - Cómo validar que la memoria persistente se guarda en PostgreSQL.

9. Agregar comandos de ejecución esperados en README:

   Crear tabla memoria en PostgreSQL:

   ```bash
   psql -d eventos -f scripts/postgres/004_crear_memoria_jsonb.sql
   ```

   Migrar memoria mock a PostgreSQL:

   ```bash
   python scripts/postgres/005_migrar_mock_session_memory.py
   ```

   Validar memoria en PostgreSQL:

   ```bash
   psql -d eventos -f scripts/postgres/006_validar_memoria_jsonb.sql
   ```

   Probar Redis:

   ```bash
   redis-cli -u "$REDIS_URL" ping
   ```

   Ver keys de sesión:

   ```bash
   redis-cli -u "$REDIS_URL" keys "jpomm:sesion:*"
   ```

   Consultar una sesión:

   ```bash
   redis-cli -u "$REDIS_URL" get "jpomm:sesion:{id_sesion}"
   ```

10. Agregar tests o smoke tests:
   - Test mock actual no debe romperse.
   - Smoke test PostgreSQL memoria:
     - guardar cotización por contacto
     - recuperar por contacto
   - Smoke test Redis:
     - guardar sesión
     - recuperar sesión
     - reiniciar/eliminar sesión
   - Los smoke tests reales deben activarse solo con variables:
     - `RUN_POSTGRES_TESTS=true`
     - `RUN_REDIS_TESTS=true`

Restricciones:
- NO tocar la lógica del agente.
- NO cambiar LangGraph.
- NO cambiar prompts.
- NO cambiar tools de negocio.
- NO tocar la migración ya hecha de datos de negocio.
- NO mover Redis a PostgreSQL.
- NO mover memoria persistente a Redis.
- PostgreSQL con JSONB es solo para `mock_session_memory.json`.
- Redis real es solo para `mock_redis_session.json`.
- Mantener el código en español: nombres de funciones nuevas, variables nuevas, comentarios y archivos propios del proyecto.
- No borrar los mocks actuales; dejarlos como fallback de desarrollo.
- No exponer secretos en logs ni README más allá de placeholders.
```

