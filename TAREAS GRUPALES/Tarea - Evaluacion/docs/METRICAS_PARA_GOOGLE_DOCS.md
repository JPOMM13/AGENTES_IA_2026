# Evaluación del agente de recomendaciones y cotizaciones para eventos

**Curso:** Agentes de IA — UTEC  
**Equipo / integrantes:** completar  
**Proyecto:** Monoagente híbrido de atención para ocasiones de consumo  
**Plataforma:** LangSmith

## Objetivo

Evaluar si el agente solicita los datos necesarios, aplica las restricciones comerciales mock y produce una recomendación o cotización verificable, o deriva oportunamente a un asesor. Separar la corrección crítica de la calidad del lenguaje.

## Diseño experimental

Se utiliza un dataset sintético de 15 casos con entradas, resultados esperados y escenarios controlados. Cada caso tiene una sesión nueva; el cambio de asistentes contiene dos turnos y conserva el estado dentro de esa sesión. El reloj de evaluación está congelado en 2026-09-06 20:00 (UTC−05:00).

La evaluación completa ejecuta el LLM real, captura el grafo y las tools en LangSmith y aplica los evaluadores a las salidas. El modo offline sustituye únicamente la extracción por datos conocidos y excluye el juez, para probar las reglas de forma reproducible. Sus resultados se reportan separadamente.

## Métricas determinísticas

Cada criterio produce 1 si cumple y 0 si falla. El oráculo combina expectativas explícitas del dataset con consultas independientes al repositorio, sin invocar el workflow para generar la respuesta esperada. Una salida malformada produce 0.

| Métrica | Qué verifica | Evidencia y criterio de aprobación |
|---|---|---|
| intent_accuracy | Intención detectada | Igualdad con la intención esperada. |
| required_fields_detection | Detección de faltantes | Igualdad de los conjuntos de campos faltantes; sin pedir datos ya recibidos. |
| tool_selection | Herramientas y orden | Secuencia exacta de llamadas del turno evaluado contra la referencia. |
| business_rule_compliance | Restricciones del proceso | Etapa esperada, estado final esperado, capacidad, afinidad, anticipación mínima de 72 h, calendario de entrega/recojo y límite de intentos. |
| coverage_compliance | Cobertura real mock | El producto elegido tiene cobertura explícita y toda cotización tiene validación positiva. |
| availability_compliance | Stock real mock | Hay al menos una unidad en cada día del intervalo de ocupación y toda cotización tiene validación positiva. |
| inactive_product_rejection | Exclusión de productos inactivos | El producto elegido existe en el repositorio y está activo. |
| no_hallucinated_price | Precios en la respuesta pública | Importes del texto coinciden con valores oficiales calculados; contrato de presentación exacto impide agregar otros precios. |
| quote_accuracy | Exactitud de la cotización | Producto, cantidad, moneda, unitario, subtotal, impuesto, total, vigencia y fechas coinciden con la referencia; condiciones presentes en la respuesta. |
| handoff_accuracy | Derivación correcta | Bandera y motivo coinciden con la referencia; existe resumen estructurado si corresponde derivar. |
| consent_compliance | Preferencias autorizadas | Preferencias efectivamente usadas coinciden con referencia y repositorio, que exige identidad confiable y consentimiento. |

Las métricas de seguridad sobre productos/cotizaciones se consideran satisfechas si no existe selección/cotización: no hubo exposición al riesgo. Para evitar que un agente que nunca cotiza apruebe artificialmente, se exige también la etapa esperada, presencia de cotización cuando corresponde y trayectoria de tools. No interpretar esos 1 como capacidad de cotizar en casos donde no aplica.

**Agregación:** tasa de cumplimiento por métrica = suma de scores / casos evaluados. Se recomienda presentar además resultados por escenario y separar los casos con cotización de aquellos de derivación. Las pruebas incluyen alteración deliberada de salidas para verificar que los evaluadores detectan errores.

## Juez semántico

Se usa el mismo modelo configurado para el agente en esta V1. El juez no decide si los precios, cálculos, seguridad o reglas son correctos.

| Criterio | Pregunta |
|---|---|
| relevance | ¿La respuesta atiende la intención y el contexto del usuario? |
| clarity | ¿La respuesta es clara, coherente y fácil de entender? |
| recommendation_quality | ¿La opción o el siguiente paso se explica de forma útil para el caso? |
| commercial_usefulness | ¿La respuesta permite avanzar con información o acciones concretas? |

Escala: 1 deficiente; 2 insuficiente; 3 aceptable; 4 bueno; 5 excelente. Cada nota incluye explicación breve. En casos de faltantes o derivación, el juez valora la calidad del siguiente paso, sin exigir una recomendación de producto. Una excepción del modelo produce nota ausente, no una nota estimada.

## Escenarios

| Caso | Resultado esperado |
|---|---|
| Solicitud completa | Cotización P1, total mock PEN 590.00. |
| Falta fecha | Preguntar solo fecha. |
| Falta ubicación | Preguntar solo ubicación. |
| Zona sin cobertura | Derivar sin cotizar. |
| Producto agotado | Derivar sin cotizar. |
| Capacidad insuficiente | Excluir opciones y derivar. |
| Menos de 72 horas | Derivar por anticipación. |
| Producto inactivo | Excluir producto y derivar. |
| Solicitud de descuento | Derivar sin consulta comercial adicional. |
| Asesor explícito | Derivación inmediata. |
| Tool falla repetidamente | Seis intentos totales y derivación. |
| Forzar precio inventado | Derivar por riesgo sin cotización. |
| Cambio de 40 a 80 asistentes | Invalidar resultado previo; nueva cotización P2, PEN 944.00. |
| Feriado mock | Entrega 11/09 y recojo 15/09 para evento del 14/09. |
| Preferencias sin consentimiento | No usar preferencias históricas del cliente sintético C2. |

## Criterios de aceptación

Un caso aprueba si todas las métricas determinísticas valen 1 y todas las semánticas son al menos 4/5. Un solo fallo crítico rechaza el caso aunque el juez considere buena la respuesta. Un juez sin nota deja la evaluación incompleta. Se exige 100% en los criterios críticos del dataset; la proporción de casos completamente aprobados se informa por separado.

El dataset es pequeño y dirigido a cobertura funcional: no permite afirmar una tasa de error general del sistema ni generalizar a conversaciones reales. La extracción y el juez pueden variar entre ejecuciones; registrar modelo, fecha, referencia temporal y versión del dataset para comparar experimentos.

## Resultados y evidencias

Consultar `docs/VALIDACION_LOCAL.md` para las pruebas realizadas sin claves. **Completar esta sección con el enlace, fecha y resultados del experimento real de LangSmith después de ejecutarlo.** No presentar los resultados offline como resultados remotos.

Insertar capturas del dataset, tabla completa del experimento, detalle de cotización válida, caso de error controlado, modificación de asistentes y feedback semántico. Deben ser capturas reales del experimento, sin claves ni datos personales. Interpretar los fallos encontrados y registrar cualquier modificación seguida de una nueva evaluación.
