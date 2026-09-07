# Demo Physical AI: MCP + cámara pública Caltrans

Servidor MCP en Python que consulta, en modo de solo lectura, el catálogo oficial de cámaras CCTV de Caltrans y entrega una captura al modelo para análisis visual. No usa credenciales ni descubre cámaras privadas.

## Instalación

Requiere Python 3.10+ y `uv`:

```bash
uv sync --extra dev
uv run python test_camera.py
uv run pytest
```

La prueba manual crea `camera.jpg`. La disponibilidad y calidad dependen de Caltrans y de cada cámara.

## Claude Desktop

1. Copia `claude_desktop_config.example.json` dentro de la clave correspondiente de `~/Library/Application Support/Claude/claude_desktop_config.json`.
2. La configuración incluida ya contiene la ruta absoluta actual. Si se mueve el proyecto, actualízala; si hiciera falta, sustituye `uv` por la salida de `which uv`.
3. Reinicia Claude Desktop.

Herramientas expuestas:

- `list_public_cameras(limit=5)` devuelve IDs temporales y ubicación.
- `get_camera_info(camera_id)` devuelve metadatos públicos.
- `get_camera_snapshot(camera_id)` devuelve la imagen al cliente MCP.

Los IDs son índices de una consulta ordenada. Conviene listar y capturar en la misma conversación porque el catálogo externo puede cambiar.

## Guion de demo

1. “Muéstrame cinco cámaras públicas disponibles.”
2. “Obtén una imagen de la cámara 2.”
3. “Analiza únicamente lo visible: vehículos, congestión, visibilidad y elementos generales.”

## Arquitectura y límites

`Claude → herramienta MCP → ArcGIS REST de Caltrans → URL pública de imagen → Claude`

La captura es estática, no streaming. El análisis debe limitarse a la escena visible, sin identificar personas ni inferir datos personales. Fallas esperables: cámara fuera de servicio, imagen desactualizada, URL modificada, baja resolución o indisponibilidad de la API.

Fuente: [capa CCTV oficial de Caltrans](https://caltrans-gis.dot.ca.gov/arcgis/rest/services/chhighway/CCTV/MapServer/0).
