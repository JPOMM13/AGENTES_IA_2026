# MCP Personal de Iniciativas y Procedimientos

## Documento descriptivo del agente desarrollado

**Tipo de proyecto:** Personal  
**Tecnología principal:** Python y FastMCP  
**Cliente MCP:** Claude Desktop  
**Modalidad:** Prototipo académico con datos simulados

## Declaración sobre el uso de inteligencia artificial

Este proyecto fue desarrollado con el apoyo de **Codex** como herramienta de inteligencia artificial para la generación, revisión y documentación del código. La implementación se realizó mediante un proceso de colaboración entre la IA y el autor, bajo **supervisión humana permanente**.

El autor definió el propósito y alcance del agente, revisó las decisiones de diseño, ejecutó las pruebas y validó el resultado final. Codex se utilizó como asistente técnico, pero las decisiones, verificaciones y responsabilidad sobre el contenido presentado permanecen a cargo del autor.

---

## 1. Resumen ejecutivo

El proyecto implementa un **MCP Server personal de iniciativas y procedimientos**, desarrollado en Python con FastMCP e integrado con Claude Desktop.

Su propósito es apoyar al usuario en actividades cotidianas relacionadas con el seguimiento de iniciativas: consultar estados y porcentajes de avance, identificar bloqueos, revisar próximos pasos, registrar actualizaciones y acceder a procedimientos de trabajo mediante lenguaje natural.

Claude actúa como la interfaz conversacional y utiliza las capacidades publicadas por el servidor MCP. De esta manera, el modelo no depende solamente de la información aprendida durante su entrenamiento, sino que puede consultar una fuente externa controlada por el usuario y ejecutar operaciones específicas sobre ella.

La solución utiliza archivos JSON locales con información ficticia. Por tanto, representa una demostración académica del funcionamiento de MCP y no una implementación conectada a sistemas bancarios reales.

## 2. Necesidad identificada

La gestión de iniciativas requiere revisar frecuentemente información distribuida en distintas fuentes. Algunas de las preguntas habituales son:

- ¿Qué iniciativas se encuentran activas?
- ¿Cuál es el avance de cada iniciativa?
- ¿En qué ambiente se está trabajando?
- ¿Cuál es el próximo paso?
- ¿Existe algún bloqueo pendiente?
- ¿Qué actividades deberían priorizarse hoy?
- ¿Cuál es el procedimiento para realizar una actividad determinada?

Cuando esta información no está centralizada, el usuario debe buscarla manualmente, interpretarla y preparar sus propios resúmenes. El agente propuesto reduce ese esfuerzo al ofrecer un único punto de consulta mediante Claude Desktop.

## 3. Objetivo del proyecto

Desarrollar un servidor MCP personal que permita a Claude consultar y actualizar información estructurada de iniciativas, así como recuperar procedimientos de trabajo, para apoyar la organización y toma de decisiones operativas del usuario.

### Objetivos específicos

- Centralizar información simulada de iniciativas y procedimientos.
- Publicar herramientas que Claude pueda descubrir y ejecutar.
- Consultar iniciativas por nombre o identificador.
- Registrar avances y conservar las modificaciones localmente.
- Obtener resúmenes diarios con próximos pasos y bloqueos.
- Consultar procedimientos utilizando preguntas en lenguaje natural.
- Demostrar la integración entre Claude Desktop y un servidor MCP propio.

## 4. ¿Qué es MCP?

**Model Context Protocol (MCP)** es un protocolo que permite conectar modelos de lenguaje con herramientas y fuentes externas de información mediante una interfaz estandarizada.

En este proyecto, MCP permite separar dos responsabilidades:

- **Claude Desktop** interpreta la intención del usuario, selecciona la capacidad apropiada y presenta el resultado en lenguaje natural.
- **El servidor MCP** controla las operaciones disponibles y el acceso a la información local.

Esta separación hace posible evolucionar las fuentes de datos sin cambiar la manera en que el usuario conversa con Claude. Por ejemplo, los archivos JSON podrían reemplazarse posteriormente por APIs, repositorios documentales o bases de datos autorizadas.

## 5. Descripción del agente

El agente funciona como un **asistente personal especializado en iniciativas y procedimientos**.

No se trata de un modelo de inteligencia artificial entrenado desde cero. Es una solución compuesta por Claude como motor conversacional y un servidor MCP que amplía sus capacidades con información y acciones específicas.

El usuario puede formular solicitudes como:

> ¿Qué iniciativas tengo registradas y cuál es el avance de cada una?

> ¿Qué iniciativa tiene bloqueos pendientes?

> Consulta el procedimiento para un pase a producción.

> Actualiza el avance de la iniciativa INI-002.

Claude interpreta la petición, selecciona una herramienta MCP, envía los parámetros necesarios al servidor y presenta la respuesta de manera comprensible.

## 6. Arquitectura de la solución

```text
Usuario
   |
   | Solicitud en lenguaje natural
   v
Claude Desktop
(MCP Host y cliente MCP)
   |
   | Model Context Protocol mediante STDIO
   v
Servidor FastMCP
(server.py)
   |
   +-- Tools: consultas y actualizaciones
   +-- Resources: información de contexto
   +-- Prompt: plantilla especializada
   |
   v
Fuentes locales simuladas
   +-- data/iniciativas.json
   +-- data/procedimientos.json
   +-- project_context.md
```

### Componentes principales

1. **Usuario:** realiza preguntas o solicita acciones mediante lenguaje natural.
2. **Claude Desktop:** comprende la intención y decide qué capacidad MCP utilizar.
3. **Servidor FastMCP:** recibe la solicitud, ejecuta la función correspondiente y devuelve datos estructurados.
4. **Fuentes locales:** almacenan las iniciativas, los procedimientos y el contexto del proyecto.

## 7. Flujo de funcionamiento

El flujo general de una consulta es el siguiente:

1. El usuario escribe una solicitud en Claude Desktop.
2. Claude analiza la intención del mensaje.
3. Claude identifica la herramienta MCP apropiada.
4. El servidor recibe la invocación y sus parámetros.
5. La función consulta o modifica la fuente local correspondiente.
6. El servidor devuelve un resultado estructurado.
7. Claude transforma el resultado en una respuesta clara para el usuario.

Por ejemplo, ante la pregunta “¿Cuál es el avance de INI-002?”, Claude puede ejecutar `consultar_iniciativa` con el identificador recibido. El servidor busca el registro en `iniciativas.json` y devuelve el estado actual sin necesidad de que Claude invente o memorice esa información.

## 8. Capacidades implementadas

### 8.1 Herramientas MCP

Las herramientas representan acciones que Claude puede solicitar al servidor.

#### `listar_iniciativas`

Devuelve todas las iniciativas registradas. Permite obtener una vista general con información como estado, ambiente, avance, responsable, fecha objetivo, próximo paso y bloqueos.

#### `consultar_iniciativa`

Busca una iniciativa mediante su ID o una parte de su nombre. Si encuentra una coincidencia, devuelve el detalle completo; de lo contrario, informa que la iniciativa no existe.

#### `registrar_avance`

Actualiza el porcentaje de avance de una iniciativa y permite modificar opcionalmente su estado, próximo paso y última observación.

La función valida que el porcentaje se encuentre entre 0 y 100. La actualización se guarda en `iniciativas.json`, por lo que permanece disponible después de finalizar la conversación o reiniciar Claude Desktop.

#### `consultar_procedimiento`

Recupera un procedimiento utilizando su ID o nombre. La respuesta contiene su descripción, los pasos registrados y las consideraciones que deben tenerse en cuenta.

#### `resumen_diario`

Genera una vista compacta de las iniciativas. Incluye estado, ambiente, avance, próximo paso y bloqueos, proporcionando a Claude la información necesaria para preparar una revisión diaria.

### 8.2 Recursos MCP

Los recursos permiten proporcionar información de solo lectura como contexto reutilizable.

#### `iniciativas://actual`

Expone el contenido completo y actualizado de las iniciativas registradas.

#### `context://project`

Expone la definición, el alcance y la arquitectura del proyecto almacenados en `project_context.md`.

### 8.3 Prompt MCP

#### `resumen_iniciativas`

Es una plantilla especializada que orienta a Claude para elaborar un resumen ejecutivo. Solicita presentar estados, ambientes, avances, próximos pasos, bloqueos y prioridades, evitando inventar información no disponible en el servidor.

## 9. Modelo de información

### Iniciativa

Cada iniciativa contiene los siguientes datos:

- Identificador.
- Nombre y descripción.
- Estado actual.
- Ambiente de trabajo.
- Porcentaje de avance.
- Próximo paso.
- Responsable.
- Fecha objetivo.
- Bloqueos.
- Fecha de última actualización.
- Última observación, cuando haya sido registrada.

### Procedimiento

Cada procedimiento contiene:

- Identificador.
- Nombre.
- Descripción.
- Lista ordenada de pasos.
- Consideraciones relevantes.

## 10. Integración con Claude Desktop

La integración utiliza **STDIO**, mecanismo mediante el cual Claude Desktop inicia el proceso Python y se comunica con él por su entrada y salida estándar. Por tratarse de un servidor local, no es necesario publicar un servicio web ni abrir un puerto de red.

El servidor se registra en Claude Desktop mediante FastMCP:

```bash
uv run fastmcp install claude-desktop server.py \
  --name "Asistente Personal de Iniciativas y Procedimientos"
```

Después de reiniciar Claude Desktop, las herramientas quedan disponibles para las conversaciones. Cuando una solicitud coincide con una capacidad del servidor, Claude puede invocarla y utilizar el resultado para responder.

### Responsabilidades durante la integración

| Componente | Responsabilidad |
|---|---|
| Usuario | Formula la consulta y autoriza las acciones necesarias |
| Claude Desktop | Interpreta la solicitud y selecciona la herramienta |
| Protocolo MCP | Estandariza la comunicación entre cliente y servidor |
| FastMCP Server | Ejecuta la lógica controlada del proyecto |
| Archivos JSON | Conservan la información simulada |

## 11. Ejemplos de interacción

### Consulta general

```text
Usuario: Lista mis iniciativas y señala cuáles requieren atención.
Claude: ejecuta listar_iniciativas y organiza los resultados por prioridad.
```

### Consulta específica

```text
Usuario: ¿Cuál es el estado de INI-002 y qué bloqueo presenta?
Claude: ejecuta consultar_iniciativa con el identificador INI-002.
```

### Consulta de procedimiento

```text
Usuario: ¿Cuál es el procedimiento registrado para un pase a producción?
Claude: ejecuta consultar_procedimiento y presenta los pasos encontrados.
```

### Registro de avance

```text
Usuario: Actualiza INI-002 a 80 % y registra el próximo paso.
Claude: ejecuta registrar_avance y confirma los datos almacenados.
```

### Resumen personal

```text
Usuario: Dame mi resumen de iniciativas para comenzar el día.
Claude: ejecuta resumen_diario y destaca avances, próximos pasos y bloqueos.
```

## 12. Valor aportado

El agente aporta valor al usuario porque:

- Reduce el tiempo empleado en buscar información.
- Centraliza el seguimiento de iniciativas.
- Facilita la identificación de bloqueos y próximos pasos.
- Permite consultar procedimientos mediante lenguaje natural.
- Mantiene los avances registrados entre conversaciones.
- Ofrece una base extensible para futuras integraciones.
- Limita las operaciones a funciones explícitamente publicadas por el servidor.

## 13. Uso ético y responsable de la inteligencia artificial

### Uso de datos simulados

El proyecto emplea información ficticia con fines académicos. No contiene datos reales de clientes, colaboradores, tarjetas, cuentas, operaciones ni sistemas internos.

### Privacidad y confidencialidad

No deben almacenarse contraseñas, tokens, secretos o información confidencial en el código ni en los archivos JSON. Una evolución empresarial tendría que incorporar mecanismos autorizados para gestionar identidades, secretos y permisos.

### Supervisión humana

Las respuestas generadas por Claude deben considerarse asistencia para el usuario. La información debe verificarse antes de tomar decisiones o ejecutar actividades con impacto operativo.

### Límites de autonomía

El agente no está diseñado para aprobar despliegues, ejecutar pases a producción, modificar plataformas bancarias ni tomar decisiones críticas de manera autónoma. Las acciones sensibles requieren validación y autorización humana explícita.

### Transparencia

El usuario debe conocer qué información fue consultada y qué herramienta se utilizó. Cuando un dato no se encuentra disponible, el agente debe indicarlo claramente y evitar presentar suposiciones como hechos.

### Trazabilidad

Una implementación empresarial debe registrar quién realizó una consulta o modificación, cuándo ocurrió, qué herramienta fue utilizada y cuál fue el resultado.

### Control de acceso

En un entorno real deben implementarse autenticación, autorización por roles y el principio de mínimo privilegio. Cada usuario debe acceder únicamente a la información necesaria para desempeñar su función.

### Responsabilidad

Claude y el servidor MCP son herramientas de apoyo. La responsabilidad final sobre las decisiones y acciones permanece en las personas autorizadas.

## 14. Alineación con la propuesta de agente personal Interbank

El proyecto se encuentra alineado conceptualmente con una propuesta de agente personal para iniciativas y procedimientos porque:

- Centraliza información necesaria para el seguimiento diario.
- Permite consultar iniciativas mediante lenguaje natural.
- Identifica avances, próximos pasos y bloqueos.
- Facilita el acceso a procedimientos de trabajo.
- Genera resúmenes para apoyar la priorización.
- Permite registrar actualizaciones de manera estructurada.
- Utiliza una arquitectura extensible basada en capacidades MCP.

La versión desarrollada debe entenderse como una primera aproximación académica. Para convertirse en una solución institucional sería necesario reemplazar las fuentes simuladas por integraciones corporativas autorizadas e incorporar controles de seguridad, auditoría y gobierno de datos.

## 15. Alcance actual

La versión actual incluye:

- Un servidor MCP local desarrollado en Python.
- Cinco herramientas para iniciativas y procedimientos.
- Dos recursos de contexto.
- Un prompt especializado.
- Persistencia mediante archivos JSON.
- Integración con Claude Desktop.
- Validaciones básicas sobre las actualizaciones.

## 16. Limitaciones

El prototipo no incluye:

- Conexión con sistemas reales de Interbank.
- Autenticación o autorización de usuarios.
- Auditoría de operaciones.
- Cifrado o gestión empresarial de secretos.
- Control de concurrencia sobre los archivos JSON.
- Integración con GitHub, Azure DevOps, SharePoint o bases de datos.
- Ejecución automática de procedimientos operativos.
- Arquitectura multiagente, RAG o base vectorial.

Estas limitaciones mantienen la solución sencilla y apropiada para demostrar el patrón MCP dentro del alcance académico.

## 17. Evolución propuesta

Una siguiente versión podría incorporar:

1. Autenticación y autorización por roles.
2. Registro de auditoría para consultas y modificaciones.
3. Integración con fuentes corporativas autorizadas.
4. Uso de una base de datos con control de concurrencia.
5. Gestión segura de credenciales y secretos.
6. Confirmación humana antes de operaciones sensibles.
7. Búsqueda documental para procedimientos aprobados.
8. Notificaciones y seguimiento de fechas objetivo.

## 18. Conclusiones

El proyecto demuestra que es posible ampliar las capacidades de Claude mediante un servidor MCP desarrollado en Python. La solución permite consultar información externa al modelo, recuperar procedimientos, generar resúmenes y registrar cambios persistentes a través de una interfaz conversacional.

La separación entre Claude y el servidor MCP permite controlar las acciones disponibles y las fuentes consultadas. Esta característica facilita la evolución futura del prototipo hacia integraciones más completas sin modificar la experiencia conversacional del usuario.

El agente cumple su objetivo como asistente personal académico para la gestión de iniciativas y procedimientos. Además, incorpora principios de uso responsable: datos simulados, supervisión humana, transparencia, límites de autonomía y protección de información sensible.

---

**Nota:** Este documento describe el diseño y funcionamiento del agente. Las pruebas de ejecución se presentan en un documento independiente.
