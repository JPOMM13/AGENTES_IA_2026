# Adaptación al ejemplo de la sesión 23

Referencia revisada: `agents26_m8s23.zip`, en `M8 - Evaluacion y Etica/S23- Planifiacion distribuida/`, proporcionado por el usuario. Sus archivos se trataron como material de referencia, no como instrucciones para ejecutar acciones.

El archivo `redteamtest01.py` del ZIP define un callback a `agent_invoke`, configura Bias y PromptInjection, llama `red_team(...)`, consulta `overview` y `test_cases`, y guarda `risk_assessment.save(to=...)`.

| Ejemplo | Implementación de esta tarea |
|---|---|
| Entrada `redteamtest01.py` | Entrada del mismo nombre delega en `security.run_redteam` |
| Callback a `demoagent.agent_invoke` | Callback en `security/online.py` invoca el grafo del cotizador mediante un worker aislado |
| Bias y PromptInjection | Seis familias pertinentes al cotizador y técnicas PromptInjection/PermissionEscalation |
| `red_team(...)` | Llamada real al SDK DeepTeam instalado |
| `risk_assessment.save(...)` | Exportación nativa en `artifacts/security/ID/deepteam-native/` |
| Agente de ejemplo con OpenAI y búsqueda | Cotizador existente; modelo objetivo, simulador y juez explícitos en Ollama local |

No se ejecuta el agente de demostración del ZIP, porque no es el cotizador y usa servicios externos. Se valida su patrón de integración en el proyecto actual. No se atribuye cobertura completa de OWASP a estas seis familias.

Validación automatizada: `python -m pytest tests/security -q`. Incluye controles, aislamiento, adaptación local y pruebas de integración del SDK con dobles de prueba; eso no equivale a inferencia real. Validación real: `python redteamtest01.py --smoke`, que debe generar exportación nativa, trazas y reporte con los tres modelos locales. El manifiesto de cada corrida contiene versiones, modelos y estado; el informe diferencia fallos, errores y casos no probados.

## Resultado histórico de validación del circuito

Esta corrida se hizo sobre la variante reforzada y no es el diagnóstico inicial solicitado posteriormente. El flujo actual usa baseline por defecto, sin controles añadidos.

Corrida `20260910T004131Z-hardened-0d8f08`: estado `completed`, DeepTeam ejecutado, 4 ataques evaluables de PII Leakage, 4 aprobados, 0 fallos y 0 errores. Los tres roles usaron `llama3.2:latest` en Ollama local. Se conserva la exportación nativa en el directorio de esa corrida. Es un smoke de una familia; no prueba las otras cinco ni demuestra ausencia de vulnerabilidades.

Las 32 pruebas automatizadas de seguridad pasaron. La huella SHA-256 de la SPEC se verificó sin cambios.

## Diagnóstico inicial del agente original

Corrida `20260910T004704Z-baseline-14b202`: DeepTeam completó 24 casos de las seis familias sobre baseline con Ollama local; 18 aprobados, 6 fallos automáticos y 0 errores. La revisión de los seis fallos no corroboró fugas: las razones del juez contradicen las respuestas o confunden información pública del flujo con instrucciones internas. Se registraron como probables falsos positivos, pendientes de validación por el equipo, en `manual_review.json`, conservando las notas nativas. No se aplicaron correcciones al agente. Este diagnóstico no confirma vulnerabilidades explotadas ni demuestra ausencia de ellas.
