"""MCP server exposing official, public, read-only Caltrans cameras."""

import base64
from typing import Any

from mcp import types
from mcp.server import MCPServer

from camera_client import CameraError, camera_by_id, download_snapshot, fetch_cameras

mcp = MCPServer("caltrans-public-cameras")


def _public_info(camera: dict[str, Any]) -> dict[str, Any]:
    return {
        "location": camera.get("locationName"),
        "latitude": camera.get("latitude"),
        "longitude": camera.get("longitude"),
        "in_service": camera.get("inService"),
        "image_url": camera.get("currentImageURL"),
        "stream_url": camera.get("streamingVideoURL"),
        "update_frequency": camera.get("currentImageUpdateFrequency"),
    }


@mcp.tool()
def list_public_cameras(limit: int = 5) -> list[dict[str, Any]]:
    """Lista cámaras de tráfico publicadas oficialmente por Caltrans. limit: 1 a 50."""
    if not 1 <= limit <= 50:
        raise ValueError("limit debe estar entre 1 y 50")
    return [
        {
            "id": index,
            "location": camera.get("locationName"),
            "latitude": camera.get("latitude"),
            "longitude": camera.get("longitude"),
            "in_service": camera.get("inService"),
        }
        for index, camera in enumerate(fetch_cameras(50)[:limit])
    ]


@mcp.tool()
def get_camera_info(camera_id: int) -> dict[str, Any]:
    """Devuelve metadatos públicos de la cámara seleccionada por su ID de lista."""
    return _public_info(camera_by_id(camera_id))


@mcp.tool(structured_output=False)
def get_camera_snapshot(camera_id: int) -> types.CallToolResult:
    """Obtiene la imagen actual de una cámara pública para analizar solo lo visible."""
    camera = camera_by_id(camera_id)
    data, content_type = download_snapshot(camera)
    return types.CallToolResult(
        content=[
            types.ImageContent(
                data=base64.b64encode(data).decode("ascii"),
                mimeType=content_type,
            )
        ]
    )


if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    except CameraError:
        raise
