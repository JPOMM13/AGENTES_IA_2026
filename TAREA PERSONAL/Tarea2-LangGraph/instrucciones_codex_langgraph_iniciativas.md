# Instrucciones para Codex — Asistente Multiagente de Seguimiento de Iniciativas con LangGraph

## 1. Objetivo

Desarrollar un **MVP académico en Python con LangGraph** que demuestre un sistema multiagente capaz de consultar y consolidar información sobre iniciativas tecnológicas.

El sistema debe permitir responder preguntas relacionadas con:

1. Información general de una iniciativa.
2. Procedimientos internos.
3. Seguimiento y pendientes.
4. Estado técnico del desarrollo.
5. Porcentaje estimado de avance técnico comparando un **Spec técnico** contra evidencia simulada de un repositorio GitHub.

La solución debe ser sencilla de ejecutar, fácil de explicar en clase y alineada con los conceptos de LangGraph: **nodos, aristas, estado compartido, enrutamiento condicional y coordinación entre agentes**.

---

## 2. Caso de uso

En el trabajo existen varias iniciativas tecnológicas en las que participan áreas como Negocio, Desarrollo, QA y Operaciones.

La información puede encontrarse distribuida entre documentación funcional, especificaciones técnicas, procedimientos y repositorios de código.

El objetivo del agente es convertirse en un **punto único de consulta**, permitiendo obtener una visión consolidada de cada iniciativa.

Ejemplos de preguntas:

- ¿Cuál es el estado de Samsung Pay?
- ¿Qué falta para terminar Samsung Pay?
- ¿Cuál es el procedimiento de pase a producción?
- ¿Cuál es el avance técnico de Samsung Pay?
- ¿Qué componentes del Spec todavía no están implementados?
- ¿Cómo va Samsung Pay y qué falta para pasar a producción?

---

## 3. Alcance del MVP

Este desarrollo es una **demostración académica**, por lo tanto NO debe conectarse a sistemas reales.

### Integraciones que deben ser simuladas

- GitHub.
- Repositorios.
- Ramas.
- Pull Requests.
- Commits.
- Tests.
- Specs técnicos.
- Información de iniciativas.
- Procedimientos.
- Bloqueos.
- Seguimiento.

Toda la información debe almacenarse localmente en archivos JSON o estructuras Python.

### No implementar por ahora

- GitHub API real.
- Azure DevOps API.
- SharePoint.
- Microsoft 365.
- Cosmos DB.
- Redis.
- Vector DB.
- MCP.
- APIM.
- Autenticación empresarial.
- Streamlit.
- Docker.
- Servicios cloud.

El foco del ejercicio es **LangGraph y la orquestación**.

---

## 4. Arquitectura lógica

```text
                               USUARIO
                                  ↓
                         ┌─────────────────┐
                         │   SUPERVISOR    │
                         └────────┬────────┘
                                  │
          ┌───────────────────────┼────────────────────────┐
          │                       │                        │
          ↓                       ↓                        ↓
   ┌─────────────┐        ┌───────────────┐        ┌──────────────┐
   │ INICIATIVAS │        │ PROCEDIMIENTOS│        │ SEGUIMIENTO  │
   └──────┬──────┘        └───────┬───────┘        └──────┬───────┘
          │                       │                        │
          │                       └──────────────┐         │
          │                                      ↓         ↓
          │                            ┌──────────────────────┐
          │                            │   ESTADO TÉCNICO     │
          │                            └──────────┬───────────┘
          │                                       │
          │                     ┌─────────────────┴─────────────────┐
          │                     │                                   │
          │                     ↓                                   ↓
          │            ┌──────────────────┐               ┌──────────────────┐
          │            │ REPOSITORIO/RAMA │               │   SPEC TÉCNICO   │
          │            │   SIMULADO       │               │    SIMULADO      │
          │            └─────────┬────────┘               └─────────┬────────┘
          │                      │                                  │
          │                      └──────────────┬───────────────────┘
          │                                     ↓
          │                          ┌──────────────────────┐
          │                          │ ANÁLISIS DE AVANCE   │
          │                          │      TÉCNICO         │
          │                          └──────────┬───────────┘
          │                                     │
          └───────────────────────┬─────────────┘
                                  ↓
                         ┌─────────────────┐
                         │ CONSOLIDADOR    │
                         └────────┬────────┘
                                  ↓
                              RESPUESTA
                                  ↓
                                 END
```

---

## 5. Agentes / nodos

### 5.1 Supervisor

Responsabilidades:

- Recibir la pregunta.
- Identificar la iniciativa mencionada.
- Detectar qué capacidades son necesarias.
- Enrutar la solicitud hacia uno o varios nodos.

Tipos de intención mínimos:

```text
iniciativa
procedimiento
seguimiento
estado_tecnico
consulta_compuesta
```

Ejemplos:

```text
"¿Qué es Samsung Pay?"
→ iniciativa

"¿Cómo hago un pase a producción?"
→ procedimiento

"¿Qué falta para Samsung Pay?"
→ seguimiento

"¿Cuál es el avance técnico de Samsung Pay?"
→ estado_tecnico

"¿Cómo va Samsung Pay y qué falta para pasar a producción?"
→ consulta_compuesta
```

El Supervisor puede utilizar un LLM o una clasificación sencilla. Para facilitar la ejecución, implementar también un modo determinístico que no dependa obligatoriamente de una API externa.

### 5.2 Agente de Iniciativas

Debe consultar información simulada sobre:

- nombre;
- descripción;
- objetivo;
- alcance;
- estado;
- ambiente;
- responsable;
- fecha objetivo;
- repositorios involucrados;
- rama asociada;
- Spec técnico asociado.

Ejemplo:

```text
Samsung Pay Visa
Estado: UAT
Ambiente actual: UAT
Próximo hito: Producción
Responsable: Equipo Wallets
Fecha objetivo: 30/09/2026
Repositorio: wallet-api
Rama: feature/samsung-pay
```

### 5.3 Agente de Procedimientos

Debe responder preguntas relacionadas con procedimientos internos simulados.

Crear como mínimo:

1. Pase a producción.
2. Conexión a Teradata.
3. Validación previa a UAT.

Cada procedimiento debe incluir:

- objetivo;
- precondiciones;
- pasos;
- evidencias requeridas;
- responsable;
- resultado esperado.

### 5.4 Agente de Seguimiento

Debe identificar:

- pendientes;
- bloqueos;
- próximo paso;
- dependencias;
- estado funcional;
- riesgos básicos.

Ejemplo:

```text
Pendientes:
- Completar pruebas QA.
- Aprobar evidencia de seguridad.

Bloqueos:
- Certificado del proveedor pendiente.

Próximo paso:
- Completar pruebas y solicitar aprobación para pase a producción.
```

### 5.5 Agente de Estado Técnico

Este es el componente diferencial.

Debe comparar:

```text
SPEC TÉCNICO
        VS
REPOSITORIO / RAMA SIMULADA
```

Su objetivo es determinar qué requerimientos definidos en el Spec ya están implementados, cuáles están parcialmente implementados y cuáles están pendientes.

**No calcular el progreso en función del número de commits.**

El porcentaje debe derivarse del grado de cumplimiento del Spec.

---

## 6. Cálculo del avance técnico

Cada elemento del Spec debe tener una estructura similar a:

```json
{
  "id": "REQ-001",
  "nombre": "Endpoint de tokenización",
  "peso": 20,
  "criterios": [
    "Endpoint disponible",
    "Validación de request",
    "Manejo de errores"
  ]
}
```

El repositorio simulado debe registrar evidencia:

```json
{
  "requirement_id": "REQ-001",
  "status": "completed",
  "evidence": [
    "src/tokenization/service.py",
    "tests/test_tokenization.py"
  ]
}
```

Estados admitidos:

```text
completed
partial
pending
```

Factores:

```text
completed = 1.0
partial   = 0.5
pending   = 0.0
```

Fórmula:

```text
avance = Σ (peso_requerimiento × factor_estado) / Σ pesos
```

Ejemplo:

```text
REQ-001 peso 20 → completed = 20
REQ-002 peso 25 → completed = 25
REQ-003 peso 20 → completed = 20
REQ-004 peso 20 → partial   = 10
REQ-005 peso 15 → pending   = 0

Total = 75 / 100
Avance técnico estimado = 75 %
```

La respuesta debe explicar cómo se obtiene el porcentaje.

---

## 7. Fuente de verdad simulada

Crear una carpeta:

```text
data/
├── initiatives.json
├── procedures.json
├── tracking.json
├── specs.json
└── github_mock.json
```

---

## 8. Datos simulados mínimos

### 8.1 initiatives.json

Crear al menos tres iniciativas:

#### Samsung Pay Visa

```text
estado: UAT
ambiente: UAT
proximo_hito: Producción
repositorio: wallet-api
rama: feature/samsung-pay
spec: SPEC-SAMSUNG-001
```

#### Migración Azure DevOps a GitHub Actions

```text
estado: En desarrollo
ambiente: DEV
repositorio: devops-platform
rama: feature/github-actions
spec: SPEC-DEVOPS-001
```

#### COFT Amex

```text
estado: Análisis
ambiente: DEV
repositorio: coft-service
rama: feature/coft-amex
spec: SPEC-COFT-001
```

Completar cada iniciativa con descripción, objetivo, responsable, fecha objetivo, alcance y bloqueos.

### 8.2 specs.json

Crear un Spec técnico para cada iniciativa.

Para Samsung Pay incluir como mínimo:

```text
REQ-001 API de tokenización              peso 20
REQ-002 Integración Samsung Pay          peso 25
REQ-003 Validación de criptograma        peso 20
REQ-004 Pruebas unitarias                peso 20
REQ-005 Pipeline CI/CD                    peso 15
```

### 8.3 github_mock.json

Simular:

- repositorio;
- rama;
- último commit;
- cantidad de commits;
- pull requests;
- archivos modificados;
- tests;
- evidencias por requerimiento.

Para Samsung Pay:

```text
REQ-001 → completed
REQ-002 → completed
REQ-003 → completed
REQ-004 → partial
REQ-005 → pending
```

Resultado esperado:

```text
avance técnico = 75 %
```

El número de commits puede mostrarse como información complementaria, pero nunca debe utilizarse directamente para calcular el porcentaje.

### 8.4 tracking.json

Ejemplo para Samsung Pay:

```text
pendientes:
- Completar pruebas unitarias.
- Configurar pipeline CI/CD.
- Ejecutar pruebas QA.

bloqueos:
- Ninguno crítico.

proximo_paso:
- Completar pruebas antes de solicitar pase a producción.
```

### 8.5 procedures.json

Crear como mínimo:

```text
PROC-001 Pase a producción
PROC-002 Conexión a Teradata
PROC-003 Validación previa a UAT
```

---

## 9. Estado compartido de LangGraph

Definir un estado con `TypedDict` o equivalente.

Campos sugeridos:

```text
user_query
initiative_name
intent
required_agents
initiative_data
procedure_data
tracking_data
technical_status
technical_progress
technical_evidence
agent_results
final_response
errors
execution_trace
```

No todos los campos deben utilizarse en todas las consultas.

---

## 10. Flujo LangGraph

Flujo mínimo:

```text
START
  ↓
Supervisor
  ↓
Conditional Routing
  │
  ├── Initiative Agent
  ├── Procedure Agent
  ├── Tracking Agent
  └── Technical Status Agent
           ↓
       Consolidator
           ↓
          END
```

Para consultas compuestas, permitir ejecutar más de un agente.

Ejemplo:

```text
"¿Cómo va Samsung Pay y qué falta para pasar a producción?"

Supervisor
      ↓
Iniciativas
      ↓
Seguimiento
      ↓
Estado Técnico
      ↓
Procedimientos
      ↓
Consolidador
      ↓
END
```

No es necesario implementar paralelismo para el MVP. Priorizar claridad del flujo.

---

## 11. Consolidador

Crear un nodo encargado de construir una respuesta única, evitando repeticiones.

Ejemplo esperado:

```text
INICIATIVA: Samsung Pay Visa

Estado general:
UAT

Avance técnico estimado:
75 %

Implementado:
- API de tokenización
- Integración Samsung Pay
- Validación de criptograma

Parcial:
- Pruebas unitarias

Pendiente:
- Pipeline CI/CD

Seguimiento:
- Completar pruebas unitarias.
- Ejecutar validación QA.

Próximo paso:
Completar pendientes técnicos y preparar el pase a producción.
```

---

## 12. Uso opcional de LLM

El sistema debe poder demostrarse incluso si no existe acceso a una API.

Implementar preferentemente dos modos:

```text
USE_LLM=true
USE_LLM=false
```

### Con LLM

Se puede utilizar OpenAI, Ollama u otro modelo compatible.

El LLM puede apoyar en:

- clasificación de intención;
- identificación de iniciativa;
- consolidación de respuesta.

### Sin LLM

Usar reglas, palabras clave y funciones Python determinísticas.

El cálculo técnico debe ser siempre determinístico y no depender del LLM.

---

## 13. Principio de diseño

Separar claramente:

```text
RAZONAMIENTO / INTERPRETACIÓN
             ↓
            LLM

DATOS Y CÁLCULOS
             ↓
      FUNCIONES PYTHON
```

El LLM **no debe inventar**:

- porcentaje técnico;
- estado de iniciativa;
- bloqueos;
- fechas;
- procedimientos;
- evidencia del repositorio.

Estos datos deben provenir exclusivamente de los JSON simulados.

---

## 14. Tools sugeridas

Implementar funciones sencillas como:

```text
get_initiative(name)
get_procedure(name)
get_tracking(name)
get_spec(spec_id)
get_repository(repo, branch)
calculate_technical_progress(spec, repository)
```

Las funciones deben ser simples y fáciles de explicar.

---

## 15. Manejo de errores

### Iniciativa no encontrada

```text
No encontré la iniciativa solicitada.
Iniciativas disponibles:
- Samsung Pay Visa
- Migración Azure DevOps a GitHub Actions
- COFT Amex
```

### Procedimiento no encontrado

```text
No encontré un procedimiento relacionado con la consulta.
```

### Rama inexistente

```text
La iniciativa está registrada, pero no existe información simulada de la rama asociada.
```

### Spec inexistente

```text
No es posible calcular el avance técnico porque la iniciativa no tiene un Spec técnico asociado.
```

Nunca inventar datos faltantes.

---

## 16. Casos de prueba obligatorios

### Caso 1 — Consulta de iniciativa

```text
¿Cuál es el estado de Samsung Pay?
```

Ruta esperada:

```text
Supervisor → Iniciativas → Consolidador
```

### Caso 2 — Procedimiento

```text
¿Cómo hago un pase a producción?
```

Ruta esperada:

```text
Supervisor → Procedimientos → Consolidador
```

### Caso 3 — Seguimiento

```text
¿Qué falta para Samsung Pay?
```

Ruta esperada:

```text
Supervisor → Seguimiento → Consolidador
```

### Caso 4 — Estado técnico

```text
¿Cuál es el avance técnico de Samsung Pay?
```

Ruta esperada:

```text
Supervisor → Estado Técnico → Spec → GitHub Mock → cálculo → Consolidador
```

Resultado esperado: **75 %**.

### Caso 5 — Consulta compuesta

```text
¿Cómo va Samsung Pay y qué falta para pasar a producción?
```

Debe integrar Iniciativas, Seguimiento, Estado Técnico y Procedimientos.

### Caso 6 — Iniciativa inexistente

```text
¿Cómo va Apple Pay?
```

Debe responder sin alucinar información.

---

## 17. Visualización del grafo

El notebook debe mostrar el grafo de LangGraph usando Mermaid o la funcionalidad disponible en LangGraph.

Debe poder verse conceptualmente como:

```text
START
  ↓
SUPERVISOR
  ↓
ROUTING
  ├── INICIATIVAS
  ├── PROCEDIMIENTOS
  ├── SEGUIMIENTO
  └── ESTADO TÉCNICO
          ↓
     CONSOLIDADOR
          ↓
         END
```

---

## 18. Trazabilidad

En cada ejecución imprimir o almacenar una traza sencilla:

```text
Ruta ejecutada:
Supervisor
→ Initiative Agent
→ Technical Status Agent
→ Consolidator
```

Usar por ejemplo:

```text
execution_trace
```

dentro del State.

---

## 19. Estructura esperada del proyecto

```text
langgraph_initiatives_agent/
│
├── README.md
├── requirements.txt
├── .env.example
│
├── data/
│   ├── initiatives.json
│   ├── procedures.json
│   ├── tracking.json
│   ├── specs.json
│   └── github_mock.json
│
├── src/
│   ├── state.py
│   ├── tools.py
│   ├── agents.py
│   ├── graph.py
│   └── config.py
│
└── notebooks/
    └── langgraph_initiatives_demo.ipynb
```

Para la entrega académica, el archivo principal será:

```text
notebooks/langgraph_initiatives_demo.ipynb
```

---

## 20. Notebook de entrega

El notebook debe contener, en este orden:

1. **Título** — Asistente Multiagente para Seguimiento de Iniciativas Tecnológicas con LangGraph.
2. **Problema** — Información distribuida entre documentación, seguimiento y repositorios.
3. **Objetivo** — Coordinar agentes especializados y consolidar estado funcional y técnico.
4. **Arquitectura** — Mostrar el diagrama.
5. **Datos simulados** — Explicar los JSON.
6. **State** — Mostrar el estado compartido.
7. **Agentes / nodos** — Explicar brevemente cada nodo.
8. **Construcción del grafo** — Mostrar LangGraph.
9. **Visualización del grafo** — Mostrar workflow.
10. **Casos de prueba** — Ejecutar los seis casos.
11. **Resultado** — Mostrar respuestas obtenidas.
12. **Conclusión** — Explicar que las fuentes simuladas pueden reemplazarse por integraciones reales en una evolución futura.

---

## 21. Requisitos técnicos

Priorizar versiones estables de:

```text
python >= 3.11
langgraph
langchain
python-dotenv
```

Agregar adaptador de modelo solo si se utilizará LLM, por ejemplo:

```text
langchain-openai
```

o:

```text
langchain-ollama
```

No agregar dependencias innecesarias.

---

## 22. Calidad del código

El código debe:

- ser modular;
- usar nombres claros;
- contener comentarios breves;
- evitar clases innecesarias;
- evitar sobreingeniería;
- ser fácil de explicar a alguien que está aprendiendo LangGraph;
- mantener separados datos, tools, agentes y grafo;
- poder ejecutarse de principio a fin.

---

## 23. Restricciones

NO:

- crear una arquitectura productiva;
- integrar servicios externos reales;
- utilizar credenciales reales;
- usar bases de datos reales;
- depender de GitHub;
- calcular progreso por número de commits;
- inventar información faltante;
- generar agentes adicionales sin necesidad.

---

## 24. Criterios de aceptación

- [ ] Existe un grafo LangGraph funcional.
- [ ] Existe un Supervisor.
- [ ] Existe un nodo de Iniciativas.
- [ ] Existe un nodo de Procedimientos.
- [ ] Existe un nodo de Seguimiento.
- [ ] Existe un nodo de Estado Técnico.
- [ ] Existe un Consolidador.
- [ ] Se utiliza State compartido.
- [ ] Existe routing condicional.
- [ ] Los datos provienen de JSON locales.
- [ ] GitHub es completamente simulado.
- [ ] El Spec técnico es la referencia para medir progreso.
- [ ] El avance técnico se calcula de forma determinística.
- [ ] Samsung Pay devuelve 75 % de avance en el escenario definido.
- [ ] Se muestra la ruta ejecutada por LangGraph.
- [ ] Se ejecutan los seis casos de prueba.
- [ ] El notebook puede utilizarse directamente como demostración académica.

---

## 25. Resultado esperado del caso principal

Consulta:

```text
¿Cómo va Samsung Pay y qué falta para pasar a producción?
```

Respuesta aproximada:

```text
INICIATIVA
Samsung Pay Visa

Estado general
UAT

Avance técnico estimado
75 %

Implementado
- API de tokenización.
- Integración Samsung Pay.
- Validación de criptograma.

Parcial
- Pruebas unitarias.

Pendiente
- Pipeline CI/CD.

Seguimiento
- Completar pruebas unitarias.
- Ejecutar validación QA.

Próximo paso
Completar los pendientes técnicos y posteriormente ejecutar
el procedimiento de pase a producción.

Ruta LangGraph
Supervisor
→ Iniciativas
→ Seguimiento
→ Estado Técnico
→ Procedimientos
→ Consolidador
→ END
```

---

## 26. Evolución futura — fuera del alcance del MVP

Documentar que las simulaciones pueden reemplazarse posteriormente por:

```text
github_mock.json
        ↓
GitHub / Azure DevOps API

initiatives.json
        ↓
Base corporativa / Cosmos DB

procedures.json
        ↓
SharePoint / RAG

specs.json
        ↓
Repositorio de Specs

tracking.json
        ↓
Jira / Azure Boards / sistema corporativo
```

LangGraph debe mantenerse como capa de orquestación.

---

## 27. Orden recomendado para Codex

Construir primero una versión mínima funcional y ejecutable:

```text
1. Crear datos simulados.
2. Crear funciones de consulta.
3. Implementar cálculo del avance técnico.
4. Definir State.
5. Implementar nodos.
6. Implementar Supervisor.
7. Crear conditional routing.
8. Crear Consolidador.
9. Construir y compilar LangGraph.
10. Ejecutar casos de prueba.
11. Crear notebook final.
12. Documentar ejecución.
```

No agregar complejidad que no contribuya a demostrar LangGraph.

El objetivo principal es que durante la exposición pueda explicarse claramente:

```text
Pregunta
   ↓
Supervisor
   ↓
selección de agentes
   ↓
consulta de fuentes simuladas
   ↓
comparación Spec vs repositorio
   ↓
consolidación
   ↓
respuesta
```

y evidenciar cómo **LangGraph controla el flujo completo**.
