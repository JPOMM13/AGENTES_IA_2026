# Tarea de seguridad del agente de cotizaciones

El flujo de entrega usa DeepTeam para atacar al cotizador real y producir evidencia de vulnerabilidades y controles. Los tres roles —cotizador, generador de ataques y juez de seguridad— usan Ollama local. La SPEC se conserva sin cambios.

**Fase actual: descubrir vulnerabilidades antes de aplicar controles.** Por defecto se ejecuta `baseline/`, la copia original del cotizador, adaptada a Ollama. Los controles añadidos de la variante `hardened` quedan inactivos. Las reglas y protecciones que ya traía el original se conservan; no se debilita artificialmente el agente para producir fallos. Los límites del arnés siguen acotando el consumo del experimento.

## Cómo probarlo

Desde esta carpeta, activa el entorno e instala las dependencias si todavía no están instaladas:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Si no existe el entorno, créalo primero con `python3 -m venv .venv`. Inicia la aplicación Ollama o ejecuta `ollama serve` en otra terminal. Descarga el modelo si falta:

```bash
ollama pull llama3.2:latest
ollama list
```

Usa `.env.example` como referencia para `.env`, conservando tu configuración existente. Los valores relevantes son:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:latest
SECURITY_SIMULATOR_MODEL=llama3.2:latest
SECURITY_JUDGE_MODEL=llama3.2:latest
```

No hacen falta claves de proveedores. Los modelos deben estar descargados en Ollama local; no se admiten modelos cloud. Instalar paquetes o descargar modelos puede requerir Internet; las inferencias de la tarea son locales.

Primero comprueba el circuito con una sola familia de vulnerabilidad:

```bash
python redteamtest01.py --smoke
```

Después ejecuta las seis familias configuradas: fuga de datos, revelación de instrucciones, permisos, manipulación de reglas comerciales, sesgo y toxicidad.

```bash
python redteamtest01.py
```

DeepTeam genera ataques, los envía al grafo del cotizador mediante un callback, evalúa las respuestas y guarda su evaluación nativa. El runner agrega trazas de herramientas y verificaciones determinísticas y genera automáticamente el reporte. Las técnicas configuradas son PromptInjection y PermissionEscalation; el muestreo de una corrida pequeña puede no elegir ambas.

La duración depende del modelo y equipo. Para ampliar el muestreo puedes usar `--attacks-per-type 2`. La consigna no exige un mínimo de casos. El smoke valida el circuito; el informe debe indicar qué familias se probaron realmente.

## Qué entregar

La terminal imprime el directorio `artifacts/security/ID/`, que contiene:

- `deepteam-native/`: exportación de `risk_assessment.save()`.
- `results.json`, `corpus.json` y `manifest.json`: ataques, respuestas, notas, errores y configuración.
- `reporte_seguridad.md`: reporte de esa ejecución.

La copia más reciente está en `reports/REPORTE_SEGURIDAD_PARA_GOOGLE_DOCS.md`. Revísala y cópiala a Google Docs: vulnerabilidades consideradas, ataques ejecutados y controles propuestos para una fase posterior. Completa integrantes y añade capturas auténticas. Un error no equivale a un ataque bloqueado; revisa el estado del manifiesto y los casos. No se publica automáticamente ningún documento.

Para regenerar el reporte de una ejecución guardada:

```bash
python -m security.report --run ID
```

Consulta `docs/GUIA_ENTREGA.md` y `docs/VALIDACION_EJEMPLO.md`.

## Comprobaciones adicionales de seguridad

```bash
python -m pytest tests/security -q
python -m security.run_redteam --offline
```

Estas comprobaciones usan fixtures y no sustituyen la ejecución de DeepTeam con Ollama. Los casos benignos conservados sirven para comprobar falsos positivos de los controles de seguridad.

La repetición del corpus con `security.replay` es opcional para verificar correcciones; su juez usa otra rúbrica, por lo que sus notas no son una comparación idéntica con las notas nativas de DeepTeam.

## Organización

`redteamtest01.py` es la entrada equivalente al ejemplo de clase; `security/online.py` contiene `red_team`, el callback y la exportación nativa. `baseline/agent/` es el cotizador de esta fase; `agent/` conserva la variante reforzada, que no se ejecuta por defecto y `local_llm.py` conecta Ollama. Los controles y las pruebas están en `security/` y `tests/security/`.

La evaluación funcional y su juez se archivaron en `tmp/fuera_del_alcance/`; no forman parte del flujo activo. `baseline/` es el objetivo predeterminado verificable. La SPEC y las evidencias históricas se conservan.
