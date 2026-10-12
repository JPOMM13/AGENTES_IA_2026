import os
from uuid import uuid4

import pytest

from app.estado import EstadoCotizacion


# Smoke test PostgreSQL JSONB: se ejecuta solo si el usuario lo activa explicitamente.
@pytest.mark.skipif(os.getenv("RUN_POSTGRES_MEMORY_TESTS") != "true", reason="Smoke test PostgreSQL desactivado.")
def test_smoke_memoria_postgres_guarda_y_recupera(monkeypatch):
    monkeypatch.setenv("MEMORY_DATA_SOURCE", "postgres")

    from app.repositorios_postgres.memoria_postgres import (
        buscar_conversacion_previa_postgres,
        guardar_estado_conversacion_postgres,
    )

    contacto = f"999{uuid4().hex[:6]}"
    estado = EstadoCotizacion(
        tipo_evento="matrimonio",
        asistentes=30,
        fecha_evento="2027-05-20",
        distrito="Miraflores",
        nombre_cliente="Smoke Test",
        contacto=contacto,
        productos_solicitados=["vino"],
    )

    guardar_estado_conversacion_postgres(estado)
    recuperado = buscar_conversacion_previa_postgres(contacto)

    assert recuperado is not None
    assert recuperado.contacto == contacto
    assert recuperado.tipo_evento == "matrimonio"


# Smoke test Redis: se ejecuta solo si el usuario lo activa explicitamente.
@pytest.mark.skipif(os.getenv("RUN_REDIS_TESTS") != "true", reason="Smoke test Redis desactivado.")
def test_smoke_sesion_redis_guarda_recupera_y_reinicia(monkeypatch):
    monkeypatch.setenv("SESSION_STORE", "redis")

    from app.repositorios_redis.conexion import reiniciar_cliente_redis
    from app.repositorios_redis.sesion_redis import (
        cargar_sesion_activa_redis,
        guardar_sesion_activa_redis,
        reiniciar_sesion_activa_redis,
    )

    reiniciar_cliente_redis()
    estado = EstadoCotizacion(
        tipo_evento="cumpleanos",
        asistentes=25,
        fecha_evento="2027-06-12",
        distrito="Miraflores",
        contacto="999222333",
    )

    guardar_sesion_activa_redis(estado)
    recuperado = cargar_sesion_activa_redis(estado.id_sesion)
    assert recuperado is not None
    assert recuperado.id_sesion == estado.id_sesion

    reiniciar_sesion_activa_redis(estado.id_sesion)
    assert cargar_sesion_activa_redis(estado.id_sesion) is None
