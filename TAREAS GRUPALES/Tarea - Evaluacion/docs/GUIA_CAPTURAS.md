# Evidencias reales para la entrega

1. Configurar `.env` y ejecutar `python -m evaluation.run_evaluation`.
2. Abrir el enlace del experimento que imprime el SDK. Verificar que pertenece al dataset `utec-eventos-v1-…` y contiene 15 ejemplos.
3. Capturar el dataset mostrando entradas y referencias. Incluir la fecha del experimento y los modelos usados.
4. Capturar la tabla de resultados con las métricas determinísticas y semánticas. Si no caben todas las columnas, obtener varias capturas legibles.
5. Abrir `01_valid`: capturar traza del grafo, llamadas a catálogo/cobertura/disponibilidad/cotización y salida con total mock PEN 590.00.
6. Abrir `11_tool_failure`: capturar intentos de búsqueda y derivación; no debe haber cotización. El estado `attempts.search_catalog` debe ser 6 (inicial + cinco reintentos).
7. Abrir `13_modify`: capturar los dos turnos y el resultado final para 80 asistentes con total mock PEN 944.00.
8. Abrir `14_holiday`: capturar entrega del 11/09 y recojo del 15/09 para el evento mock del 14/09.
9. Capturar las cuatro notas del juez y sus explicaciones. Si una nota está ausente, resolver el error y ejecutar un nuevo experimento antes de concluir.
10. Copiar el contenido de `METRICAS_PARA_GOOGLE_DOCS.md` a Google Docs, completar integrantes y resultados, insertar las capturas y enlazar el experimento. Explicar diferencias entre evaluación local de reglas y evaluación real del LLM.

No se han generado capturas de LangSmith en esta entrega de código porque no se ejecutó un experimento autenticado. La tabla local no sustituye esas capturas.
