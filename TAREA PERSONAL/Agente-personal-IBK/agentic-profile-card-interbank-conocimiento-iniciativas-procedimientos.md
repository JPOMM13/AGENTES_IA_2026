# AGENTIC PROFILE CARD
## Agente de Conocimiento de Iniciativas y Procedimientos – Interbank

### 1. Objetivo
Centralizar y facilitar el acceso al conocimiento relacionado con iniciativas, proyectos y procedimientos internos de diferentes equipos.

El agente debe permitir consultar rápidamente:
- De qué trata una iniciativa.
- Estado, alcance, responsables y fechas importantes.
- Documentación relacionada.
- Procedimientos internos y pasos para ejecutar una tarea.

---

### 2. Qué información recibe

El agente podrá recibir conocimiento desde:

- Conversaciones con el usuario.
- PDF.
- Word.
- Excel.
- PowerPoint.
- Documentación técnica.
- Wikis o repositorios internos.
- Grabaciones de reuniones, capacitaciones o demostraciones.

Ejemplos de iniciativas:

- Samsung Pay.
- COFT AMEX.
- Migración DevOps de Azure a GitHub Actions.
- Otros proyectos o iniciativas internas.

Ejemplos de procedimientos:

- Pase a producción.
- Conexión a Teradata.
- Configuración de ambientes.
- Ejecución de pruebas.
- Despliegues.
- Uso de herramientas internas.

---

### 3. Capacidades principales

El agente debe poder:

**Guardar conocimiento**

Registrar información relevante proporcionada por los usuarios o encontrada en documentos.

**Consultar iniciativas**

Responder preguntas como:

> ¿Cuál es el alcance de Samsung Pay?

> ¿Qué fecha tenemos para pasar a producción?

> ¿Qué iniciativas están pendientes?

**Consultar procedimientos**

Responder:

> ¿Cómo hago un pase a producción?

> ¿Cómo me conecto a Teradata?

Mostrando los pasos encontrados en la documentación oficial.

**Relacionar información**

Relacionar conversaciones, documentos y archivos pertenecientes a una misma iniciativa o procedimiento.

---

### 4. Conocimiento desde grabaciones

Las grabaciones deben convertirse también en una fuente de conocimiento.

El procesamiento debe considerar:

**Audio**
- Transcripción de lo explicado por las personas.

**Imagen / video**
- Pantallas mostradas.
- Formularios.
- Botones.
- Campos.
- Menús.
- Configuraciones.
- Diagramas.

Ejemplo:

En una grabación alguien dice:

> “Ingresamos los datos y continuamos.”

Pero en pantalla aparece un formulario con:

- Ambiente
- Aplicación
- Versión
- Responsable
- Fecha de despliegue

El agente debe capturar también esa información visual.

El conocimiento final podría convertirse en:

```text
Paso 1: Abrir el formulario de despliegue.

Paso 2: Completar:
- Ambiente
- Aplicación
- Versión
- Responsable
- Fecha de despliegue

Paso 3: Validar la información.

Paso 4: Continuar con el despliegue.
```

Esto permite transformar una grabación en un **procedimiento reutilizable**.

---

### 5. Recuperación de conocimiento

El agente debe buscar primero en el conocimiento disponible mediante RAG.

Fuentes posibles:

Usuario  
↓  
Agente  
↓  
RAG  
↓  

- Iniciativas
- Documentos
- Procedimientos
- Grabaciones procesadas
- Conocimiento previamente registrado

Si encuentra información confiable:

> responde indicando la fuente.

Si no encuentra suficiente información:

> indica que no tiene evidencia suficiente y solicita información adicional.

No debe inventar procedimientos.

---

### 6. Memoria

**Memoria de iniciativas**

Guardar información como:

- Nombre.
- Objetivo.
- Alcance.
- Estado.
- Responsable.
- Fechas importantes.
- Dependencias.
- Documentos relacionados.
- Decisiones tomadas.

**Memoria de procedimientos**

Guardar:

- Nombre del procedimiento.
- Equipo responsable.
- Objetivo.
- Prerrequisitos.
- Pasos.
- Evidencias o capturas.
- Fuente.
- Fecha de actualización.

Un mismo procedimiento puede tener variantes según:

- Equipo.
- Sistema.
- Ambiente.
- Tecnología.

Por ello, el agente no debe asumir que existe un único procedimiento universal.

---

### 7. Tipo de agente

Principalmente:

**Agente basado en conocimiento + memoria contextual.**

Utiliza:

- RAG para recuperar información.
- Memoria para conservar contexto relevante.
- ReAct cuando necesite consultar diferentes fuentes o herramientas.
- Capacidades multimodales para interpretar documentos, imágenes y grabaciones.

Inicialmente puede funcionar como **un solo agente**.

Posteriormente podría evolucionar hacia agentes especializados:

```text
Usuario
   │
   ▼
Agente de Conocimiento
   │
   ├── Iniciativas
   ├── Procedimientos
   ├── Documentos
   └── Grabaciones / Multimodalidad
```

---

### 8. Regla principal

El agente debe diferenciar siempre entre:

**Información documentada**

y

**Información inferida.**

Nunca debe presentar una inferencia como un procedimiento oficial.

Cuando responda sobre un procedimiento crítico debe indicar:

- Fuente.
- Equipo responsable.
- Fecha o versión disponible.

---

## Resultado esperado

Crear una memoria corporativa inteligente donde una persona pueda preguntar:

> ¿Qué sabemos de Samsung Pay?

> ¿Cuándo debemos entregar esta iniciativa?

> ¿Cómo hago el pase a producción?

> ¿Cómo me conecto a Teradata?

> ¿Dónde está el documento donde se explicó esto?

Y obtener una respuesta basada en el conocimiento almacenado, incluyendo documentos, conversaciones y procedimientos extraídos de grabaciones.
