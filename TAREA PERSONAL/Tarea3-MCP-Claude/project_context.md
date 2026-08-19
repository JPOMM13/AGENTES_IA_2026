# Project Context — MCP Personal de Iniciativas y Procedimientos

## 1. Propósito

Este proyecto académico implementa un MCP Server personal para apoyar la gestión diaria de iniciativas y procedimientos.

Claude Desktop actúa como **MCP Host**. El servidor desarrollado en Python con **FastMCP** expone herramientas, recursos y un prompt especializado para consultar o actualizar información local simulada.

> Todos los datos de esta versión son ficticios y se usan únicamente con fines académicos.

## 2. Problema que resuelve

En el trabajo diario puede ser necesario responder rápidamente preguntas como:

- ¿Qué iniciativas están activas?
- ¿En qué estado se encuentra una iniciativa?
- ¿Cuál es el siguiente paso?
- ¿Existe algún bloqueo?
- ¿Cuál es el procedimiento para un pase a producción?
- ¿Qué debería revisar hoy?

El MCP Server centraliza ese contexto y lo hace accesible a Claude mediante un protocolo estándar.

## 3. Alcance de la versión 1

La versión 1 trabaja solamente con archivos locales:

- `data/iniciativas.json`
- `data/procedimientos.json`
- `project_context.md`

No se conecta a sistemas reales del banco, GitHub, Azure DevOps, Teradata, SharePoint, APIs empresariales ni bases de datos.

## 4. Entidades

### Iniciativa

Cada iniciativa contiene:

- id
- nombre
- descripción
- estado
- ambiente
- porcentaje de avance
- próximo paso
- responsable
- fecha objetivo
- bloqueos
- fecha de última actualización

### Procedimiento

Cada procedimiento contiene:

- id
- nombre
- descripción
- pasos
- consideraciones

## 5. Capacidades MCP

### Tools

1. `listar_iniciativas`
   - Lista las iniciativas registradas.

2. `consultar_iniciativa`
   - Busca una iniciativa por nombre o ID.

3. `registrar_avance`
   - Actualiza porcentaje, estado, próximo paso o comentario de una iniciativa.
   - Persiste el cambio en `iniciativas.json`.

4. `consultar_procedimiento`
   - Recupera un procedimiento por nombre o ID.

5. `resumen_diario`
   - Devuelve una vista compacta de avance, próximos pasos y bloqueos.

### Resources

- `iniciativas://actual`
  - Expone el estado completo actual de las iniciativas.

- `context://project`
  - Expone este Project Context como contexto reutilizable.

### Prompt

- `resumen_iniciativas`
  - Plantilla para pedir un resumen ejecutivo de iniciativas con prioridad, bloqueos y próximos pasos.

## 6. Arquitectura

```text
Usuario
   |
   v
Claude Desktop
(MCP Host)
   |
   v
MCP Client
   |
   | STDIO
   v
FastMCP Server
(server.py)
   |
   +-- Tools
   +-- Resources
   +-- Prompt
   |
   v
Archivos locales
   +-- iniciativas.json
   +-- procedimientos.json
   +-- project_context.md
```

## 7. Evolución futura

Sin cambiar la forma en que Claude consume las capacidades MCP, las fuentes locales podrían reemplazarse por:

- GitHub / GitHub Actions
- Azure DevOps
- APIs internas
- bases de datos
- repositorios documentales
- Project Specs reales
- sistemas de seguimiento

La versión 1 busca demostrar el patrón MCP de manera simple y entendible antes de incorporar integraciones empresariales.
