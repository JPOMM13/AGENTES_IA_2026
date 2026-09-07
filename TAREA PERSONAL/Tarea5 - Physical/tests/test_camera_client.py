import httpx
import pytest

from camera_client import CameraError, camera_by_id, download_snapshot, fetch_cameras


def test_fetch_filters_and_prioritizes_in_service():
    def handler(request):
        return httpx.Response(200, json={"features": [
            {"attributes": {"OBJECTID": 1, "locationName": "A", "currentImageURL": "https://x/a.jpg", "inService": "false"}},
            {"attributes": {"OBJECTID": 2, "locationName": "B", "currentImageURL": "https://x/b.jpg", "inService": "true"}},
            {"attributes": {"OBJECTID": 3, "locationName": "C", "currentImageURL": None, "inService": "true"}},
        ]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        cameras = fetch_cameras(client=client)
    assert [c["locationName"] for c in cameras] == ["B", "A"]


def test_camera_id_out_of_range():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"features": [
        {"attributes": {"OBJECTID": 1, "currentImageURL": "https://x/a.jpg"}}
    ]})))
    with client, pytest.raises(CameraError, match="no existe"):
        camera_by_id(5, client=client)


def test_snapshot_rejects_non_image():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="html", headers={"content-type": "text/html"})))
    with client, pytest.raises(CameraError, match="no devolvió una imagen"):
        download_snapshot({"currentImageURL": "https://x/cam"}, client=client)

