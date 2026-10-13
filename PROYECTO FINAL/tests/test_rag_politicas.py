"""Preguntas de politica (RAG) al inicio o a mitad de la cotizacion.

Problema que cubren: una pregunta como "¿hacen entregas en feriados?" se convertia en distrito "Feriados",
el guardrail del router la transformaba en "recomendacion" y la tool de cobertura la rechazaba; ademas, si la
base de GCP no respondia (certificado con permisos 0644) el turno terminaba en error 500.
"""
from __future__ import annotations

import pytest

from app.estado import EstadoCotizacion
from app.tools import consulta_rag
from app.tools.extraccion import (
    _extraer_distrito,
    _proteger_intencion_clasificada,
    _resolver_intencion_respaldo,
    es_pregunta_de_servicio,
)


@pytest.fixture(autouse=True)
def _sin_llm(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


# EXTRACCION: una pregunta no declara distrito; una pregunta por cobertura si.
@pytest.mark.parametrize(
    "mensaje, esperado",
    [
        ("¿hacen entregas en feriados?", None),
        ("Tengo un evento de 50 personas en un piso 4 sin ascensor, ¿me atienden?", None),
        ("¿y hay recargo por piso si no hay ascensor?", None),
        ("¿atienden en Villa El Salvador?", "Villa El Salvador"),
        ("Quiero cotizar un cumpleaños en Miraflores", "Miraflores"),
        ("el evento es en Villa El Salvador", "Villa El Salvador"),
    ],
)
def test_pregunta_no_se_toma_como_distrito(mensaje, esperado):
    assert _extraer_distrito(mensaje) == esperado


# ROUTER: la pregunta clasificada como consulta_general se mantiene aunque traiga datos (los datos ya se fusionan).
def test_pregunta_de_politica_con_datos_sigue_siendo_consulta_general():
    fields = {"asistentes": 50}
    assert _proteger_intencion_clasificada("consulta_general", fields, "Tengo 50 personas en piso 4, ¿me atienden?") == "consulta_general"
    # Sin pregunta, el guardrail original sigue vigente: datos de cotizacion mandan.
    assert _proteger_intencion_clasificada("consulta_general", fields, "somos 50 personas") == "recomendacion"


# REGLAS DE RESPALDO (sin LLM): la pregunta de servicio va al RAG, no a "modificar_pedido" por el "sin " ni a cotizar.
@pytest.mark.parametrize(
    "mensaje, intencion",
    [
        ("¿hay recargo por piso si no hay ascensor?", "consulta_general"),
        ("¿qué incluye el servicio de cerveza de barril?", "consulta_general"),
        ("¿hacen entregas en feriados?", "consulta_general"),
        ("quiero cotizar cerveza de barril para 40 personas", "recomendacion"),
        ("¿cuánto cuesta el barril de 50 litros?", "consulta_precio"),
    ],
)
def test_reglas_de_respaldo_enrutan_preguntas_de_servicio(mensaje, intencion):
    estado = EstadoCotizacion()
    assert es_pregunta_de_servicio(mensaje) == (intencion == "consulta_general")
    assert _resolver_intencion_respaldo(mensaje.lower(), estado) == intencion


# TOOL RAG: si el retriever (GCP) falla, se responde con el respaldo local; si no hay chunks, se dice con claridad.
def test_buscar_rag_degrada_al_respaldo_local(monkeypatch):
    import sys, types

    falso = types.ModuleType("app.tools.retriever_gcp")
    def retrieve_chunks(query, top_k=6):
        raise ConnectionError("pool timeout")
    falso.retrieve_chunks = retrieve_chunks
    monkeypatch.setitem(sys.modules, "app.tools.retriever_gcp", falso)

    respuesta = consulta_rag.buscar_rag("¿cuál es la política de anticipación?")
    assert "72 horas" in respuesta  # viene de MOCK_KNOWLEDGE (POL-001)
    assert "asesor" in consulta_rag.buscar_rag("¿puedo pagar con criptomonedas?").lower()

    falso.retrieve_chunks = lambda query, top_k=6: []
    assert consulta_rag.buscar_rag("¿atienden en Marte?") == consulta_rag.SIN_RESULTADOS


# FLUJO COMPLETO: la pregunta a mitad de la cotizacion se responde con el RAG y la memoria no se pierde.
def test_pregunta_de_politica_a_mitad_no_pierde_la_cotizacion(monkeypatch):
    import app.flujo as flujo
    from app.flujo import manejar_mensaje

    monkeypatch.setattr(flujo, "buscar_rag", lambda query: f"RAG: respuesta a '{query}'")
    estado = EstadoCotizacion()
    _, estado = manejar_mensaje("Quiero cotizar un cumpleaños de 40 personas el 20 de noviembre de 2027 en Miraflores", estado)
    assert estado.distrito == "Miraflores" and estado.asistentes == 40

    respuesta, estado = manejar_mensaje("una duda: ¿hacen entregas en feriados?", estado)
    assert "RAG: respuesta" in respuesta
    assert estado.distrito == "Miraflores" and estado.asistentes == 40 and estado.etapa == "politica"

    # Al inicio tambien: la pregunta se responde y despues se puede empezar a cotizar con normalidad.
    nuevo = EstadoCotizacion()
    respuesta, nuevo = manejar_mensaje("Hola, antes de cotizar: ¿cuál es su política de anticipación?", nuevo)
    assert "RAG: respuesta" in respuesta and nuevo.tipo_evento is None


# FLUJO COMPLETO: con una cotizacion previa pendiente de "retomar o seguir", la pregunta igual se responde.
def test_pregunta_de_politica_pasa_la_compuerta_de_cotizacion_previa(monkeypatch):
    import app.flujo as flujo
    from app.flujo import manejar_mensaje

    monkeypatch.setattr(flujo, "buscar_rag", lambda query: "RAG: entregamos el dia habil anterior")
    estado = EstadoCotizacion(contacto="999888777")
    estado.estado_previo_pendiente = {"contacto": "999888777", "tipo_evento": "cumpleanos"}

    respuesta, estado = manejar_mensaje("¿hacen entregas en feriados?", estado)
    assert "RAG: entregamos" in respuesta
    assert "retomar la anterior" in respuesta  # recuerda la eleccion pendiente
    assert estado.estado_previo_pendiente is not None
