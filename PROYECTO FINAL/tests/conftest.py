import app.almacen_sesion_redis as redis_session_store
import app.almacen_sesion as session_store
import pytest


# Ejecuta la responsabilidad de aislar memoria mock.
@pytest.fixture(autouse=True)
def aislar_memoria_mock(tmp_path, monkeypatch):
    monkeypatch.setattr(session_store, "STORE_PATH", tmp_path / "mock_session_memory.json")
    monkeypatch.setattr(redis_session_store, "REDIS_MOCK_PATH", tmp_path / "mock_redis_session.json")
