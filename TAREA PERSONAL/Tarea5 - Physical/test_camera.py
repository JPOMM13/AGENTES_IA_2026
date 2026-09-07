"""Prueba manual del catálogo y una captura, antes de usar MCP."""

from pathlib import Path

from camera_client import save_snapshot


def main() -> None:
    result = save_snapshot(Path("camera.jpg"), camera_id=0)
    camera = result["camera"]
    print("Cámara:", camera.get("locationName"))
    print("Imagen:", camera.get("currentImageURL"))
    print("Latitud:", camera.get("latitude"))
    print("Longitud:", camera.get("longitude"))
    print(f"Imagen guardada en {result['path']} ({result['bytes']} bytes)")


if __name__ == "__main__":
    main()
