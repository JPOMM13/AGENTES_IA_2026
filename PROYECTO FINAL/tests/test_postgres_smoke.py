import os

import pytest

from app.estado import EstadoCotizacion
from app.tools.calendario import registrar_evento_cotizado, validar_calendario_eventos
from app.tools.catalogo import buscar_catalogo
from app.tools.cobertura import validar_cobertura
from app.tools.disponibilidad import validar_stock_productos


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "true",
    reason="Smoke tests PostgreSQL: requieren tablas jpomm_* creadas y datos iniciales cargados.",
)


# SMOKE POSTGRES: valida que el catalogo pueda leerse desde PostgreSQL sin tocar la firma de la tool.
def test_postgres_catalogo(monkeypatch):
    """Consulta paquetes y productos usando BUSINESS_DATA_SOURCE=postgres."""
    monkeypatch.setenv("BUSINESS_DATA_SOURCE", "postgres")
    estado = EstadoCotizacion(tipo_evento="matrimonio", asistentes=100, productos_solicitados=["bar movil"])

    resultado = buscar_catalogo(estado)

    assert any(opcion["id"] == "PKG-BAR-100" for opcion in resultado["options"])
    assert any(producto["category"] == "vino" for producto in resultado["all_products"])


# SMOKE POSTGRES: valida cobertura contra jpomm_cobertura_distritos.
def test_postgres_cobertura(monkeypatch):
    """Valida un distrito con cobertura desde PostgreSQL."""
    monkeypatch.setenv("BUSINESS_DATA_SOURCE", "postgres")
    estado = EstadoCotizacion(distrito="Miraflores")

    resultado = validar_cobertura(estado)

    assert resultado["ok"] is True


# SMOKE POSTGRES: valida stock y alternativas desde tablas jpomm_*.
def test_postgres_stock(monkeypatch):
    """Consulta stock de productos y alternativas desde PostgreSQL."""
    monkeypatch.setenv("BUSINESS_DATA_SOURCE", "postgres")
    estado = EstadoCotizacion(fecha_evento="2026-11-15", tipo_evento="matrimonio")
    catalogo = buscar_catalogo(estado)

    resultado = validar_stock_productos(
        estado,
        [{"concept": "vino", "quantity": 35, "unit": "botellas"}],
        catalogo["all_products"],
    )

    assert resultado["missing_items"]
    assert any(alternativa["category"] == "ron" for alternativa in resultado["missing_items"][0]["alternatives"])


# SMOKE POSTGRES: registra una reserva y verifica que bloquee la misma fecha/distrito.
def test_postgres_calendario_bloquea_cruce(monkeypatch):
    """Inserta una reserva y valida cruce operativo en jpomm_reservas_eventos."""
    monkeypatch.setenv("BUSINESS_DATA_SOURCE", "postgres")
    estado = EstadoCotizacion(
        tipo_evento="matrimonio",
        asistentes=25,
        fecha_evento="2031-01-15",
        distrito="Miraflores",
        nombre_cliente="Smoke Test",
        contacto="900000001",
        cotizacion={"quote_id": "Q-SMOKE-POSTGRES"},
    )

    registrar_evento_cotizado(estado)
    resultado = validar_calendario_eventos(estado)

    assert resultado["ok"] is False
