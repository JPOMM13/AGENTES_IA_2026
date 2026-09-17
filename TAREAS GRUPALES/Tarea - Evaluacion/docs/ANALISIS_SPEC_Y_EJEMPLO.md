# Análisis del SPEC y del código de clase

## Alcance del encargo

El usuario pidió analizar el SPEC, revisar el ZIP centrándose en `langsmith_evaluator.py` y `team.py`, y generar código para cumplir la tarea de evaluación. El material adjunto se trató como referencia de requisitos de implementación, no como autorización para acceder a cuentas, publicar documentos ni inventar resultados.

La captura de la tarea pide proponer métricas en Google Docs, implementarlas con LangSmith o DeepEval y documentar los reportes con capturas. Se eligió LangSmith por coherencia con el SPEC. Se proporciona documentación para copiar a Google Docs y una guía de capturas; no se simula haber publicado un documento ni ejecutado un experimento remoto.

## Qué se adapta del ZIP

| Archivo original | Hallazgo | Implementación entregada |
|---|---|---|
| `team.py` | StateGraph, estado compartido, nodos y routing; equipo editorial con supervisor | `agent/graph.py` conserva el patrón de grafo y estado; usa un solo agente con tools determinísticas. `team.py` inicia la CLI. |
| `team.py` | Modelo global fijo y estado editorial | Configuración central, creación diferida del modelo y estado de eventos por sesión. |
| `langsmith_evaluator.py` | Dataset de un artículo; métricas calculadas manualmente sobre `Example.inputs` | Dataset de 15 escenarios, ejecución del agente y comparación de sus `outputs` con `reference_outputs`. |
| `langsmith_evaluator.py` | Crea dataset, pero el `main` no llama a `evaluate` para registrar un experimento de aplicación | `Client.evaluate` registra runs y feedback de evaluadores dentro de un experimento. |
| `langsmith_evaluator.py` | Algunas excepciones producen notas 1 o 0.5 | Las métricas determinísticas fallan con 0; un juez no disponible produce nota ausente y resultado incompleto. |
| `langsmith_evaluator.py` | Judge de tono con parsing de un número libre | Pydantic valida cuatro criterios semánticos de 1 a 5 y una explicación. |

No se extrajo la carpeta `.git` del ZIP ni se reutilizaron sus archivos como repositorio del proyecto.

## Trazabilidad de requisitos

| Requisito | Archivo o prueba |
|---|---|
| Configuración y claves | `config.py`, `.env.example`, `.gitignore` |
| Capa de datos intercambiable | `repositories/base.py`, `repositories/json_repository.py` |
| Entidades del mock | `data/mock_data_eventos.json` |
| Estado y extracción limitada | `agent/state.py`, `agent/prompts.py` |
| Flujo y sesión | `agent/graph.py`, `app.py` |
| Reglas, ranking y precios | `agent/tools.py` |
| 15 escenarios | `evaluation/dataset.py` |
| 11 criterios críticos + juez | `evaluation/evaluators.py` |
| Dataset, experimento y reporte | `evaluation/run_evaluation.py` |
| Casos límite y mutación de salidas | `tests/test_rules.py` |

## Supuestos y límites explícitos

1. Sin Excel y Profile Card, la cobertura de Miraflores/San Isidro, los productos, precios, impuesto mock del 18%, calendario, ranking y política de un pack son supuestos sintéticos. No son hechos comerciales verificados.
2. El feriado del 14 de septiembre de 2026 es exclusivamente mock. El calendario excluye sábados y domingos al buscar días hábiles. No se consultó Internet para completar datos comerciales.
3. Se interpreta “máximo cinco reintentos” como seis intentos totales. La demo no confirma compras, reservas ni pagos; no existen operaciones con efectos que puedan duplicarse por reintento.
4. La recomendación exige los cuatro datos mínimos; las preguntas informativas generales pueden responderse sin pedirlos. Ambigüedad, solicitudes fuera de autonomía y fallos persistentes generan resumen de derivación pendiente.
5. Para evitar alucinaciones en el texto final, la redacción comercial es una plantilla determinística. El LLM elige una apertura validada, sin poder modificar importes ni condiciones. Es una restricción deliberada frente a una redacción libre por LLM.
6. Los filtros léxicos de derivación son conservadores; pueden derivar ante frases con negación o mención indirecta de descuentos/asesores. No constituyen una solución exhaustiva de seguridad. El LLM complementa la detección semántica mediante un campo de riesgo cerrado.
7. No hay autenticación, almacenamiento durable de conversaciones, integración real con asesores ni escritura del histórico. La memoria por sesión y los resúmenes satisfacen la demo; un servicio de producción requiere esas capas adicionales.
8. La evaluación offline no mide extracción real ni juez; las pruebas del SDK verifican firmas y esquemas sin red. La comprobación end-to-end real requiere claves, modelo disponible y acceso a la región de LangSmith.
