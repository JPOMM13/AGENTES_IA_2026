from app.estado import EstadoCotizacion
from app.workflow import manejar_mensaje
import app.session_store as session_store
import app.redis_session_store as redis_session_store
import app.artifacts as artifacts
import app.tools.extraction as extraction_tools
import app.workflow as workflow


# Prueba el comportamiento de test flujo recomendacion completo.
def test_flujo_recomendacion_completo():
    estado = EstadoCotizacion()
    respuesta, estado = manejar_mensaje(
        "Soy Juan Perez, mi telefono es 999888777. Necesito bar movil premium para un matrimonio de 100 personas el 25 de octubre en Miraflores",
        estado,
    )
    assert "Bar movil premium" in respuesta
    assert estado.opcion_recomendada["id"] == "PKG-BAR-100"
    assert estado.cobertura_ok is True
    assert estado.disponibilidad_ok is True


# Prueba el comportamiento de test pide campos faltantes.
def test_pide_campos_faltantes():
    estado = EstadoCotizacion()
    respuesta, estado = manejar_mensaje("Quiero organizar un cumpleanos", estado)
    assert "asistentes" in respuesta
    assert "persona que cotiza" not in respuesta
    assert estado.opcion_recomendada is None


# Prueba el comportamiento de test cotizacion despues recomendacion.
def test_cotizacion_despues_recomendacion():
    estado = EstadoCotizacion()
    _, estado = manejar_mensaje(
        "Soy Juan Perez, mi telefono es 999888777. Necesito bar movil premium para un matrimonio de 100 personas el 25 de octubre en Miraflores",
        estado,
    )
    respuesta, estado = manejar_mensaje("Cuanto cuesta?", estado)
    assert "sin generar cotizacion" in respuesta
    assert estado.cotizacion is None

    respuesta, estado = manejar_mensaje("genera la cotizacion", estado)
    assert "Cotizacion mock" in respuesta
    assert estado.cotizacion["total"] == 3304.0


# Prueba el comportamiento de test cotizacion genera artefacto visual.
def test_cotizacion_genera_artefacto_visual(monkeypatch, tmp_path):
    monkeypatch.setattr(artifacts, "ARTIFACT_DIR", tmp_path / "generated")
    estado = EstadoCotizacion()
    _, estado = manejar_mensaje(
        "Soy Juan Perez, mi telefono es 999888777. Necesito bar movil premium para un matrimonio de 100 personas el 25 de octubre en Miraflores",
        estado,
    )
    _, estado = manejar_mensaje("genera la cotizacion", estado)

    assert estado.imagen_artefacto_cotizacion
    assert (tmp_path / "generated").exists()
    assert "Q-POC-0001" in estado.imagen_artefacto_cotizacion


# Prueba el comportamiento de test descuento no cambia precio y ofrece derivacion.
def test_descuento_no_cambia_precio_y_ofrece_derivacion():
    estado = EstadoCotizacion()
    _, estado = manejar_mensaje(
        "Soy Juan Perez, mi telefono es 999888777. Necesito bar movil premium para un matrimonio de 100 personas el 25 de octubre en Miraflores",
        estado,
    )
    _, estado = manejar_mensaje("genera la cotizacion", estado)
    original_total = estado.cotizacion["total"]
    respuesta, estado = manejar_mensaje("Me haces 15% de descuento?", estado)
    assert "No puedo aprobar descuentos" in respuesta
    assert estado.cotizacion["total"] == original_total
    assert estado.derivacion_ofrecida is True


# Prueba el comportamiento de test no cotiza sin cobertura.
def test_no_cotiza_sin_cobertura():
    estado = EstadoCotizacion()
    respuesta, estado = manejar_mensaje(
        "Soy Ana, mi telefono es 999111222. Necesito cerveza y gaseosas sencillas para una reunion de 80 personas el 25 de octubre en Chosica",
        estado,
    )
    assert "No tengo cobertura" in respuesta
    assert estado.cotizacion is None


# Prueba el comportamiento de test recoleccion incremental e imagen despues cotizacion.
def test_recoleccion_incremental_e_imagen_despues_cotizacion():
    estado = EstadoCotizacion()
    respuesta, estado = manejar_mensaje("Quiero organizar un matrimonio", estado)
    assert "asistentes" in respuesta

    respuesta, estado = manejar_mensaje("Soy Ana Torres y mi telefono es 999111222", estado)
    assert "asistentes" in respuesta

    respuesta, estado = manejar_mensaje("Seran 100 personas el 25 de octubre en Miraflores, prefiero premium y vino", estado)
    assert "productos disponibles" in respuesta

    respuesta, estado = manejar_mensaje("muestrame una imagen", estado)
    assert "despues de generar una cotizacion" in respuesta
    assert estado.imagen_solicitada is False

    _, estado = manejar_mensaje("genera la cotizacion", estado)
    respuesta, estado = manejar_mensaje("muestrame una imagen", estado)
    assert "Muestro una imagen" in respuesta
    assert estado.imagen_solicitada is True


# Prueba el comportamiento de test extrae nombre cerca telefono y usa memoria temporal.
def test_extrae_nombre_cerca_telefono_y_usa_memoria_temporal():
    estado = EstadoCotizacion()
    _, estado = manejar_mensaje("Necesito bebidas para un matrimonio de 100 personas el 25 de octubre en Miraflores", estado)

    respuesta, estado = manejar_mensaje("John Manchego mi numero es 989515182", estado)
    assert estado.nombre_cliente == "John Manchego"
    assert estado.contacto == "989515182"
    assert "productos o servicios" in respuesta
    assert "nombre de la persona" not in respuesta

    respuesta, estado = manejar_mensaje("ya te di mi nombre", estado)
    assert "John Manchego" in respuesta


# Prueba el comportamiento de test extrae nombre mayusculas mixtas antes telefono.
def test_extrae_nombre_mayusculas_mixtas_antes_telefono():
    estado = EstadoCotizacion()
    _, estado = manejar_mensaje("Necesito bebidas para un matrimonio de 50 personas el 4 de diciembre en Miraflores", estado)

    respuesta, estado = manejar_mensaje("JOhn manchego y mi numero es 989515182", estado)

    assert estado.nombre_cliente == "John Manchego"
    assert estado.contacto == "989515182"
    assert "nombre de la persona" not in respuesta


# Prueba el comportamiento de test cae a cotizacion productos si no calza paquete.
def test_cae_a_cotizacion_productos_si_no_calza_paquete():
    estado = EstadoCotizacion()
    respuesta, estado = manejar_mensaje(
        "Soy Luis Ramos, mi telefono es 999222333. Necesito cerveza, vino, gaseosas, hielo y bartender premium para una reunion de 100 personas el 25 de octubre en Miraflores",
        estado,
    )
    assert "productos disponibles" in respuesta
    assert estado.opcion_recomendada["origen"] == "products"

    respuesta, estado = manejar_mensaje("Cuanto cuesta?", estado)
    assert "sin generar cotizacion" in respuesta
    assert estado.cotizacion is None

    respuesta, estado = manejar_mensaje("genera la cotizacion", estado)
    assert "Cotizacion por productos disponibles" in respuesta
    assert estado.cotizacion["total"] == 4035.6


# Prueba el comportamiento de test consulta precio producto no crea cotizacion.
def test_consulta_precio_producto_no_crea_cotizacion():
    estado = EstadoCotizacion()
    respuesta, estado = manejar_mensaje("Cuanto cuesta el vino?", estado)
    assert "Vino tinto reserva" in respuesta
    assert "sin generar cotizacion" in respuesta
    assert estado.cotizacion is None


# Prueba el comportamiento de test producto no soportado sugiere similar antes cotizar.
def test_producto_no_soportado_sugiere_similar_antes_cotizar():
    estado = EstadoCotizacion()
    respuesta, estado = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito whisky economico para un matrimonio de 34 personas el 25 de octubre en Miraflores",
        estado,
    )
    assert "no lo tengo en catalogo mock" in respuesta
    assert "vino" in respuesta
    assert "cerveza" in respuesta
    assert estado.opcion_recomendada is None
    assert estado.productos_solicitados_no_soportados == ["whisky"]

    respuesta, estado = manejar_mensaje("entonces reemplazalo por vino", estado)
    assert estado.productos_solicitados_no_soportados == []
    assert estado.productos_solicitados == ["vino"]
    assert "productos disponibles" in respuesta


# Prueba el comportamiento de test aceptar alternativa mantiene hilo sin derivacion.
def test_aceptar_alternativa_mantiene_hilo_sin_derivacion():
    estado = EstadoCotizacion()
    respuesta, estado = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito gaseosas cerveza pisco ron para un matrimonio de 45 personas el 23 de diciembre en Miraflores",
        estado,
    )
    assert "pisco" in respuesta
    assert "vino" in respuesta
    assert estado.productos_solicitados_no_soportados == ["pisco"]

    respuesta, estado = manejar_mensaje("si dame vino", estado)
    assert estado.productos_solicitados_no_soportados == []
    assert "WhatsApp" not in respuesta
    assert "productos disponibles" in respuesta
    assert estado.opcion_recomendada["origen"] == "products"


# Prueba el comportamiento de test producto sin stock sugiere alternativas misma familia.
def test_producto_sin_stock_sugiere_alternativas_misma_familia():
    estado = EstadoCotizacion()
    respuesta, estado = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito vino para un matrimonio de 100 personas el 15 de noviembre en Miraflores",
        estado,
    )
    assert "Stock insuficiente" in respuesta or "stock" in respuesta
    assert "Ron añejo botella" in respuesta
    assert "Cerveza artesanal lata" in respuesta
    assert estado.opcion_recomendada is None


# Prueba el comportamiento de test fecha parcial indica faltante y luego completa.
def test_fecha_parcial_indica_faltante_y_luego_completa():
    estado = EstadoCotizacion()
    respuesta, estado = manejar_mensaje(
        "es matrimonio, 34 personas, para diciembre, miraflores, para John Manchego, 989515182 que sea economico",
        estado,
    )
    assert "falta el dia" in respuesta
    assert estado.fecha_parcial["mes"] == 12
    assert estado.fecha_evento is None

    respuesta, estado = manejar_mensaje("para el 4 de diciembre", estado)
    assert estado.fecha_evento == "2026-12-04"
    assert "fecha" not in estado.campos_faltantes


# Prueba el comportamiento de test fecha parcial solo dia indica mes faltante.
def test_fecha_parcial_solo_dia_indica_mes_faltante():
    estado = EstadoCotizacion()
    respuesta, estado = manejar_mensaje("para el 4", estado)
    assert "falta el mes" in respuesta
    assert estado.fecha_parcial["dia"] == 4


# Prueba el comportamiento de test numero asistentes no se usa como dia evento.
def test_numero_asistentes_no_se_usa_como_dia_evento():
    estado = EstadoCotizacion()
    _, estado = manejar_mensaje("necesito cotizar un matrimonio", estado)
    _, estado = manejar_mensaje("30 personas", estado)
    assert estado.asistentes == 30
    assert estado.fecha_parcial["dia"] is None
    assert estado.fecha_evento is None

    respuesta, estado = manejar_mensaje("sera en septiembre y en miraflores", estado)
    assert estado.fecha_evento is None
    assert estado.fecha_parcial["mes"] == 9
    assert "falta el dia" in respuesta


# Prueba el comportamiento de test asistentes en seguimiento no activa derivacion.
def test_asistentes_en_seguimiento_no_activa_derivacion():
    estado = EstadoCotizacion()
    _, estado = manejar_mensaje("es un matrimonio", estado)
    respuesta, estado = manejar_mensaje("es para 20 personas", estado)

    assert estado.asistentes == 20
    assert estado.intencion != "human_handoff"
    assert estado.etapa == "recoleccion"
    assert estado.derivacion_confirmada is False
    assert "WhatsApp" not in respuesta


# Prueba el comportamiento de test numero suelto llena asistentes si agente los pidio.
def test_numero_suelto_llena_asistentes_si_agente_los_pidio():
    estado = EstadoCotizacion()
    respuesta, estado = manejar_mensaje(
        "Quiero una cotizacion para un evento de matrimonio, para el 24 de febrero del 2027 en Miraflores, mi nombre es John Manchego y mi numero de celular es 989515182",
        estado,
    )
    assert estado.fecha_evento == "2027-02-24"
    assert "cantidad de asistentes" in respuesta

    respuesta, estado = manejar_mensaje("80", estado)

    assert estado.asistentes == 80
    assert "cantidad de asistentes" not in estado.campos_faltantes
    assert "productos" in respuesta.lower()


# Prueba el comportamiento de test productos faltantes lista catalogo para elegir.
def test_productos_faltantes_lista_catalogo_para_elegir():
    estado = EstadoCotizacion()
    respuesta, estado = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Es un matrimonio para 45 personas el 23 de diciembre en Miraflores",
        estado,
    )

    assert "Productos disponibles para elegir" in respuesta
    assert "Cerveza artesanal lata" in respuesta
    assert "Vino tinto reserva" in respuesta
    assert "Gaseosa 1.5L" in respuesta
    assert "Pack celebracion esencial" in respuesta
    assert estado.opcion_recomendada is None


# Prueba el comportamiento de test usuario puede revisar y modificar productos antes cotizar.
def test_usuario_puede_revisar_y_modificar_productos_antes_cotizar():
    estado = EstadoCotizacion()
    _, estado = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Es un matrimonio para 45 personas el 23 de diciembre en Miraflores",
        estado,
    )
    _, estado = manejar_mensaje("quiero cerveza, vino y hielo", estado)
    assert estado.opcion_recomendada is not None

    respuesta, estado = manejar_mensaje("quitar vino", estado)
    assert "vino" not in estado.productos_solicitados
    assert estado.cotizacion is None
    assert estado.opcion_recomendada is None
    assert "Productos/servicios: cerveza, hielo" in respuesta

    respuesta, estado = manejar_mensaje("cambiar cerveza por agua", estado)
    assert "cerveza" not in estado.productos_solicitados
    assert "agua" in estado.productos_solicitados
    assert "Productos/servicios: hielo, agua" in respuesta


# Prueba el comportamiento de test cambio implicito reemplaza producto sin stock.
def test_cambio_implicito_reemplaza_producto_sin_stock():
    estado = EstadoCotizacion()
    _, estado = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito cerveza vino agua y hielo para un matrimonio de 100 personas el 25 de octubre en Miraflores",
        estado,
    )
    assert "agua" in estado.productos_sin_stock

    respuesta, estado = manejar_mensaje("cambialo por gaseosa", estado)

    assert "agua" not in estado.productos_solicitados
    assert "gaseosa" in estado.productos_solicitados
    assert estado.productos_sin_stock == []
    assert "Productos considerados" in respuesta


# Prueba el comportamiento de test puede retomar conversacion previa por identidad.
def test_puede_retomar_conversacion_previa_por_identidad(monkeypatch, tmp_path):
    monkeypatch.setattr(session_store, "STORE_PATH", tmp_path / "mock_session_memory.json")
    monkeypatch.setattr(redis_session_store, "REDIS_MOCK_PATH", tmp_path / "mock_redis_session.json")
    original = EstadoCotizacion()
    _, original = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito cerveza y vino para un matrimonio de 45 personas el 23 de diciembre en Miraflores",
        original,
    )
    assert original.nombre_cliente == "John Manchego"
    assert original.contacto == "989515182"
    assert original.productos_solicitados == ["cerveza", "vino"]

    new_session = EstadoCotizacion()
    respuesta, retomado = manejar_mensaje(
        "quiero retomar mi cotizacion anterior, soy John Manchego mi numero es 989515182",
        new_session,
    )

    assert "retome la ultima cotizacion" in respuesta
    assert retomado.id_sesion == new_session.id_sesion
    assert retomado.nombre_cliente == "John Manchego"
    assert retomado.contacto == "989515182"
    assert retomado.tipo_evento == "matrimonio"
    assert retomado.asistentes == 45
    assert retomado.fecha_evento == "2026-12-23"
    assert retomado.distrito == "Miraflores"
    assert retomado.productos_solicitados == ["cerveza", "vino"]

    active_session = redis_session_store.cargar_sesion_activa(new_session.id_sesion)
    assert active_session is not None
    assert active_session.id_sesion == new_session.id_sesion
    assert active_session.nombre_cliente == "John Manchego"
    assert active_session.productos_solicitados == ["cerveza", "vino"]


# Prueba el comportamiento de test contacto coincidente pregunta antes sobrescribir cotizacion.
def test_contacto_coincidente_pregunta_antes_sobrescribir_cotizacion(monkeypatch, tmp_path):
    monkeypatch.setattr(session_store, "STORE_PATH", tmp_path / "mock_session_memory.json")
    monkeypatch.setattr(redis_session_store, "REDIS_MOCK_PATH", tmp_path / "mock_redis_session.json")
    previo = EstadoCotizacion()
    _, previo = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito cerveza y vino para un matrimonio de 45 personas el 23 de diciembre en Miraflores",
        previo,
    )

    current = EstadoCotizacion()
    _, current = manejar_mensaje("necesito cotizar un matrimonio", current)
    _, current = manejar_mensaje("20 personas el 23 de diciembre en Miraflores", current)
    respuesta, current = manejar_mensaje("John Manchego numero 989515182", current)

    assert "Encontre una cotizacion previa" in respuesta
    assert "Datos que acabas de dar" in respuesta
    assert "Cotizacion previa encontrada" in respuesta
    assert "Productos/servicios: cerveza, vino" in respuesta
    assert current.estado_previo_pendiente is not None

    respuesta, retomado = manejar_mensaje("retomar la anterior", current)
    assert "retome la cotizacion previa" in respuesta
    assert retomado.id_sesion == current.id_sesion
    assert retomado.asistentes == 45
    assert retomado.productos_solicitados == ["cerveza", "vino"]


# Prueba que una intencion de retomar sesion previa pida contacto para buscar memoria.
def test_pide_telefono_para_buscar_datos_de_otra_sesion():
    estado = EstadoCotizacion()

    respuesta, estado = manejar_mensaje("pero ya te di mis datos en otra session", estado)

    assert estado.intencion == "resume_previous"
    assert estado.campos_faltantes == ["contacto"]
    assert "telefono o correo" in respuesta
    assert "tipo de evento" not in respuesta
    assert "cantidad de asistentes" not in respuesta


# Prueba que la frase de continuar conversacion anterior pida contacto.
def test_quiere_seguir_con_conversacion_anterior_pide_contacto():
    estado = EstadoCotizacion()

    respuesta, estado = manejar_mensaje("Hola quiero seguir con la conversacion que tuvimos", estado)

    assert estado.intencion == "resume_previous"
    assert estado.campos_faltantes == ["contacto"]
    assert "telefono o correo" in respuesta
    assert "tipo de evento" not in respuesta
    assert "cantidad de asistentes" not in respuesta


# Prueba que retomar conversacion prevalece aunque el agente sugiera revisar pedido.
def test_retomar_conversacion_no_se_convierte_en_revision_pedido(monkeypatch):
    monkeypatch.setattr(
        extraction_tools,
        "_extraer_campos_con_agente",
        lambda message, estado: {"intent_override": "review_order"},
    )
    estado = EstadoCotizacion()

    respuesta, estado = manejar_mensaje("Hola quiero seguir con la conversacion que tuvimos", estado)

    assert estado.intencion == "resume_previous"
    assert estado.etapa == "memoria_previa"
    assert "telefono o correo" in respuesta
    assert "producto o servicio" not in respuesta


# Prueba que datos anteriores y seguir conversacion pida telefono/correo.
def test_datos_anteriores_y_seguir_conversacion_pide_contacto():
    estado = EstadoCotizacion()

    respuesta, estado = manejar_mensaje("Hola ya te deje datos anteriormente quiero seguir con mi conversacion", estado)

    assert estado.intencion == "resume_previous"
    assert estado.etapa == "memoria_previa"
    assert estado.campos_faltantes == ["contacto"]
    assert "telefono o correo" in respuesta
    assert "tipo de evento" not in respuesta
    assert "cantidad de asistentes" not in respuesta


# Prueba que una frase natural de sesion previa pide contacto y no reinicia recoleccion.
def test_ya_tuve_session_contigo_pide_contacto():
    estado = EstadoCotizacion()

    respuesta, estado = manejar_mensaje("esta bien, yo ya tuve una session contigo y quiero continuarla", estado)

    assert estado.intencion == "resume_previous"
    assert estado.etapa == "memoria_previa"
    assert estado.campos_faltantes == ["contacto"]
    assert "telefono o correo" in respuesta
    assert "tipo de evento" not in respuesta
    assert "cantidad de asistentes" not in respuesta


# Prueba que una variante natural de conversacion previa no caiga a recoleccion normal.
def test_ya_tuvimos_session_y_di_todos_mis_datos_pide_contacto():
    estado = EstadoCotizacion()

    respuesta, estado = manejar_mensaje("ya tuvimos una session te di todos mis datos", estado)

    assert estado.intencion == "resume_previous"
    assert estado.etapa == "memoria_previa"
    assert estado.campos_faltantes == ["contacto"]
    assert "telefono o correo" in respuesta
    assert "cantidad de asistentes" not in respuesta
    assert "fecha y distrito" not in respuesta


# Prueba que un saludo con typo sobre datos anteriores no se trate como saludo simple.
def test_hola_datos_enteriormente_pide_contacto_para_memoria():
    estado = EstadoCotizacion()

    respuesta, estado = manejar_mensaje("Hola ya te dire mis datos enteriormente", estado)

    assert estado.intencion == "resume_previous"
    assert estado.etapa == "memoria_previa"
    assert estado.campos_faltantes == ["contacto"]
    assert "telefono o correo" in respuesta
    assert "tipo de evento" not in respuesta
    assert "cantidad de asistentes" not in respuesta


# Prueba que reclamar datos ya dados en otra sesion mantiene la busqueda de memoria.
def test_ya_te_di_esos_datos_pide_contacto_para_memoria():
    estado = EstadoCotizacion()

    respuesta, estado = manejar_mensaje("te estoy diciendo que ya te di esos datos", estado)

    assert estado.intencion == "resume_previous"
    assert estado.etapa == "memoria_previa"
    assert estado.campos_faltantes == ["contacto"]
    assert "telefono o correo" in respuesta
    assert "tipo de evento" not in respuesta
    assert "cantidad de asistentes" not in respuesta


# Prueba que el guardrail corrija una mala decision del agente decisor.
def test_guardrail_decision_preserva_recuperacion_memoria(monkeypatch):
    monkeypatch.setattr(
        workflow,
        "decidir_siguiente_accion_con_agente",
        lambda mensaje_usuario, estado: "pedir_campos_faltantes",
    )
    estado = EstadoCotizacion()

    respuesta, estado = manejar_mensaje("esta bien, yo ya tuve una session contigo y quiero continuarla", estado)

    assert estado.intencion == "resume_previous"
    assert estado.etapa == "memoria_previa"
    assert estado.campos_faltantes == ["contacto"]
    assert "telefono o correo" in respuesta
    assert "tipo de evento" not in respuesta
    assert "cantidad de asistentes" not in respuesta


# Prueba que si el LLM decisor falla, el guardrail posterior igual mantiene la intencion correcta.
def test_fallback_si_llm_decisor_falla_en_recuperacion_memoria(monkeypatch):
    monkeypatch.setattr(
        workflow,
        "decidir_siguiente_accion_con_agente",
        lambda mensaje_usuario, estado: None,
    )
    estado = EstadoCotizacion()

    respuesta, estado = manejar_mensaje("ya tuvimos una session te di todos mis datos", estado)

    assert estado.intencion == "resume_previous"
    assert estado.etapa == "memoria_previa"
    assert estado.campos_faltantes == ["contacto"]
    assert "telefono o correo" in respuesta
    assert "cantidad de asistentes" not in respuesta


# Prueba que pedir otra cotizacion limpie el contexto anterior.
def test_otra_cotizacion_con_otro_numero_inicia_contexto_nuevo():
    estado = EstadoCotizacion()
    _, estado = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito cerveza, agua y hielo para un matrimonio de 49 personas el 3 de marzo de 2027 en Miraflores",
        estado,
    )
    assert estado.nombre_cliente == "John Manchego"
    assert estado.contacto == "989515182"
    assert estado.productos_solicitados == ["cerveza", "agua", "hielo"]

    respuesta, estado = manejar_mensaje("ahora quiero hacer otra cotizacion con otro numero", estado)

    assert estado.nombre_cliente is None
    assert estado.contacto is None
    assert estado.tipo_evento is None
    assert estado.asistentes is None
    assert estado.fecha_evento is None
    assert estado.distrito is None
    assert estado.productos_solicitados == []
    assert estado.opcion_recomendada is None
    assert estado.cotizacion is None
    assert "tipo de evento" in respuesta
    assert "cantidad de asistentes" in respuesta
    assert "cerveza" not in respuesta.split("Memoria temporal")[0]


# Prueba que el telefono posterior a una solicitud de recuperar memoria se usa para buscar memoria.
def test_contacto_despues_de_retomar_busca_memoria_y_si_no_existe_inicia_nueva(monkeypatch, tmp_path):
    monkeypatch.setattr(session_store, "STORE_PATH", tmp_path / "mock_session_memory.json")
    monkeypatch.setattr(redis_session_store, "REDIS_MOCK_PATH", tmp_path / "mock_redis_session.json")
    estado = EstadoCotizacion()

    respuesta, estado = manejar_mensaje("tuve una sesion anterior donde te di ya mis datos", estado)
    assert estado.intencion == "resume_previous"
    assert "telefono o correo" in respuesta

    respuesta, estado = manejar_mensaje("989515182", estado)

    assert estado.intencion == "resume_previous"
    assert estado.contacto == "989515182"
    assert "No encontre una cotizacion anterior" in respuesta
    assert "Empecemos una nueva cotizacion" in respuesta
    assert "productos o servicios" not in respuesta.split("Memoria temporal")[0]


# Prueba que una busqueda de memoria sin datos no se guarde como cotizacion previa.
def test_busqueda_sin_memoria_no_crea_cotizacion_previa_falsa(monkeypatch, tmp_path):
    monkeypatch.setattr(session_store, "STORE_PATH", tmp_path / "mock_session_memory.json")
    monkeypatch.setattr(redis_session_store, "REDIS_MOCK_PATH", tmp_path / "mock_redis_session.json")
    estado = EstadoCotizacion()

    _, estado = manejar_mensaje("tuve una sesion anterior donde te di ya mis datos", estado)
    respuesta, estado = manejar_mensaje("989515182", estado)
    assert "No encontre una cotizacion anterior" in respuesta

    new_state = EstadoCotizacion()
    _, new_state = manejar_mensaje("tuve una sesion anterior donde te di ya mis datos", new_state)
    respuesta, new_state = manejar_mensaje("989515182", new_state)

    assert "No encontre una cotizacion anterior" in respuesta
    assert "retome la ultima cotizacion" not in respuesta


# Prueba que una memoria sin cotizante ni productos no se trate como cotizacion anterior util.
def test_memoria_incompleta_sin_nombre_no_se_retoma_como_cotizacion(monkeypatch, tmp_path):
    monkeypatch.setattr(session_store, "STORE_PATH", tmp_path / "mock_session_memory.json")
    monkeypatch.setattr(redis_session_store, "REDIS_MOCK_PATH", tmp_path / "mock_redis_session.json")
    previo = EstadoCotizacion(contacto="989515182", tipo_evento="matrimonio", asistentes=49, fecha_evento="2027-03-03", distrito="Miraflores")
    session_store.guardar_estado_conversacion(previo)

    estado = EstadoCotizacion()
    _, estado = manejar_mensaje("tuve una sesion anterior donde te di ya mis datos", estado)
    respuesta, estado = manejar_mensaje("989515182", estado)

    assert "No encontre una cotizacion anterior" in respuesta
    assert "retome la ultima cotizacion" not in respuesta


# Prueba que el nombre se capture cuando el flujo esta esperando cotizante.
def test_nombre_contextual_se_captura_cuando_falta_cotizante():
    estado = EstadoCotizacion()
    _, estado = manejar_mensaje("matrimonio para 49 personas el 3 de marzo de 2027 en Miraflores mi telefono es 989515182", estado)

    respuesta, estado = manejar_mensaje("es para John Manchego", estado)

    assert estado.nombre_cliente == "John Manchego"
    assert "nombre de la persona que cotiza" not in respuesta.split("Memoria temporal")[0]


# Prueba el comportamiento de test sesion activa se guarda por session id.
def test_sesion_activa_se_guarda_por_session_id(monkeypatch, tmp_path):
    monkeypatch.setattr(redis_session_store, "REDIS_MOCK_PATH", tmp_path / "mock_redis_session.json")
    estado = EstadoCotizacion()
    id_sesion = estado.id_sesion

    _, estado = manejar_mensaje(
        "Soy John Manchego, mi telefono es 989515182. Necesito cerveza para un matrimonio de 30 personas el 25 de octubre en Miraflores",
        estado,
    )

    restored = redis_session_store.cargar_sesion_activa(id_sesion)
    assert restored is not None
    assert restored.id_sesion == id_sesion
    assert restored.nombre_cliente == "John Manchego"
    assert restored.contacto == "989515182"
    assert restored.tipo_evento == "matrimonio"
    assert restored.asistentes == 30
    assert restored.productos_solicitados == ["cerveza"]

    another_state = EstadoCotizacion()
    _, another_state = manejar_mensaje(
        "Soy Ana Torres, mi telefono es 999111222. Necesito vino para un matrimonio de 20 personas el 25 de octubre en Miraflores",
        another_state,
    )
    assert redis_session_store.cargar_sesion_activa(id_sesion) is None
    assert redis_session_store.cargar_sesion_activa(another_state.id_sesion) is not None

    redis_session_store.reiniciar_sesion_activa(another_state.id_sesion)
    assert redis_session_store.cargar_sesion_activa(another_state.id_sesion) is None
