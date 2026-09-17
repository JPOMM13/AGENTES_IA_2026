# Fase inicial: descubrir y visualizar vulnerabilidades

Todas las ejecuciones siguientes usan el agente original (`baseline`) por defecto. No se aplican los controles añadidos ni se ejecuta replay reforzado en esta fase. Se registran hallazgos reales, incluso si no hay violaciones detectadas.

1. Ejecuta `python redteamtest01.py --smoke` con Ollama iniciado para verificar la conexión y el circuito completo.
2. Ejecuta `python redteamtest01.py` para probar las seis familias configuradas con DeepTeam. Conserva el ID mostrado y revisa errores y ataques efectivamente generados.
3. Abre `reports/REPORTE_SEGURIDAD_PARA_GOOGLE_DOCS.md`. La matriz enumera vulnerabilidades consideradas y distingue las probadas de las pendientes.
4. Revisa manualmente ataques, respuestas y notas del juez. Para cada hallazgo, explica el control, cómo se podría implementar en la siguiente fase. No presentes un control propuesto como aplicado ni un error como aprobado.
5. Copia el reporte a Google Docs y completa integrantes. Añade capturas reales de la ejecución, ataques representativos y código de los controles; usa datos sintéticos.
6. Adjunta o enlaza la exportación nativa `artifacts/security/ID/deepteam-native/` y las evidencias de esa misma ejecución según el mecanismo de entrega del curso.

La consigna pide posibles vulnerabilidades, probar ataques y documentar controles, con un reporte tras usar DeepTeam. No exige evaluación funcional, LangSmith, un mínimo de 20 casos ni cero vulnerabilidades encontradas. Repetir los ataques después de corregir un control es útil y opcional; el smoke por sí solo no prueba las seis familias.

El reporte se genera después de ejecutar el código: DeepTeam es una evaluación adversarial de seguridad. El agente responde realmente y un juez local evalúa los ataques; las verificaciones determinísticas complementan ese juicio. Las pruebas offline solo verifican el arnés y los controles y no sustituyen este entregable.
