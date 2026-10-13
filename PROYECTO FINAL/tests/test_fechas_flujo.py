"""Fechas relativas, parciales y pasadas de principio a fin (grafo completo, modo mock, sin LLM).

Con COTIZADOR_FECHA_HOY fijado al 13-10-2026 (martes) los resultados son reproducibles en cualquier maquina.
"""
from __future__ import annotations

import pytest

from app.estado import EstadoCotizacion
from app.flujo import manejar_mensaje


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setenv("COTIZADOR_FECHA_HOY", "2026-10-13")
    monkeypatch.setenv("LLM_ENABLED", "false")


def _turno(mensaje: str, estado: EstadoCotizacion | None = None):
    return manejar_mensaje(mensaje, estado or EstadoCotizacion())


def test_proximo_sabado_se_resuelve_y_se_confirma_una_sola_vez():
    respuesta, estado = _turno("Cumpleaños de 30 personas el proximo sabado en Miraflores")
    assert estado.fecha_evento == "2026-10-17"
    assert "sábado 17/10/2026" in respuesta  # nota de confirmacion
    assert estado.fecha_requiere_confirmacion is False and estado.fecha_nota is None  # ya se mostro
    respuesta, estado = _turno("cerveza", estado)
    assert "17/10/2026" not in respuesta  # no se repite la nota


def test_manana_y_pasado_manana_caen_en_la_regla_de_72_horas():
    for frase, esperada in [("mañana", "2026-10-14"), ("pasado mañana", "2026-10-15")]:
        respuesta, estado = _turno(f"Soy Ana Torres, 999111222. Reunion de 20 personas {frase} en Miraflores")
        assert estado.fecha_evento == esperada
        _, estado = _turno("cerveza", estado)
        assert not estado.cotizacion


def test_dia_y_mes_sin_anio_que_ya_paso_va_al_siguiente_anio_con_aviso():
    respuesta, estado = _turno("Matrimonio de 80 personas el 15 de enero en San Isidro")
    assert estado.fecha_evento == "2027-01-15"
    assert "2027" in respuesta and "Confirmame" in respuesta


def test_dia_de_semana_con_numero_usa_el_numero():
    _, estado = _turno("Reunion de 20 personas el sabado 24 en Barranco")
    assert estado.fecha_evento == "2026-10-24"
    respuesta, estado = _turno("Reunion de 20 personas el viernes 24 en Barranco")
    assert estado.fecha_evento == "2026-10-24" and "cae" in respuesta  # el 24 es sabado: se avisa


def test_en_dos_semanas_asume_mismo_dia_y_lo_dice():
    respuesta, estado = _turno("Corporativo de 50 personas en dos semanas en Surco")
    assert estado.fecha_evento == "2026-10-27" and "Asumi" in respuesta


def test_rango_ambiguo_no_adivina_y_pide_el_dia():
    respuesta, estado = _turno("Cumpleaños de 30 personas la proxima semana en Miraflores")
    assert estado.fecha_evento is None
    assert "fecha" in respuesta.lower()


def test_fecha_parcial_en_dos_turnos_usa_el_anio_actual():
    _, estado = _turno("Cumpleaños de 30 personas en Miraflores el 20")
    assert estado.fecha_evento is None and estado.fecha_parcial.get("dia") == 20
    _, estado = _turno("de noviembre", estado)
    assert estado.fecha_evento == "2026-11-20"


def test_fecha_imposible_sigue_rechazada():
    respuesta, estado = _turno("Cumpleaños de 30 personas el 30 de febrero en Miraflores")
    assert estado.fecha_evento is None and "no es valida" in respuesta


def test_fecha_absoluta_con_anio_no_cambia():
    _, estado = _turno("Matrimonio de 100 personas el 24 de febrero de 2027 en Miraflores")
    assert estado.fecha_evento == "2027-02-24" and not estado.fecha_requiere_confirmacion
