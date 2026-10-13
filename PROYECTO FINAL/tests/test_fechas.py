"""Pruebas del resolutor determinista de fechas (app/utilidades/fechas.py).

Por que con `hoy` fijo: la logica es pura y recibe la fecha de referencia como
parametro, asi cada caso es reproducible en cualquier dia que se ejecute la suite.
Fecha de referencia: lunes 12 de octubre de 2026.
"""
from datetime import date

import pytest

from app.utilidades.fechas import (
    ResultadoFecha,
    describir_fecha,
    interpretar_numero,
    obtener_hoy,
    palabras_a_numero,
    resolver_fecha_relativa,
)

HOY = date(2026, 10, 12)  # lunes


# Fechas absolutas: ISO, dd/mm, dd-mm-aaaa, "15 de noviembre", "noviembre 15".
@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("el 17/10", "2026-10-17"),
        ("el 17-10-2026", "2026-10-17"),
        ("2026-11-15", "2026-11-15"),
        ("2026/11/15", "2026-11-15"),
        ("el 15 de noviembre", "2026-11-15"),
        ("15 noviembre", "2026-11-15"),
        ("15 de noviembre del 2026", "2026-11-15"),
        ("noviembre 15", "2026-11-15"),
        ("para el 4 de diciembre", "2026-12-04"),
        ("el 25 de octubre en Miraflores", "2026-10-25"),
        ("el 1/1/27", "2027-01-01"),
        ("EL 25 DE OCTUBRE", "2026-10-25"),
    ],
)
def test_fechas_absolutas(texto, esperado):
    resultado = resolver_fecha_relativa(texto, HOY)
    assert resultado.fecha_iso == esperado
    assert resultado.error is None


# Relativas con aritmetica exacta: manana, pasado manana, en N dias/semanas, hoy.
@pytest.mark.parametrize(
    "texto, esperado, confirmar",
    [
        ("es para mañana", "2026-10-13", False),
        ("pasado mañana", "2026-10-14", False),
        ("es para hoy", "2026-10-12", False),
        ("en 3 dias", "2026-10-15", False),
        ("en 15 días", "2026-10-27", False),
        ("en quince dias", "2026-10-27", False),
        ("dentro de 10 dias", "2026-10-22", False),
        ("en dos semanas", "2026-10-26", True),
        ("en 1 semana", "2026-10-19", True),
        ("en un mes", "2026-11-12", True),
    ],
)
def test_fechas_relativas_exactas(texto, esperado, confirmar):
    resultado = resolver_fecha_relativa(texto, HOY)
    assert resultado.fecha_iso == esperado
    assert resultado.necesita_confirmacion is confirmar


# Dias de la semana: "este/el/proximo sabado", "viernes que viene", fin de semana.
@pytest.mark.parametrize(
    "texto, esperado, confirmar",
    [
        ("el próximo sábado", "2026-10-17", True),
        ("este sábado", "2026-10-17", False),
        ("el sabado", "2026-10-17", False),
        ("el viernes que viene", "2026-10-16", True),
        ("el proximo viernes", "2026-10-16", True),
        ("el domingo 18", "2026-10-18", False),
        ("este lunes", "2026-10-12", False),  # "este" incluye hoy
        ("el lunes", "2026-10-19", False),  # "el" nunca es hoy
        ("este fin de semana", "2026-10-17", True),
        ("el proximo fin de semana", "2026-10-17", True),
        ("cumpleaños para 30 personas el próximo sábado en Surco", "2026-10-17", True),
    ],
)
def test_dias_de_la_semana(texto, esperado, confirmar):
    resultado = resolver_fecha_relativa(texto, HOY)
    assert resultado.fecha_iso == esperado
    assert resultado.necesita_confirmacion is confirmar


# "El proximo fin de semana" dicho un sabado se refiere al siguiente, no a hoy.
def test_proximo_fin_de_semana_dicho_un_sabado():
    sabado = date(2026, 10, 17)
    resultado = resolver_fecha_relativa("el proximo fin de semana", sabado)
    assert resultado.fecha_iso == "2026-10-24"


# Rangos ambiguos: no se inventa el dia; se devuelve el rango y una nota para preguntar.
def test_proxima_semana_devuelve_rango_y_pide_dia_exacto():
    resultado = resolver_fecha_relativa("es para un cumpleaños la próxima semana", HOY)
    assert resultado.fecha_iso is None
    assert resultado.necesita_confirmacion is True
    assert resultado.rango_sugerido == ("2026-10-19", "2026-10-25")
    assert "dia exacto" in resultado.nota.lower()
    assert "24/10/2026" in resultado.nota  # sabado sugerido


def test_semana_que_viene_tambien_es_rango():
    resultado = resolver_fecha_relativa("la semana que viene", HOY)
    assert resultado.rango_sugerido == ("2026-10-19", "2026-10-25")


def test_fin_de_mes_devuelve_rango():
    resultado = resolver_fecha_relativa("a fin de mes", HOY)
    assert resultado.fecha_iso is None
    assert resultado.rango_sugerido == ("2026-10-25", "2026-10-31")


def test_fin_de_mes_en_ultima_semana_pasa_al_mes_siguiente():
    resultado = resolver_fecha_relativa("fin de mes", date(2026, 10, 28))
    assert resultado.rango_sugerido == ("2026-11-24", "2026-11-30")


# Parciales: dia suelto, mes suelto, anio suelto (con anio inferido para el mes).
def test_dia_suelto_es_parcial():
    resultado = resolver_fecha_relativa("el 3", HOY)
    assert resultado.fecha_iso is None
    assert resultado.fecha_parcial == {"dia": 3, "mes": None, "anio": None}


def test_mes_suelto_este_anio():
    resultado = resolver_fecha_relativa("diciembre", HOY)
    assert resultado.fecha_parcial == {"dia": None, "mes": 12, "anio": 2026}


def test_mes_suelto_ya_pasado_es_del_anio_siguiente():
    resultado = resolver_fecha_relativa("en febrero", HOY)
    assert resultado.fecha_parcial == {"dia": None, "mes": 2, "anio": 2027}


def test_anio_suelto():
    resultado = resolver_fecha_relativa("2027", HOY)
    assert resultado.fecha_parcial == {"dia": None, "mes": None, "anio": 2027}


def test_dia_suelto_no_confunde_asistentes():
    resultado = resolver_fecha_relativa("somos 30 personas", HOY)
    assert resultado.fecha_iso is None
    assert resultado.fecha_parcial is None


# Fechas invalidas o pasadas: error explicable, nunca una fecha inventada.
def test_fecha_imposible_da_error():
    resultado = resolver_fecha_relativa("el 31 de febrero", HOY)
    assert resultado.fecha_iso is None
    assert "no es valida" in resultado.error
    assert "31/02/2026" in resultado.error


def test_fecha_pasada_con_anio_explicito_da_error():
    resultado = resolver_fecha_relativa("5/10/2025", HOY)
    assert resultado.fecha_iso is None
    assert "ya paso" in resultado.error


def test_fecha_pasada_sin_anio_se_mueve_al_siguiente_con_confirmacion():
    resultado = resolver_fecha_relativa("el 5 de octubre", HOY)
    assert resultado.fecha_iso == "2027-10-05"
    assert resultado.necesita_confirmacion is True
    assert "2027" in resultado.nota


# Casos de ruido: telefonos, horas y "por la manana" no son fechas.
def test_telefono_no_es_fecha():
    resultado = resolver_fecha_relativa("mi telefono es 999-111-222", HOY)
    assert resultado.fecha_iso is None
    assert resultado.error is None


def test_por_la_manana_no_es_manana():
    resultado = resolver_fecha_relativa("por la mañana del 20 de octubre", HOY)
    assert resultado.fecha_iso == "2026-10-20"


def test_hoy_como_adverbio_no_es_fecha():
    resultado = resolver_fecha_relativa("hoy quiero cotizar para el 25 de octubre", HOY)
    assert resultado.fecha_iso == "2026-10-25"


def test_diciembre_cincuenta_personas_no_es_dia():
    resultado = resolver_fecha_relativa("en diciembre 50 personas", HOY)
    assert resultado.fecha_iso is None
    assert resultado.fecha_parcial["mes"] == 12


def test_sin_senal_de_fecha_devuelve_vacio():
    resultado = resolver_fecha_relativa("quiero cerveza y hielo", HOY)
    assert resultado == ResultadoFecha()
    assert resultado.encontro_algo is False


# Numeros en palabras (reutilizados para asistentes y "en dos semanas").
@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("cincuenta", 50),
        ("ciento veinte", 120),
        ("treinta y cinco", 35),
        ("doscientas", 200),
        ("quince", 15),
        ("hola", None),
    ],
)
def test_palabras_a_numero(texto, esperado):
    assert palabras_a_numero(texto) == esperado


def test_interpretar_numero_acepta_digitos_y_palabras():
    assert interpretar_numero("50") == 50
    assert interpretar_numero("cincuenta") == 50


# Reloj unico: COTIZADOR_FECHA_HOY permite fijar "hoy" para evals reproducibles.
def test_obtener_hoy_respeta_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("COTIZADOR_FECHA_HOY", "2026-10-12")
    assert obtener_hoy() == HOY
    monkeypatch.setenv("COTIZADOR_FECHA_HOY", "no-es-fecha")
    assert obtener_hoy() == date.today()


def test_describir_fecha_en_espanol():
    assert describir_fecha("2026-10-17") == "sábado 17 de octubre de 2026"
    assert describir_fecha(None) == "fecha pendiente"


# "el sabado 24": el numero de dia manda; si el dia de la semana no calza, se registra el numero y se pide confirmar.
def test_dia_semana_con_numero_resuelve_por_el_numero():
    from datetime import date

    from app.utilidades.fechas import resolver_fecha_relativa

    hoy = date(2026, 10, 13)  # martes
    r = resolver_fecha_relativa("cumpleanos el sabado 24 en miraflores", hoy)
    assert r.fecha_iso == "2026-10-24" and not r.necesita_confirmacion
    r = resolver_fecha_relativa("reunion el viernes 24", hoy)  # el 24 de octubre de 2026 es sabado
    assert r.fecha_iso == "2026-10-24" and r.necesita_confirmacion and "cae" in (r.nota or "")
    r = resolver_fecha_relativa("el domingo 5", hoy)  # ya paso el 5 de octubre -> 5 de noviembre
    assert r.fecha_iso == "2026-11-05"
