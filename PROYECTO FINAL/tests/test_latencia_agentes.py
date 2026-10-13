from __future__ import annotations

from types import SimpleNamespace

from app.configuracion_llm import ConfiguracionLLM
from app.estado import EstadoCotizacion


# TEST LATENCIA: valida que el modelo agentico se construya con timeout y pocos reintentos.
def test_construir_modelo_chat_agentico_configura_timeout_y_reintentos(monkeypatch):
    from app import modelo_agentico

    captura = {}

    def fake_init_chat_model(modelo, **kwargs):
        captura["modelo"] = modelo
        captura["kwargs"] = kwargs
        return "modelo-falso"

    monkeypatch.setattr("langchain.chat_models.init_chat_model", fake_init_chat_model)
    config = ConfiguracionLLM(
        habilitado=True,
        proveedor="openai",
        model="gpt-4o-mini",
        clave_api="sk-test",
        segundos_timeout=12,
    )

    modelo = modelo_agentico.construir_modelo_chat_agentico(config)

    assert modelo == "modelo-falso"
    assert captura["modelo"] == "openai:gpt-4o-mini"
    assert captura["kwargs"]["temperature"] == 0
    assert captura["kwargs"]["timeout"] == 12
    assert captura["kwargs"]["max_retries"] == 1
    assert captura["kwargs"]["api_key"] == "sk-test"


# TEST LATENCIA: valida que la tool del decisor sea return_direct y devuelva una accion sin segunda vuelta.
def test_decisor_agentico_tool_return_direct(monkeypatch):
    from app import decisor_agentico

    captura = {}

    def fake_create_agent(**kwargs):
        captura.update(kwargs)
        return "agente-decisor"

    monkeypatch.setattr("langchain.agents.create_agent", fake_create_agent)
    monkeypatch.setattr(decisor_agentico, "construir_modelo_chat_agentico", lambda config: "modelo-falso")
    monkeypatch.setattr(decisor_agentico, "obtener_middleware_langchain_guardrails", lambda: [])

    agente = decisor_agentico.crear_agente_decisor()
    herramienta = captura["tools"][0]
    salida = herramienta.invoke(
        {
            "mensaje_usuario": "genera la cotizacion",
            "tiene_campos_faltantes": False,
            "tiene_recomendacion": True,
            "tiene_cotizacion": False,
            "puede_responder_precio": True,
            "puede_validar_y_recomendar": True,
            "puede_generar_cotizacion": True,
            "puede_mostrar_imagen": False,
            "solicito_emitir_propuesta": True,
        }
    )

    assert agente == "agente-decisor"
    assert herramienta.return_direct is True
    assert salida == "generar_cotizacion"


# TEST LATENCIA: valida que la tool del extractor sea return_direct y entregue JSON estructurado.
def test_extractor_agentico_tool_return_direct(monkeypatch):
    from app import extractor_agentico

    captura = {}

    def fake_create_agent(**kwargs):
        captura.update(kwargs)
        return "agente-extractor"

    monkeypatch.setattr("langchain.agents.create_agent", fake_create_agent)
    monkeypatch.setattr(extractor_agentico, "construir_modelo_chat_agentico", lambda config: "modelo-falso")
    monkeypatch.setattr(extractor_agentico, "obtener_middleware_langchain_guardrails", lambda: [])

    agente = extractor_agentico.crear_agente_extractor()
    herramienta = captura["tools"][0]
    salida = herramienta.invoke(
        {
            "tipo_evento": "matrimonio",
            "asistentes": "30",
            "fecha_evento": "2027-02-05",
            "distrito": "Miraflores",
            "nombre_cliente": "Juan Perez",
            "contacto": "999888777",
            "requested_products_csv": "cerveza,hielo",
        }
    )

    assert agente == "agente-extractor"
    assert herramienta.return_direct is True
    assert '"tipo_evento": "matrimonio"' in salida
    assert '"requested_products_csv": "cerveza,hielo"' in salida


# TEST LATENCIA: si create_agent excede recursion, el wrapper registra traza y deja fallback.
def test_invocar_agente_con_guardrails_captura_recursion(monkeypatch):
    from langgraph.errors import GraphRecursionError

    from app.guardrails import capa_intermedia

    class AgenteConRecursion:
        def invoke(self, carga, config=None):
            assert config == {"recursion_limit": 6}
            raise GraphRecursionError("recursion alcanzada")

    estado = EstadoCotizacion()
    monkeypatch.setattr(
        capa_intermedia,
        "validar_mensaje_entrada",
        lambda mensaje: SimpleNamespace(permitido=True, motivo="entrada valida"),
    )

    resultado = capa_intermedia.invocar_agente_con_guardrails(
        AgenteConRecursion(),
        {"messages": [{"role": "user", "content": "hola"}]},
        "hola",
        estado,
        "agente_decisor",
    )

    assert resultado is None
    assert any(
        traza["evento"] == "agente_recursion_error" and traza["carga"]["agente"] == "agente_decisor"
        for traza in estado.trazas
    )
