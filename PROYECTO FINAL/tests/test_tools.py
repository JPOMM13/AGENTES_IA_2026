from app.state import QuoteState
from app.agentic_decider import obtener_disponibilidad_tools
from app.tools.availability import mock_validar_disponibilidad
from app.tools.availability import mock_validar_stock_productos
from app.tools.catalog import mock_buscar_catalogo
from app.tools.coverage import mock_validar_cobertura
from app.tools.dimensioning import mock_dimensionar_evento


# Prueba el comportamiento de test catalogo encuentra opcion matrimonio.
def test_catalogo_encuentra_opcion_matrimonio():
    state = QuoteState(event_type="matrimonio", attendees=100, requested_products=["bar movil"])
    result = mock_buscar_catalogo(state)
    assert any(option["id"] == "PKG-BAR-100" for option in result["options"])


# Prueba el comportamiento de test cobertura rechaza distrito sin cobertura.
def test_cobertura_rechaza_distrito_sin_cobertura():
    state = QuoteState(district="Chosica")
    result = mock_validar_cobertura(state)
    assert result["ok"] is False


# Prueba el comportamiento de test disponibilidad descarta opcion no disponible.
def test_disponibilidad_descarta_opcion_no_disponible():
    state = QuoteState(event_date="2026-10-25")
    options = [{"id": "PKG-CORP-150"}]
    result = mock_validar_disponibilidad(state, options)
    assert result["available_options"] == []
    assert result["discarded_options"]


# Prueba el comportamiento de test dimensionamiento devuelve regla versionada.
def test_dimensionamiento_devuelve_regla_versionada():
    state = QuoteState(attendees=100, requested_products=["vino", "hielo"])
    result = mock_dimensionar_evento(state)
    assert result["rule_id"] == "DIM-POC-001"
    assert [item["concept"] for item in result["items"]] == ["vino", "hielo"]


# Prueba el comportamiento de test stock sugiere alternativas categoria si producto falta.
def test_stock_sugiere_alternativas_categoria_si_producto_falta():
    state = QuoteState(event_date="2026-11-15", event_type="matrimonio")
    catalog = mock_buscar_catalogo(state)
    result = mock_validar_stock_productos(
        state,
        [{"concept": "vino", "quantity": 35, "unit": "botellas"}],
        catalog["all_products"],
    )
    alternatives = result["missing_items"][0]["alternatives"]
    assert any(alternative["category"] == "ron" for alternative in alternatives)
    assert any(alternative["category"] == "cerveza" for alternative in alternatives)


# Prueba el comportamiento de test disponibilidad tools bloquea negocio sin datos minimos.
def test_disponibilidad_tools_bloquea_negocio_sin_datos_minimos():
    state = QuoteState(missing_fields=["event_date", "district", "customer_name"])
    readiness = obtener_disponibilidad_tools("genera la cotizacion", state)
    assert readiness["can_validate_and_recommend"] is False
    assert readiness["can_generate_quote"] is False
    assert readiness["can_show_image"] is False


# Prueba el comportamiento de test disponibilidad tools permite precio informativo producto.
def test_disponibilidad_tools_permite_precio_informativo_producto():
    state = QuoteState(missing_fields=["event_date", "district", "customer_name"])
    readiness = obtener_disponibilidad_tools("cuanto cuesta el vino", state)
    assert readiness["can_answer_price"] is True
