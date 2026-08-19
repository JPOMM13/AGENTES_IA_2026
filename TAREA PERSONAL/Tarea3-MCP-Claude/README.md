# MCP Personal — Iniciativas y Procedimientos

Primera versión académica, simple y demostrable, basada en el patrón de la clase de MCP.

## ¿Qué hace?

Permite que un cliente MCP como Claude Desktop consulte y actualice información simulada de iniciativas y consulte procedimientos de trabajo.

## Estructura

```text
mcp_iniciativas_v1/
├── server.py
├── project_context.md
├── pyproject.toml
├── test_local.py
├── data/
│   ├── iniciativas.json
│   └── procedimientos.json
└── screenshots/
    └── README.md
```

## Capacidades

### Tools

- `listar_iniciativas`
- `consultar_iniciativa`
- `registrar_avance`
- `consultar_procedimiento`
- `resumen_diario`

### Resources

- `iniciativas://actual`
- `context://project`

### Prompt

- `resumen_iniciativas`

## Requisito académico

Los datos incluidos son **simulados** y no corresponden a información real de una entidad financiera.

## Instalación con uv

### 1. Entrar al proyecto

```bash
cd mcp_iniciativas_v1
```

### 2. Crear/sincronizar el entorno

Si ya tienes `uv` instalado:

```bash
uv sync
```

### 3. Validar los JSON

```bash
uv run python test_local.py
```

Deberías ver:

```text
OK JSON: iniciativas.json -> 3 registros
OK JSON: procedimientos.json -> 3 registros
OK: archivos JSON válidos.
```

## Inspeccionar el MCP

```bash
uv run fastmcp inspect server.py
```

Esto permite verificar las tools, resources y prompts definidos.

## Probar con MCP Inspector

```bash
uv run fastmcp dev inspector server.py
```

## Ejecutar directamente

```bash
uv run python server.py
```

El servidor usa STDIO por defecto. En esta modalidad normalmente el cliente MCP es quien inicia y administra el proceso.

## Instalar en Claude Desktop

Con una versión actual de FastMCP:

```bash
uv run fastmcp install claude-desktop server.py
```

Después reinicia Claude Desktop.

> Si tu versión instalada de FastMCP muestra una sintaxis distinta, ejecuta `uv run fastmcp --help` y `uv run fastmcp install --help`.

## Pruebas sugeridas en Claude

### Prueba 1 — listado

> ¿Qué iniciativas tengo registradas? Muéstrame estado, ambiente y avance.

Tool esperada: `listar_iniciativas`

### Prueba 2 — consulta

> ¿En qué estado está la migración DevOps a GitHub Actions y cuál es su próximo paso?

Tool esperada: `consultar_iniciativa`

### Prueba 3 — actualización

> Actualiza la iniciativa Migración DevOps a GitHub Actions a 80% de avance e indica que finalizaron las pruebas funcionales.

Tool esperada: `registrar_avance`

Luego pregunta:

> ¿Cuál es ahora el avance de la migración DevOps?

Debe devolver 80%.

### Prueba 4 — procedimiento

> ¿Cuál es el procedimiento registrado para un pase a producción?

Tool esperada: `consultar_procedimiento`

### Prueba 5 — resumen personal

> Dame mi resumen de iniciativas para comenzar el día. Prioriza las que necesitan atención.

Tool esperada: `resumen_diario`

## ¿Qué demuestra esta versión?

1. Claude puede descubrir tools del servidor.
2. Claude puede leer datos externos al modelo.
3. Claude puede modificar una fuente local mediante una tool.
4. El cambio persiste en `iniciativas.json`.
5. Los Resources aportan contexto sin representar una acción.
6. El Prompt ofrece una plantilla reutilizable.
7. La implementación puede evolucionar luego hacia GitHub, Azure DevOps, APIs o bases de datos sin cambiar el concepto principal del agente.

## Qué NO incluye esta versión

Para mantener la tarea sencilla, no incluye:

- LangGraph
- supervisor multiagente
- RAG
- base vectorial
- Cosmos DB
- GitHub real
- Azure DevOps real
- APIs bancarias
- autenticación OAuth

Todo eso puede agregarse en una siguiente versión.
