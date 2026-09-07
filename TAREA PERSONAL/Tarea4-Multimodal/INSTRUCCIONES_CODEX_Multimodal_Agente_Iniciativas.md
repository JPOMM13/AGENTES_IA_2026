# Instrucciones para Codex — Evolución Multimodal del Agente de Iniciativas y Procedimientos

## 1. Objetivo

Tomar como base el proyecto existente **`Tarea2-LangGraph`** y agregarle una capacidad multimodal para procesar grabaciones de reuniones en formato **MP4**.

**No crear un agente nuevo ni rehacer la arquitectura actual.**  
Debe conservarse el mismo agente multiagente con LangGraph y sus capacidades actuales:

- Supervisor.
- Agente de iniciativas.
- Agente de procedimientos.
- Agente de seguimiento.
- Agente de estado técnico.
- Consolidador.
- Actualización de actores.
- Datos simulados en JSON.
- Cálculo del avance técnico comparando `specs.json` con `github_mock.json`.

La nueva capacidad debe complementar al agente existente permitiéndole obtener información adicional desde una reunión grabada.

---

## 2. Proyecto base que debe conservarse

Trabajar sobre la estructura actual:

```text
Tarea2-LangGraph/
├── src/
│   ├── agents.py
│   ├── graph.py
│   ├── state.py
│   ├── tools.py
│   ├── llm.py
│   └── config.py
├── data/
│   ├── initiatives.json
│   ├── procedures.json
│   ├── tracking.json
│   ├── specs.json
│   └── github_mock.json
├── requirements.txt
├── .env.example
└── README.md
```

No eliminar ni reemplazar las funcionalidades existentes.

Las consultas actuales deben seguir funcionando, por ejemplo:

```text
¿Cuál es el estado de Samsung Pay?
¿Cómo hago un pase a producción?
¿Qué falta para Samsung Pay?
¿Cuál es el avance técnico de Samsung Pay?
¿Cómo va Samsung Pay y qué falta para pasar a producción?
```

---

## 3. Nueva capacidad: reunión multimodal

Agregar al mismo agente la posibilidad de procesar un archivo:

```text
reunion_samsung_pay.mp4
```

El flujo debe ser:

```text
MP4
 │
 ├── Audio ──> Transcripción ──> Texto
 │
 └── Video ──> Frames ──> Modelo multimodal ──> Información visual
                                      │
                                      ▼
                         Contexto de la reunión
                                      │
                                      ▼
                       Agente existente / Consolidador
```

La finalidad es recuperar información que puede aparecer:

- hablada durante la reunión;
- escrita o visible en una pantalla compartida.

Ejemplo: en el audio se menciona una fecha de producción, mientras que en pantalla aparece `Security Scan: PENDING`.

---

## 4. Implementación solicitada

### 4.1 Mantener el Supervisor actual

Agregar una nueva intención:

```text
reunion_multimodal
```

Ejemplo:

```text
Procesa la reunión input/reunion_samsung_pay.mp4
```

El Supervisor debe enviar esta solicitud al nuevo nodo multimodal.

No modificar innecesariamente las demás rutas del grafo.

---

### 4.2 Agregar un nodo multimodal

Agregar un nodo, por ejemplo:

```text
meeting
```

al `StateGraph`.

Este nodo debe encargarse de:

1. recibir la ruta del MP4;
2. extraer/transcribir el audio;
3. extraer entre 3 y 5 frames representativos;
4. analizar los frames con un modelo con visión;
5. consolidar lo encontrado;
6. guardar el resultado en el estado compartido de LangGraph.

Crear un módulo sencillo, por ejemplo:

```text
src/multimodal.py
```

No crear otro proyecto ni otro grafo.

---

## 5. Estado compartido

Extender `InitiativeState` agregando únicamente lo necesario:

```python
meeting_file: str
meeting_transcription: str
meeting_visual_evidence: list
meeting_context: dict
```

`meeting_context` debe conservar durante la ejecución información como:

```python
{
    "initiative": "Samsung Pay Visa",
    "dates": [],
    "responsibles": [],
    "agreements": [],
    "pending": [],
    "risks": [],
    "technical_information": [],
    "sources": {}
}
```

No implementar base de datos ni memoria persistente.

---

## 6. Procesamiento del MP4

### Audio

Extraer el audio del MP4 y transcribirlo.

Para mantener la demo sencilla, utilizar **Whisper local / faster-whisper**.

Ejemplo de información obtenida:

```text
Samsung Pay terminó las pruebas de QA.
La salida a producción está prevista para el 28 de agosto.
Carlos gestionará la aprobación del CAB.
```

### Video

Extraer solo **3 a 5 frames**, distribuidos a lo largo del video.

Analizar cada frame mediante un **modelo multimodal con visión disponible en Ollama**.

Configurar el modelo desde `.env`, por ejemplo:

```env
VISION_MODEL=llava:latest
```

El análisis visual debe buscar información útil para el agente, no describir toda la imagen:

- iniciativa;
- estado;
- fechas;
- repositorio;
- rama;
- pipeline;
- pruebas;
- aprobaciones;
- pendientes;
- riesgos.

Ejemplo de contenido visible:

```text
Repository: wallet-api
Branch: feature/samsung-pay
Pipeline: SUCCESS
QA: APPROVED
Security Scan: PENDING
```

---

## 7. Integración con la información existente

El procesamiento de la reunión **no debe modificar los JSON base**.

Debe complementar temporalmente la información existente.

Así, el agente podrá combinar:

```text
initiatives.json
tracking.json
specs.json
github_mock.json
+
transcripción de reunión
+
evidencia visual de reunión
```

Si la reunión contiene un dato diferente al JSON, no sobrescribirlo automáticamente. Mostrar ambos y señalar que la reunión contiene información adicional o más reciente.

---

## 8. Consultas posteriores

Después de procesar una reunión, deben funcionar preguntas como:

```text
¿Qué se acordó en la reunión de Samsung Pay?
¿Qué quedó pendiente?
¿Qué información apareció en pantalla?
¿Quién gestionará el CAB?
¿El Security Scan está terminado?
¿Cómo va Samsung Pay considerando la última reunión?
¿De dónde obtuviste que el Security Scan está pendiente?
```

El agente debe poder indicar el origen cuando corresponda:

```text
Datos base
Audio de la reunión
Pantalla compartida
```

Ejemplo:

```text
El Security Scan aparece como PENDING.
Fuente: pantalla compartida de la reunión.
```

---

## 9. Caso de prueba

Usar **Samsung Pay Visa**, que ya existe en `initiatives.json`.

Crear o utilizar un MP4 corto de aproximadamente 1 a 3 minutos donde:

- se mencione verbalmente una fecha, responsable o acuerdo;
- se comparta una pantalla con al menos un dato técnico que no sea mencionado verbalmente.

La prueba debe demostrar claramente:

```text
Audio -> Texto
Video -> Imagen -> Texto
Ambas fuentes -> Respuesta del agente
```

---

## 10. Restricciones

Mantener esta tarea como una demo académica sencilla.

**No implementar:**

- RAG;
- embeddings;
- base vectorial;
- Cosmos DB;
- MCP;
- integración real con Teams;
- integración real con GitHub;
- Azure;
- frontend web;
- nuevos agentes innecesarios;
- persistencia permanente de reuniones.

---

## 11. Archivos a modificar o agregar

Preferentemente limitar los cambios a:

```text
src/state.py
src/graph.py
src/agents.py
src/config.py
src/multimodal.py        # nuevo
requirements.txt
.env.example
README.md
```

Si es necesario separar funciones, se puede agregar un módulo auxiliar, pero mantener el código pequeño y entendible.

---

## 12. Criterios de aceptación

La implementación estará completa cuando:

- las consultas actuales del proyecto sigan funcionando;
- el agente pueda recibir un MP4;
- pueda transcribir el audio;
- pueda extraer y analizar frames;
- combine audio + información visual;
- conserve esa información en el estado de LangGraph durante la sesión;
- responda preguntas posteriores sobre la reunión;
- indique si un dato proviene del audio o de la pantalla;
- no invente información que no exista en las fuentes;
- el código pueda ejecutarse localmente y esté documentado en el README.

## Resultado esperado

El resultado final debe seguir siendo el **mismo Agente de Iniciativas y Procedimientos**, pero ahora con una nueva capacidad:

```text
Usuario
   ↓
Supervisor LangGraph
   ↓
Iniciativas / Procedimientos / Seguimiento / Estado técnico
   +
Reunión MP4
   ├── Audio -> Transcripción
   └── Video -> Frames -> MLLM
   ↓
Consolidador
   ↓
Respuesta única y verificable
```

Priorizar que la demo funcione de punta a punta antes de agregar cualquier mejora adicional.
