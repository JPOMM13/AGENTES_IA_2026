# Validación ejecutada

Fecha local: 6 de septiembre de 2026 (America/Lima).

| Comprobación | Resultado |
|---|---|
| `python -m pytest -q` | 46 pruebas aprobadas. |
| `python -m evaluation.run_evaluation --offline` | 15/15 casos aprobados, 11 métricas determinísticas por caso. |
| Compilación de módulos Python | Correcta. |
| CLI sin clave de OpenAI | Mensaje claro de configuración faltante y salida 2. |
| Evaluación online sin clave de LangSmith | Mensaje claro de configuración faltante y salida 2. |
| Firmas de los evaluadores con el SDK instalado | Verificadas mediante `run_evaluator` sin red. |
| Esquema del juez y fallo del proveedor simulado | Cuatro notas válidas o cuatro notas ausentes; nunca inventa notas. |
| Reporte con feedback ausente | Caso incompleto, no aprobado. |

Las pruebas cubren los quince escenarios del SPEC; seguimiento de datos faltantes; actualización y retirada de campos; invalidación de cotizaciones previas; frontera exacta de 72 horas; stock ausente en el día de recojo; preferencias con y sin consentimiento; reintentos transitorios y errores permanentes; intenciones informativa/recomendación; presupuesto con impuestos; bloqueo de campos de precio/consentimiento en la extracción; salida malformada; y alteraciones de precios, texto, intención, capacidad, tools y validaciones.

Entorno: Python 3.14.7; LangGraph 1.2.11; langchain-openai 1.6.0; LangSmith 0.12.2; Pydantic 2.13.5; pytest 9.1.1. Las versiones completas están en `requirements-lock.txt`.

No se ejecutaron llamadas reales a OpenAI ni a LangSmith, no se creó un experimento remoto y no se obtuvieron capturas de esa plataforma. El modo offline emplea extracción simulada; estos resultados no acreditan calidad de comprensión del LLM ni notas semánticas. La guía de ejecución remota y capturas está en el README y `GUIA_CAPTURAS.md`.

El primer ensayo detectó un defecto en el evaluador de precios: incluía la puntuación final de la oración en el importe. Se corrigió el patrón y se añadieron comprobaciones del cuerpo completo de la respuesta y pruebas con importes adulterados antes de obtener los resultados finales anteriores.
