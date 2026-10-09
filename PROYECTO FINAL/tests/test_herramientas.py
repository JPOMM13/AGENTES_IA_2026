from app.estado import EstadoCotizacion
from app.decisor_agentico import obtener_disponibilidad_tools
from app.tools.disponibilidad import mock_validar_disponibilidad
from app.tools.disponibilidad import mock_validar_stock_productos
from app.tools.catalogo import mock_buscar_catalogo
from app.tools.cobertura import mock_validar_cobertura
from app.tools.dimensionamiento import mock_dimensionar_evento


# Prueba el comportamiento de test catalogo encuentra opcion matrimonio.
def test_catalogo_encuentra_opcion_matrimonio():
    estado = EstadoCotizacion(tipo_evento="matrimonio", asistentes=100, productos_solicitados=["bar movil"])
    resultado = mock_buscar_catalogo(estado)
    assert any(option["id"] == "PKG-BAR-100" for option in resultado["options"])


# Prueba el comportamiento de test cobertura rechaza distrito sin cobertura.
def test_cobertura_rechaza_distrito_sin_cobertura():
    estado = EstadoCotizacion(distrito="Chosica")
    resultado = mock_validar_cobertura(estado)
    assert resultado["ok"] is False


# Prueba el comportamiento de test disponibilidad descarta opcion no disponible.
def test_disponibilidad_descarta_opcion_no_disponible():
    estado = EstadoCotizacion(fecha_evento="2026-10-25")
    options = [{"id": "PKG-CORP-150"}]
    resultado = mock_validar_disponibilidad(estado, options)
    assert resultado["available_options"] == []
    assert resultado["opciones_descartadas"]


# Prueba el comportamiento de test dimensionamiento devuelve regla versionada.
def test_dimensionamiento_devuelve_regla_versionada():
    estado = EstadoCotizacion(asistentes=100, productos_solicitados=["vino", "hielo"])
    resultado = mock_dimensionar_evento(estado)
    assert resultado["rule_id"] == "DIM-POC-001"
    assert [item["concept"] for item in resultado["items"]] == ["vino", "hielo"]


# Prueba el comportamiento de test stock sugiere alternativas categoria si producto falta.
def test_stock_sugiere_alternativas_categoria_si_producto_falta():
    estado = EstadoCotizacion(fecha_evento="2026-11-15", tipo_evento="matrimonio")
    catalog = mock_buscar_catalogo(estado)
    resultado = mock_validar_stock_productos(
        estado,
        [{"concept": "vino", "quantity": 35, "unit": "botellas"}],
        catalog["all_products"],
    )
    alternatives = resultado["missing_items"][0]["alternatives"]
    assert any(alternative["category"] == "ron" for alternative in alternatives)
    assert any(alternative["category"] == "cerveza" for alternative in alternatives)


# Prueba el comportamiento de test disponibilidad tools bloquea negocio sin datos minimos.
def test_disponibilidad_tools_bloquea_negocio_sin_datos_minimos():
    estado = EstadoCotizacion(campos_faltantes=["fecha_evento", "distrito", "nombre_cliente"])
    disponibilidad = obtener_disponibilidad_tools("genera la cotizacion", estado)
    assert disponibilidad["puede_validar_y_recomendar"] is False
    assert disponibilidad["puede_generar_cotizacion"] is False
    assert disponibilidad["puede_mostrar_imagen"] is False


# Prueba el comportamiento de test disponibilidad tools permite precio informativo producto.
def test_disponibilidad_tools_permite_precio_informativo_producto():
    estado = EstadoCotizacion(campos_faltantes=["fecha_evento", "distrito", "nombre_cliente"])
    disponibilidad = obtener_disponibilidad_tools("cuanto cuesta el vino", estado)
    assert disponibilidad["puede_responder_precio"] is True
