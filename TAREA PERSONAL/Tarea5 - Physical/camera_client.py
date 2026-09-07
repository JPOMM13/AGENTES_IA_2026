"""Read-only client for the official Caltrans CCTV ArcGIS layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

API_URL = (
    "https://caltrans-gis.dot.ca.gov/arcgis/rest/services/"
    "chhighway/CCTV/MapServer/0/query"
)
FIELDS = (
    "OBJECTID,locationName,currentImageURL,streamingVideoURL,latitude,"
    "longitude,inService,currentImageUpdateFrequency"
)
USER_AGENT = "caltrans-public-camera-mcp/1.0 (educational read-only demo)"


class CameraError(RuntimeError):
    """A clear, user-facing error from the public camera service."""


def _is_in_service(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1", "active"}


def fetch_cameras(limit: int = 50, *, client: httpx.Client | None = None) -> list[dict[str, Any]]:
    """Return a deterministic list of public cameras that expose a snapshot URL."""
    if not 1 <= limit <= 200:
        raise ValueError("limit debe estar entre 1 y 200")
    params = {
        "where": "currentImageURL IS NOT NULL",
        "outFields": FIELDS,
        "returnGeometry": "false",
        "orderByFields": "OBJECTID ASC",
        "resultRecordCount": limit,
        "f": "json",
    }
    owns_client = client is None
    http = client or httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    try:
        response = http.get(API_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise CameraError(f"No se pudo consultar el catálogo público de Caltrans: {exc}") from exc
    finally:
        if owns_client:
            http.close()
    if payload.get("error"):
        raise CameraError(f"Caltrans devolvió un error: {payload['error'].get('message', 'desconocido')}")
    cameras = [f.get("attributes", {}) for f in payload.get("features", [])]
    cameras = [c for c in cameras if c.get("currentImageURL")]
    cameras.sort(key=lambda c: (not _is_in_service(c.get("inService")), c.get("OBJECTID", 0)))
    if not cameras:
        raise CameraError("No se encontraron cámaras públicas con imagen disponible.")
    return cameras


def camera_by_id(camera_id: int, *, client: httpx.Client | None = None) -> dict[str, Any]:
    """Resolve the zero-based ID shown by list_public_cameras."""
    if camera_id < 0:
        raise CameraError("camera_id no puede ser negativo")
    cameras = fetch_cameras(max(50, camera_id + 1), client=client)
    if camera_id >= len(cameras):
        raise CameraError(f"camera_id {camera_id} no existe; hay {len(cameras)} cámaras disponibles en la consulta")
    return cameras[camera_id]


def download_snapshot(camera: dict[str, Any], *, client: httpx.Client | None = None) -> tuple[bytes, str]:
    """Download a public snapshot and validate that the response is an image."""
    url = camera.get("currentImageURL")
    if not url or not str(url).lower().startswith(("https://", "http://")):
        raise CameraError("La cámara no tiene una URL pública de imagen válida")
    owns_client = client is None
    http = client or httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    try:
        response = http.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if not content_type.startswith("image/"):
            raise CameraError(f"La URL no devolvió una imagen (Content-Type: {content_type or 'ausente'})")
        return response.content, content_type
    except httpx.HTTPError as exc:
        raise CameraError(f"No se pudo descargar la captura pública: {exc}") from exc
    finally:
        if owns_client:
            http.close()


def save_snapshot(path: Path, camera_id: int = 0) -> dict[str, Any]:
    camera = camera_by_id(camera_id)
    data, content_type = download_snapshot(camera)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"camera": camera, "path": str(path), "content_type": content_type, "bytes": len(data)}

