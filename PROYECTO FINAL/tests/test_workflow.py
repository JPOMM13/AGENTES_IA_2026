from app.state import QuoteState
from app.workflow import manejar_mensaje
import app.session_store as session_store
import app.redis_session_store as redis_session_store
import app.artifacts as artifacts


# Prueba el comportamiento de test flujo recomendacion completo.
def test_flujo_recomendacion_completo():
    state = QuoteState()
    response, state = manejar_mensaje(
        "Soy Juan Perez, mi telefono es 999888777. Necesito bar movil premium para un matrimonio de 100 personas el 25 de octubre en Miraflores",
        state,
    )
    assert "Bar movil premium" in response
    assert state.recommended_option["id"] == "PKG-BAR-100"
    assert state.coverage_ok is True
    assert state.availability_ok is True


# Prueba el comportamiento de test pide campos faltantes.
def test_pide_campos_faltantes():
    state = QuoteState()
    response, state = manejar_mensaje("Quiero organizar un cumpleanos", state)
    assert "asistentes" in response
    assert "persona que cotiza" not in response
    assert state.recommended_option is None


# Prueba el comportamiento de test cotizacion despues recomendacion.
def test_cotizacion_despues_recomendacion():
    state = QuoteState()
    _, state = manejar_mensaje(
        "Soy Juan Perez, mi telefono es 999888777. Necesito bar movil premium para un matrimonio de 100 personas el 25 de octubre en Miraflores",
        state,
    )
    response, state = manejar_mensaje("Cuanto cuesta?", state)
    assert "sin generar cotizacion" in response
    assert state.quote is None

    response, state = manejar_mensaje("genera la cotizacion", state)
    assert "Cotizacion mock" in response
    assert state.quote["total"] == 3304.0


# Prueba el comportamiento de test cotizacion genera artefacto visual.
def test_cotizacion_genera_artefacto_visual(monkeypatch, tmp_path):
    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path / "generated")
    state = QuoteState()
    _, state = manejar_mensaje(
        "Soy Juan Perez, mi telefono es 999888777. Necesito bar movil premium para un matrimonio de 100 personas el 25 de octubre en Miraflores",
        state,
    )
    _, state = manejar_mensaje("genera la cotizacion", state)

    assert state.quote_artifact_image
    assert (tmp_path / "generated").exists()
    assert "Q-POC-0001" in state.quote_artifact_image


# Prueba el comportamiento de test descuento no cambia precio y ofrece derivacion.
def test_descuento_no_cambia_precio_y_ofrece_derivacion():
    state = QuoteState()
    _, state = manejar_mensaje(
        "Soy Juan Perez, mi telefono es 999888777. Necesito bar movil premium para un matrimonio de 100 personas el 25 de octubre en Miraflores",
        state,
    )
    _, state = manejar_mensaje("genera la cotizacion", state)
    original_total = state.quote["total"]
    response, state = manejar_mensaje("Me haces 15% de descuento?", state)
    assert "No puedo aprobar descuentos" in response
    assert state.quote["total"] == original_total
    assert state.handoff_offered is True


# Prueba el comportamiento de test no cotiza sin cobertura.
def test_no_cotiza_sin_cobertura():
    state = QuoteState()
    response, state = manejar_mensaje(
        "Soy Ana, mi telefono es 999111222. Necesito cerveza y gaseosas sencillas para una reunion de 80 personas el 25 de octubre en Chosica",
        state,
    )
    assert "No tengo cobertura" in response
    assert state.quote is None


# Prueba el comportamiento de test recoleccion incremental e imagen despues cotizacion.
def test_recoleccion_incremental_e_imagen_despues_cotizacion():
    state = QuoteState()
    response, state = manejar_mensaje("Quiero organizar un matrimonio", state)
    assert "asistentes" in response

    response, state = manejar_mensaje("Soy Ana Torres y mi telefono es 999111222", state)
    assert "asistentes" in response

    response, state = manejar_mensaje("Seran 100 personas el 25 de octubre en Miraflores, prefiero premium y vino", state)
    assert "productos disponibles" in response

    response, state = manejar_mensaje("muestrame una imagen", state)
    assert "despues de generar una cotizacion" in response
    assert state.image_requested is False

    _, state = manejar_mensaje("genera la cotizacion", state)
    response, state = manejar_mensaje("muestrame una imagen", state)
    assert "Muestro una imagen" in response
    assert state.image_requested is True


# Prueba el comportamiento de test extrae nombre cerca telefono y usa memoria temporal.
def test_extrae_nombre_cerca_telefono_y_usa_memoria_temporal():
    state = QuoteState()
    _, state = manejar_mensaje("Necesito bebidas para un matrimonio de 100 personas el 25 de octubre en Miraflores", state)

    response, state = manejar_mensaje("John Manchego mi numero es 989515182", state)
    assert state.customer_name == "John Manchego"
    assert state.contact == "989515182"
    assert "productos o servicios" in response
    assert "nombre de la persona" not in response

    response, state = manejar_mensaje("ya te di mi nombre", state)
    assert "John Manchego" in response


# Prueba el comportamiento de test extrae nombre mayusculas mixtas antes telefono.
def test_extrae_nombre_mayusculas_mixtas_antes_telefono():
    state = QuoteState()
    _, state = manejar_mensaje("Necesito bebidas para un matrimonio de 50 personas el 4 de diciembre en Miraflores", state)

    response, state = manejar_mensaje("JOhn manchego y mi numero es 989515182", state)

    assert state.customer_name == "John Manchego"
    assert state.contact == "989515182"
    assert "nombre de la persona" not in response


# Prueba el comportamiento de test cae a cotizacion productos si no calza paquete.
def test_cae_a_cotizacion_productos_si_no_calza_paquete():
    state = QuoteState()
    response, state = manejar_mensaje(
        "Soy Luis Ramos, mi telefono es 999222333. Necesito cerveza, vino, gaseosas, hielo y bartender premium para una reunion de 100 personas el 25 de octubre en Miraflores",
        state,
    )
    assert "productos disponibles" in response
    assert state.recommended_option["source"] == "products"

    response, state = manejar_mensaje("Cuanto cuesta?", state)
    assert "sin generar cotizacion" in response
    assert state.quote is None

    response, state = manejar_mensaje("genera la cotizacion", state)
    assert "Cotizacion por productos disponibles" in response
    assert state.quote["total"] == 4035.6


# Prueba el comportamiento de test consulta precio producto no crea cotizacion.
def test_consulta_precio_producto_no_crea_cotizacion():
    state = QuoteState()
    response, state = manejar_mensaje("Cuanto cuesta el vino?", state)
    assert "Vino tinto reserva" in response
    assert "sin generar cotizacion" in response
    assert state.quote is None


# Prueba el comportamiento de test producto no soportado sugiere similar antes cotizar.
def test_producto_no_soportado_sugiere_similar_antes_cotizar():
    state = QuoteState()
    response, state = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito whisky economico para un matrimonio de 34 personas el 25 de octubre en Miraflores",
        state,
    )
    assert "no lo tengo en catalogo mock" in response
    assert "vino" in response
    assert "cerveza" in response
    assert state.recommended_option is None
    assert state.unsupported_requested_products == ["whisky"]

    response, state = manejar_mensaje("entonces reemplazalo por vino", state)
    assert state.unsupported_requested_products == []
    assert state.requested_products == ["vino"]
    assert "productos disponibles" in response


# Prueba el comportamiento de test aceptar alternativa mantiene hilo sin derivacion.
def test_aceptar_alternativa_mantiene_hilo_sin_derivacion():
    state = QuoteState()
    response, state = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito gaseosas cerveza pisco ron para un matrimonio de 45 personas el 23 de diciembre en Miraflores",
        state,
    )
    assert "pisco" in response
    assert "vino" in response
    assert state.unsupported_requested_products == ["pisco"]

    response, state = manejar_mensaje("si dame vino", state)
    assert state.unsupported_requested_products == []
    assert "WhatsApp" not in response
    assert "productos disponibles" in response
    assert state.recommended_option["source"] == "products"


# Prueba el comportamiento de test producto sin stock sugiere alternativas misma familia.
def test_producto_sin_stock_sugiere_alternativas_misma_familia():
    state = QuoteState()
    response, state = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito vino para un matrimonio de 100 personas el 15 de noviembre en Miraflores",
        state,
    )
    assert "Stock insuficiente" in response or "stock" in response
    assert "Ron añejo botella" in response
    assert "Cerveza artesanal lata" in response
    assert state.recommended_option is None


# Prueba el comportamiento de test fecha parcial indica faltante y luego completa.
def test_fecha_parcial_indica_faltante_y_luego_completa():
    state = QuoteState()
    response, state = manejar_mensaje(
        "es matrimonio, 34 personas, para diciembre, miraflores, para John Manchego, 989515182 que sea economico",
        state,
    )
    assert "falta el dia" in response
    assert state.partial_date["month"] == 12
    assert state.event_date is None

    response, state = manejar_mensaje("para el 4 de diciembre", state)
    assert state.event_date == "2026-12-04"
    assert "fecha" not in state.missing_fields


# Prueba el comportamiento de test fecha parcial solo dia indica mes faltante.
def test_fecha_parcial_solo_dia_indica_mes_faltante():
    state = QuoteState()
    response, state = manejar_mensaje("para el 4", state)
    assert "falta el mes" in response
    assert state.partial_date["day"] == 4


# Prueba el comportamiento de test numero asistentes no se usa como dia evento.
def test_numero_asistentes_no_se_usa_como_dia_evento():
    state = QuoteState()
    _, state = manejar_mensaje("necesito cotizar un matrimonio", state)
    _, state = manejar_mensaje("30 personas", state)
    assert state.attendees == 30
    assert state.partial_date["day"] is None
    assert state.event_date is None

    response, state = manejar_mensaje("sera en septiembre y en miraflores", state)
    assert state.event_date is None
    assert state.partial_date["month"] == 9
    assert "falta el dia" in response


# Prueba el comportamiento de test asistentes en seguimiento no activa derivacion.
def test_asistentes_en_seguimiento_no_activa_derivacion():
    state = QuoteState()
    _, state = manejar_mensaje("es un matrimonio", state)
    response, state = manejar_mensaje("es para 20 personas", state)

    assert state.attendees == 20
    assert state.intent != "human_handoff"
    assert state.stage == "recoleccion"
    assert state.handoff_confirmed is False
    assert "WhatsApp" not in response


# Prueba el comportamiento de test numero suelto llena asistentes si agente los pidio.
def test_numero_suelto_llena_asistentes_si_agente_los_pidio():
    state = QuoteState()
    response, state = manejar_mensaje(
        "Quiero una cotizacion para un evento de matrimonio, para el 24 de febrero del 2027 en Miraflores, mi nombre es John Manchego y mi numero de celular es 989515182",
        state,
    )
    assert state.event_date == "2027-02-24"
    assert "cantidad de asistentes" in response

    response, state = manejar_mensaje("80", state)

    assert state.attendees == 80
    assert "cantidad de asistentes" not in state.missing_fields
    assert "productos" in response.lower()


# Prueba el comportamiento de test productos faltantes lista catalogo para elegir.
def test_productos_faltantes_lista_catalogo_para_elegir():
    state = QuoteState()
    response, state = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Es un matrimonio para 45 personas el 23 de diciembre en Miraflores",
        state,
    )

    assert "Productos disponibles para elegir" in response
    assert "Cerveza artesanal lata" in response
    assert "Vino tinto reserva" in response
    assert "Gaseosa 1.5L" in response
    assert "Pack celebracion esencial" in response
    assert state.recommended_option is None


# Prueba el comportamiento de test usuario puede revisar y modificar productos antes cotizar.
def test_usuario_puede_revisar_y_modificar_productos_antes_cotizar():
    state = QuoteState()
    _, state = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Es un matrimonio para 45 personas el 23 de diciembre en Miraflores",
        state,
    )
    _, state = manejar_mensaje("quiero cerveza, vino y hielo", state)
    assert state.recommended_option is not None

    response, state = manejar_mensaje("quitar vino", state)
    assert "vino" not in state.requested_products
    assert state.quote is None
    assert state.recommended_option is None
    assert "Productos/servicios: cerveza, hielo" in response

    response, state = manejar_mensaje("cambiar cerveza por agua", state)
    assert "cerveza" not in state.requested_products
    assert "agua" in state.requested_products
    assert "Productos/servicios: hielo, agua" in response


# Prueba el comportamiento de test cambio implicito reemplaza producto sin stock.
def test_cambio_implicito_reemplaza_producto_sin_stock():
    state = QuoteState()
    _, state = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito cerveza vino agua y hielo para un matrimonio de 100 personas el 25 de octubre en Miraflores",
        state,
    )
    assert "agua" in state.stock_shortage_products

    response, state = manejar_mensaje("cambialo por gaseosa", state)

    assert "agua" not in state.requested_products
    assert "gaseosa" in state.requested_products
    assert state.stock_shortage_products == []
    assert "Productos considerados" in response


# Prueba el comportamiento de test puede retomar conversacion previa por identidad.
def test_puede_retomar_conversacion_previa_por_identidad(monkeypatch, tmp_path):
    monkeypatch.setattr(session_store, "STORE_PATH", tmp_path / "mock_session_memory.json")
    monkeypatch.setattr(redis_session_store, "REDIS_MOCK_PATH", tmp_path / "mock_redis_session.json")
    original = QuoteState()
    _, original = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito cerveza y vino para un matrimonio de 45 personas el 23 de diciembre en Miraflores",
        original,
    )
    assert original.customer_name == "John Manchego"
    assert original.contact == "989515182"
    assert original.requested_products == ["cerveza", "vino"]

    new_session = QuoteState()
    response, resumed = manejar_mensaje(
        "quiero retomar mi cotizacion anterior, soy John Manchego mi numero es 989515182",
        new_session,
    )

    assert "retome la ultima cotizacion" in response
    assert resumed.session_id == new_session.session_id
    assert resumed.customer_name == "John Manchego"
    assert resumed.contact == "989515182"
    assert resumed.event_type == "matrimonio"
    assert resumed.attendees == 45
    assert resumed.event_date == "2026-12-23"
    assert resumed.district == "Miraflores"
    assert resumed.requested_products == ["cerveza", "vino"]

    active_session = redis_session_store.cargar_sesion_activa(new_session.session_id)
    assert active_session is not None
    assert active_session.session_id == new_session.session_id
    assert active_session.customer_name == "John Manchego"
    assert active_session.requested_products == ["cerveza", "vino"]


# Prueba el comportamiento de test contacto coincidente pregunta antes sobrescribir cotizacion.
def test_contacto_coincidente_pregunta_antes_sobrescribir_cotizacion(monkeypatch, tmp_path):
    monkeypatch.setattr(session_store, "STORE_PATH", tmp_path / "mock_session_memory.json")
    monkeypatch.setattr(redis_session_store, "REDIS_MOCK_PATH", tmp_path / "mock_redis_session.json")
    previous = QuoteState()
    _, previous = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito cerveza y vino para un matrimonio de 45 personas el 23 de diciembre en Miraflores",
        previous,
    )

    current = QuoteState()
    _, current = manejar_mensaje("necesito cotizar un matrimonio", current)
    _, current = manejar_mensaje("20 personas el 23 de diciembre en Miraflores", current)
    response, current = manejar_mensaje("John Manchego numero 989515182", current)

    assert "Encontre una cotizacion previa" in response
    assert "Datos que acabas de dar" in response
    assert "Cotizacion previa encontrada" in response
    assert "Productos/servicios: cerveza, vino" in response
    assert current.pending_previous_state is not None

    response, resumed = manejar_mensaje("retomar la anterior", current)
    assert "retome la cotizacion previa" in response
    assert resumed.session_id == current.session_id
    assert resumed.attendees == 45
    assert resumed.requested_products == ["cerveza", "vino"]


# Prueba el comportamiento de test sesion activa se guarda por session id.
def test_sesion_activa_se_guarda_por_session_id(monkeypatch, tmp_path):
    monkeypatch.setattr(redis_session_store, "REDIS_MOCK_PATH", tmp_path / "mock_redis_session.json")
    state = QuoteState()
    session_id = state.session_id

    _, state = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito cerveza para un matrimonio de 30 personas el 25 de octubre en Miraflores",
        state,
    )

    restored = redis_session_store.cargar_sesion_activa(session_id)
    assert restored is not None
    assert restored.session_id == session_id
    assert restored.customer_name == "John Manchego"
    assert restored.contact == "989515182"
    assert restored.event_type == "matrimonio"
    assert restored.attendees == 30
    assert restored.requested_products == ["cerveza"]

    another_state = QuoteState()
    _, another_state = manejar_mensaje(
        "Soy Ana Torres, mi telefono es 999111222. Necesito vino para un matrimonio de 20 personas el 25 de octubre en Miraflores",
        another_state,
    )
    assert redis_session_store.cargar_sesion_activa(session_id) is None
    assert redis_session_store.cargar_sesion_activa(another_state.session_id) is not None

    redis_session_store.reiniciar_sesion_activa(another_state.session_id)
    assert redis_session_store.cargar_sesion_activa(another_state.session_id) is None
