from app.estado import EstadoCotizacion
from app.decisor_agentico import obtener_disponibilidad_tools
from app.tools.disponibilidad import validar_disponibilidad
from app.tools.disponibilidad import validar_stock_productos
from app.tools.catalogo import buscar_catalogo
from app.tools.cobertura import validar_cobertura
from app.tools.dimensionamiento import dimensionar_evento
from app.tools.calendario import registrar_evento_cotizado, validar_calendario_eventos
from app.almacen_calendario import cargar_reservas_eventos


# Prueba el comportamiento de test catalogo encuentra opcion matrimonio.
def test_catalogo_encuentra_opcion_matrimonio():
    estado = EstadoCotizacion(tipo_evento="matrimonio", asistentes=100, productos_solicitados=["bar movil"])
    resultado = buscar_catalogo(estado)
    assert any(option["id"] == "PKG-BAR-100" for option in resultado["options"])


# Prueba el comportamiento de test cobertura rechaza distrito sin cobertura.
def test_cobertura_rechaza_distrito_sin_cobertura():
    estado = EstadoCotizacion(distrito="Chosica")
    resultado = validar_cobertura(estado)
    assert resultado["ok"] is False


# Prueba el comportamiento de test disponibilidad descarta opcion no disponible.
def test_disponibilidad_descarta_opcion_no_disponible():
    estado = EstadoCotizacion(fecha_evento="2026-10-25")
    options = [{"id": "PKG-CORP-150"}]
    resultado = validar_disponibilidad(estado, options)
    assert resultado["available_options"] == []
    assert resultado["opciones_descartadas"]


# Prueba el comportamiento de test dimensionamiento devuelve regla versionada.
def test_dimensionamiento_devuelve_regla_versionada():
    estado = EstadoCotizacion(asistentes=100, productos_solicitados=["vino", "hielo"])
    resultado = dimensionar_evento(estado)
    assert resultado["rule_id"] == "DIM-001"
    assert [item["concept"] for item in resultado["items"]] == ["vino", "hielo"]


# Prueba el comportamiento de test stock sugiere alternativas categoria si producto falta.
def test_stock_sugiere_alternativas_categoria_si_producto_falta():
    estado = EstadoCotizacion(fecha_evento="2026-11-15", tipo_evento="matrimonio")
    catalog = buscar_catalogo(estado)
    resultado = validar_stock_productos(
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


# Prueba el comportamiento de test calendario agrega reservas sin reemplazar misma sesion.
def test_calendario_agrega_reservas_sin_reemplazar_misma_sesion():
    estado = EstadoCotizacion(
        tipo_evento="matrimonio",
        asistentes=30,
        fecha_evento="2027-02-24",
        distrito="Miraflores",
        nombre_cliente="Ana Torres",
        contacto="999111222",
        cotizacion={"quote_id": "Q-POC-A"},
    )
    registrar_evento_cotizado(estado)

    estado.fecha_evento = "2027-02-25"
    estado.contacto = "999333444"
    estado.cotizacion = {"quote_id": "Q-POC-B"}
    registrar_evento_cotizado(estado)

    reservas = cargar_reservas_eventos()
    assert len(reservas) == 2
    assert {reserva["fecha_evento"] for reserva in reservas} == {"2027-02-24", "2027-02-25"}


# Prueba el comportamiento de test calendario bloquea cruce aunque sea misma sesion.
def test_calendario_bloquea_cruce_aunque_sea_misma_sesion():
    estado = EstadoCotizacion(
        tipo_evento="matrimonio",
        asistentes=30,
        fecha_evento="2027-02-24",
        distrito="Miraflores",
        nombre_cliente="Ana Torres",
        contacto="999111222",
        cotizacion={"quote_id": "Q-POC-A"},
    )
    registrar_evento_cotizado(estado)

    nueva_cotizacion = EstadoCotizacion(
        id_sesion=estado.id_sesion,
        tipo_evento="cumpleanos",
        asistentes=20,
        fecha_evento="2027-02-24",
        distrito="Miraflores",
        nombre_cliente="Luis Ramos",
        contacto="999333444",
    )
    resultado = validar_calendario_eventos(nueva_cotizacion)

    assert resultado["ok"] is False
    assert len(resultado["reservas_cruzadas"]) == 1


# IMAGEN MULTIMODAL: apagada por defecto -> SVG local; encendida -> PNG del proveedor (simulado); error -> SVG local.
def test_imagen_multimodal_apagada_usa_svg_y_encendida_guarda_png(tmp_path, monkeypatch):
    import base64, io, json
    from pathlib import Path

    import app.artefactos as artefactos
    from app.artefactos import generar_artefacto_visual_cotizacion

    monkeypatch.setattr(artefactos, "ARTIFACT_DIR", tmp_path)
    estado = EstadoCotizacion(tipo_evento="matrimonio", asistentes=30, fecha_evento="2027-02-15", distrito="Miraflores")
    estado.opcion_recomendada = {"id": "PKG-BAR-100", "name": "Bar movil premium"}
    estado.cotizacion = {"quote_id": "COT-TEST", "total": 3304.0, "currency": "PEN", "details": []}

    monkeypatch.setenv("IMAGE_GENERATION_ENABLED", "false")
    assert generar_artefacto_visual_cotizacion(estado).endswith(".svg")

    monkeypatch.setenv("IMAGE_GENERATION_ENABLED", "true")
    monkeypatch.setenv("IMAGE_API_KEY", "clave-de-prueba")
    falso_png = base64.b64encode(b"\x89PNG\r\n\x1a\nprueba").decode()

    class RespuestaFalsa(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(artefactos, "urlopen", lambda request, timeout=0, context=None: RespuestaFalsa(json.dumps({"data": [{"b64_json": falso_png}]}).encode()))
    ruta = generar_artefacto_visual_cotizacion(estado)
    assert ruta.endswith(".png") and Path(ruta).read_bytes().startswith(b"\x89PNG")

    def falla(request, timeout=0, context=None):
        raise TimeoutError("sin respuesta")
    monkeypatch.setattr(artefactos, "urlopen", falla)
    assert generar_artefacto_visual_cotizacion(estado).endswith(".svg")


# FOTO DEL LOCAL + COMPOSICION: validacion de la foto, rutas publicas sin traversal, referencias por producto y
# composicion con el proveedor simulado; sin foto se usa la generacion por prompt / SVG.
def test_foto_local_valida_tipo_y_tamano(tmp_path, monkeypatch):
    import app.artefactos as artefactos
    from app.artefactos import guardar_foto_local, ruta_imagen_publica

    monkeypatch.setattr(artefactos, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(artefactos, "ARTIFACT_DIR", tmp_path / "generated")
    ruta = guardar_foto_local("abcdef12-sesion", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "local.png")
    assert ruta.endswith("local_abcdef12.png")
    import pytest as _pytest
    with _pytest.raises(ValueError):
        guardar_foto_local("s", b"GIF89a" + b"0" * 10, "x.gif")
    with _pytest.raises(ValueError):
        guardar_foto_local("s", b"\xff\xd8\xff" + b"0" * (8 * 1024 * 1024 + 1), "grande.jpg")
    assert ruta_imagen_publica("local_abcdef12.png") is not None
    assert ruta_imagen_publica("../../.env") is None and ruta_imagen_publica("no_existe.png") is None


def test_referencias_de_productos_por_categoria():
    from app.artefactos import imagenes_referencia_productos

    estado = EstadoCotizacion(tipo_evento="matrimonio", asistentes=30)
    estado.opcion_recomendada = {"id": "PKG-BAR-100", "name": "Bar movil premium", "items": [{"name": "Bar movil premium"}]}
    estado.cotizacion = {"quote_id": "COT-X", "total": 1.0, "details": [{"concept": "cerveza"}, {"concept": "hielo"}, {"concept": "agua"}]}
    nombres = [r.name for r in imagenes_referencia_productos(estado)]
    assert nombres[0] == "bar_movil.png" and "cerveza.png" in nombres and "hielo.png" in nombres and "agua.png" in nombres


def test_composicion_sobre_foto_usa_el_proveedor_y_degrada_si_falla(tmp_path, monkeypatch):
    import base64, types

    import app.artefactos as artefactos
    from app.artefactos import generar_artefacto_visual_cotizacion

    monkeypatch.setattr(artefactos, "ARTIFACT_DIR", tmp_path)
    foto = tmp_path / "local.jpg"; foto.write_bytes(b"\xff\xd8\xff" + b"0" * 50)
    estado = EstadoCotizacion(tipo_evento="matrimonio", asistentes=30, fecha_evento="2027-02-15", distrito="Miraflores")
    estado.opcion_recomendada = {"id": "PKG-BAR-100", "name": "Bar movil premium"}
    estado.cotizacion = {"quote_id": "COT-F", "total": 3304.0, "currency": "PEN", "details": [{"concept": "cerveza"}]}
    estado.foto_local = str(foto)
    monkeypatch.setenv("IMAGE_GENERATION_ENABLED", "true"); monkeypatch.setenv("IMAGE_API_KEY", "clave-de-prueba")

    llamadas = {}
    class ImagenesFalsas:
        def edit(self, **kwargs):
            llamadas["edit"] = {"n_imagenes": len(kwargs["image"]), "prompt": kwargs["prompt"]}
            return types.SimpleNamespace(data=[types.SimpleNamespace(b64_json=base64.b64encode(b"\x89PNGcompuesta").decode())])
    class ClienteFalso:
        def __init__(self, api_key=None): self.images = ImagenesFalsas()
    import openai
    monkeypatch.setattr(openai, "OpenAI", ClienteFalso)
    ruta = generar_artefacto_visual_cotizacion(estado)
    assert ruta.endswith(".png") and (tmp_path / ruta.split("/")[-1]).read_bytes().startswith(b"\x89PNGcompuesta")
    assert llamadas["edit"]["n_imagenes"] >= 2 and "foto real del local" in llamadas["edit"]["prompt"]
    assert any(t["evento"] == "componer_imagen_sobre_foto" for t in estado.trazas)

    class ClienteQueFalla:
        def __init__(self, api_key=None): raise RuntimeError("proveedor caido")
    monkeypatch.setattr(openai, "OpenAI", ClienteQueFalla)
    def sin_red(request, timeout=0, context=None): raise TimeoutError("sin red")
    monkeypatch.setattr(artefactos, "urlopen", sin_red)
    assert generar_artefacto_visual_cotizacion(estado).endswith(".svg")


def test_endpoint_foto_guarda_en_la_sesion(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import app.artefactos as artefactos
    from app.api import aplicacion

    monkeypatch.setattr(artefactos, "UPLOAD_DIR", tmp_path)
    cliente = TestClient(aplicacion)
    id_sesion = cliente.post("/api/sesiones", json={}).json()["id_sesion"]
    import base64
    png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()
    r = cliente.post(f"/api/sesiones/{id_sesion}/foto", json={"imagen_base64": png, "nombre": "local.png"})
    assert r.status_code == 200 and r.json()["foto_local"].endswith(".png")
    assert cliente.post(f"/api/sesiones/{id_sesion}/foto", json={"imagen_base64": base64.b64encode(b"GIF89a" + b"0" * 64).decode(), "nombre": "x.gif"}).status_code == 400
    nombre = r.json()["foto_local"].split("/")[-1]
    assert cliente.get(f"/api/imagenes/{nombre}").status_code == 200
    assert cliente.get("/api/imagenes/no-existe.png").status_code == 404
