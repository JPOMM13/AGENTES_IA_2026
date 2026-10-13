from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.configuracion_llm import obtener_configuracion_generacion_imagen


ARTIFACT_DIR = Path(__file__).resolve().parent / "data" / "generated"
UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "uploads"
PRODUCT_REF_DIR = Path(__file__).resolve().parent / "data" / "assets" / "productos"
MAX_BYTES_FOTO = 8 * 1024 * 1024
MAX_REFERENCIAS = 6  # la API de edicion acepta hasta 16 imagenes; con la foto + 6 referencias alcanza y no se encarece


# FOTO DEL LOCAL: valida tipo por cabecera (no por extension) y guarda por sesion.
def guardar_foto_local(id_sesion: str, datos: bytes, nombre: str = "local.jpg") -> str:
    if len(datos) > MAX_BYTES_FOTO:
        raise ValueError("La foto supera el maximo de 8 MB.")
    if datos[:3] == b"\xff\xd8\xff":
        extension = "jpg"
    elif datos[:8] == b"\x89PNG\r\n\x1a\n":
        extension = "png"
    elif datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        extension = "webp"
    else:
        raise ValueError("Formato no soportado: usa jpg, png o webp.")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ruta = UPLOAD_DIR / f"local_{nombre_archivo_seguro(id_sesion[:8])}.{extension}"
    ruta.write_bytes(datos)
    return str(ruta)


def ruta_imagen_publica(nombre: str) -> Path | None:
    """Resuelve un nombre de archivo (sin rutas) dentro de las carpetas publicas de imagenes."""
    seguro = Path(nombre).name
    for carpeta in (ARTIFACT_DIR, UPLOAD_DIR, PRODUCT_REF_DIR):
        candidata = carpeta / seguro
        if candidata.is_file():
            return candidata
    return None


# REFERENCIAS DE PRODUCTOS: una imagen por categoria/paquete en assets/productos (la tabla jpomm_paquetes ya tiene
# columna imagen; para productos sueltos se usa la categoria). Se usan como imagenes de referencia en la edicion.
def imagenes_referencia_productos(estado: Any) -> list[Path]:
    nombres: list[str] = []
    opcion = estado.opcion_recomendada or {}
    if opcion.get("id", "").startswith("PKG") or "bar" in str(opcion.get("name", "")).lower():
        nombres.append("bar_movil")
    for producto in nombres_productos_cotizacion(estado):
        clave = normalizar_nombre_producto(producto)
        for categoria in ("cerveza", "vino", "ron", "gaseosa", "agua", "hielo", "bartenders"):
            if categoria.rstrip("s") in clave and categoria not in nombres:
                nombres.append(categoria)
    rutas = [PRODUCT_REF_DIR / f"{n}.png" for n in nombres]
    return [r for r in rutas if r.is_file()][:MAX_REFERENCIAS]


# PROMPT DE COMPOSICION: la foto del cliente es la escena base; las referencias son los productos cotizados.
def construir_prompt_composicion(estado: Any, referencias: list[Path]) -> str:
    productos = ", ".join(p.stem.replace("_", " ") for p in referencias) or "los productos cotizados"
    tipo_evento = estado.tipo_evento or "evento social"
    asistentes = estado.asistentes or "varias"
    return (
        "La primera imagen es la foto real del local del cliente. Recrea exactamente ese mismo espacio (misma "
        "arquitectura, perspectiva e iluminacion) ya montado para el evento, integrando de forma realista los "
        f"productos de las imagenes de referencia siguientes: {productos}. Tipo de evento: {tipo_evento}, "
        f"para {asistentes} personas. Mesas y decoracion coherentes con el evento; personas de fondo sin rostros "
        "protagonistas si corresponde. Fotografia realista, horizontal. Sin texto, precios, logos ni etiquetas."
    )


# COMPOSICION MULTIMODAL: foto del local + referencias de productos -> imagen final (OpenAI Images edit).
def componer_imagen_sobre_foto(estado: Any, config: Any, path: Path) -> str:
    foto = Path(estado.foto_local or "")
    referencias = imagenes_referencia_productos(estado)
    if not foto.is_file():
        return ""
    from openai import OpenAI

    cliente = OpenAI(api_key=config.clave_api)
    archivos = [open(foto, "rb")] + [open(r, "rb") for r in referencias]
    try:
        respuesta = cliente.images.edit(
            model=config.model,
            image=archivos,
            prompt=construir_prompt_composicion(estado, referencias),
            n=1,
            size=config.size,
            quality=config.quality,
        )
    finally:
        for archivo in archivos:
            archivo.close()
    b64_data = respuesta.data[0].b64_json
    if not b64_data:
        return ""
    path.write_bytes(base64.b64decode(b64_data))
    estado.registrar_log(
        "componer_imagen_sobre_foto",
        {"path": str(path), "foto": str(foto), "referencias": [r.name for r in referencias], "model": config.model},
    )
    return str(path)


# SSL: en macOS el Python de python.org no trae los certificados raiz del sistema y urllib falla con
# CERTIFICATE_VERIFY_FAILED; se usa el bundle de certifi si esta instalado (misma solucion que app/llm.py).
def contexto_ssl_imagen():
    import ssl

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


# ARTEFACTO MULTIMODAL: genera o reutiliza la imagen visual asociada a la cotizacion final.
def generar_artefacto_visual_cotizacion(estado: Any) -> str:
    """Genera la imagen visual de la cotizacion y devuelve su ruta."""
    if not estado.cotizacion:
        return ""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    # IMAGEN MULTIMODAL: solo cuando IMAGE_GENERATION_ENABLED=true y hay clave (config.listo); si esta apagado, si la
    # API falla o tarda mas que IMAGE_TIMEOUT_SECONDS, se usa el SVG local. Asi los tests y los evals nunca consumen API.
    image_path = generar_imagen_multimodal_evento(estado)
    if image_path:
        return image_path

    # RESPALDO LOCAL CUANDO NO HAY PROVEEDOR MULTIMODAL CONFIGURADO.
    # EN PRODUCCION ESTO DEBERIA SER UNA IMAGEN GENERADA POR EL PROVEEDOR DE IA O UN ASSET GUARDADO EN STORAGE.
    quote_id = estado.cotizacion.get("quote_id", "cotizacion")
    filename = f"{nombre_archivo_seguro(quote_id)}_{nombre_archivo_seguro(estado.id_sesion[:8])}.svg"
    path = ARTIFACT_DIR / filename
    path.write_text(construir_svg_cotizacion(estado), encoding="utf-8")
    return str(path)


# ARTEFACTO MULTIMODAL: regenera imagen solo si la cotizacion cambia o no existe artefacto.
def refrescar_artefacto_visual_si_es_necesario(estado: Any) -> str:
    """Regenera un SVG viejo como PNG cuando la imagen multimodal ya esta activa."""
    if not estado.cotizacion:
        return ""
    current_path = Path(estado.imagen_artefacto_cotizacion or "")
    config = obtener_configuracion_generacion_imagen()
    if current_path.suffix.lower() == ".png" and current_path.exists():
        return str(current_path)
    if not config.listo:
        return str(current_path) if estado.imagen_artefacto_cotizacion else ""

    image_path = generar_imagen_multimodal_evento(estado)
    if image_path:
        estado.imagen_artefacto_cotizacion = image_path
    return estado.imagen_artefacto_cotizacion or ""


# MULTIMODAL/IMAGEN: punto donde se llamaria a la API de imagen; ahora puede usar respaldo local si esta comentada.
def generar_imagen_multimodal_evento(estado: Any) -> str:
    """Llama al proveedor multimodal configurado y guarda un PNG del evento."""
    config = obtener_configuracion_generacion_imagen()
    if not config.listo:
        estado.registrar_log(
            "generar_imagen_multimodal_evento_omitida",
            {"motivo": "IMAGE_GENERATION_ENABLED apagado o API key no configurada"},
        )
        return ""

    prompt = construir_prompt_imagen_evento(estado)
    quote_id = estado.cotizacion.get("quote_id", "cotizacion")
    filename = f"{nombre_archivo_seguro(quote_id)}_{nombre_archivo_seguro(estado.id_sesion[:8])}.png"
    path = ARTIFACT_DIR / filename

    # 1) Si el cliente subio la foto de su local, la imagen final se compone sobre ella con los productos cotizados.
    if estado.foto_local:
        try:
            ruta_compuesta = componer_imagen_sobre_foto(estado, config, path)
            if ruta_compuesta:
                return ruta_compuesta
        except Exception as exc:  # noqa: BLE001 - degrada a la generacion por prompt y luego al SVG.
            estado.registrar_log("componer_imagen_sobre_foto_error", {"error": str(exc)[:300]})

    try:
        # 2) MULTIMODAL por prompt: envia el prompt a OpenAI Images (gpt-image-1 devuelve b64_json). El prompt se
        # construye solo con datos validados de la cotizacion (sin texto libre del usuario), asi no hay inyeccion.
        carga = {
            "model": config.model,
            "prompt": prompt,
            "n": 1,
            "size": config.size,
            "quality": config.quality,
        }
        request = Request(
            config.url_imagen,
            data=json.dumps(carga).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {config.clave_api}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=config.segundos_timeout, context=contexto_ssl_imagen()) as respuesta:
            response_data = json.loads(respuesta.read().decode("utf-8"))

        b64_data = response_data["data"][0].get("b64_json")
        if not b64_data:
            estado.registrar_log("generar_imagen_multimodal_evento_vacia", {"proveedor": config.proveedor})
            return ""

        path.write_bytes(base64.b64decode(b64_data))
        estado.registrar_log("generar_imagen_multimodal_evento", {"path": str(path), "proveedor": config.proveedor, "model": config.model})
        return str(path)
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError, OSError) as exc:
        # FAIL-SAFE: la imagen es un extra; cualquier error degrada al SVG local y queda en la traza.
        detalle = exc.read().decode("utf-8", "ignore")[:300] if isinstance(exc, HTTPError) else str(exc)[:300]
        estado.registrar_log("generar_imagen_multimodal_evento_error", {"error": detalle, "proveedor": config.proveedor})
        return ""


# PROMPT MULTIMODAL: describe evento, productos y servicios para generar una imagen coherente.
def construir_prompt_imagen_evento(estado: Any) -> str:
    """Construye un prompt visual realista basado solo en la cotizacion validada."""
    tipo_evento = estado.tipo_evento or "evento social"
    asistentes = estado.asistentes or "varias"
    distrito = estado.distrito or "Lima"
    fecha_evento = estado.fecha_evento or "fecha por confirmar"
    products = nombres_productos_cotizacion(estado)
    visual_elements = describir_productos_para_imagen(products)
    services = describir_servicios_para_imagen(estado)

    return (
        "Genera una imagen fotografica realista, horizontal y profesional de un evento cotizado. "
        f"Tipo de evento: {tipo_evento}. Cantidad de asistentes: {asistentes}. "
        f"Lugar referencial: {distrito}, Lima. Fecha referencial: {fecha_evento}. "
        f"Debe verse como una escena real del evento, no como una tarjeta grafica ni una infografia. "
        f"Incluye de forma natural estos productos o servicios cotizados: {visual_elements}{services}. "
        "Muestra mesas, ambiente de recepcion, estacion de bebidas o barra si corresponde, iluminacion calida, "
        "personas conversando de fondo sin rostros protagonistas, decoracion coherente con el tipo de evento. "
        "No agregues texto, precios, logos, marcas, etiquetas, iconos, diagramas, screenshots ni elementos abstractos."
    )


# PROMPT MULTIMODAL: traduce productos cotizados a una descripcion visual para la imagen.
def describir_productos_para_imagen(products: list[str]) -> str:
    """Convierte productos cotizados en elementos visuales para el prompt."""
    if not products:
        return "productos de catering por confirmar"

    catalog = {
        "cerveza": "cervezas frias en botellas o latas sobre una barra",
        "vino": "botellas de vino y copas servidas",
        "ron": "botellas de ron en una estacion de licores",
        "gaseosa": "botellas de gaseosa en una mesa de bebidas",
        "agua": "botellas de agua mineral",
        "hielo": "cubetas con hielo para bebidas",
        "bar": "barra movil elegante para bebidas",
        "bartender": "bartender atendiendo discretamente la barra",
    }
    descriptions = []
    for product in products:
        normalized = normalizar_nombre_producto(product)
        descriptions.append(catalog.get(normalized, product))
    return ", ".join(descriptions[:8])


# PROMPT MULTIMODAL: agrega servicios cotizados al contexto visual del evento.
def describir_servicios_para_imagen(estado: Any) -> str:
    """Agrega servicios recomendados del paquete si existen en la cotizacion."""
    option = estado.opcion_recomendada or {}
    services = option.get("services") or []
    if not services:
        return ""
    visible_services = ", ".join(str(service) for service in services[:4])
    return f", ademas de servicios como {visible_services}"


# IMAGEN LOCAL: construye SVG local cuando no se usa API multimodal real.
def construir_svg_cotizacion(estado: Any) -> str:
    """Construye el SVG con datos del evento, productos y totales."""
    tipo_evento = html.escape(str(estado.tipo_evento or "evento"))
    distrito = html.escape(str(estado.distrito or "distrito pendiente"))
    fecha_evento = html.escape(str(estado.fecha_evento or "fecha pendiente"))
    asistentes = html.escape(str(estado.asistentes or "pendiente"))
    products = nombres_productos_cotizacion(estado)
    product_text = html.escape(", ".join(products[:5]) if products else "productos por confirmar")
    total = html.escape(f"{estado.cotizacion.get('currency', 'PEN')} {estado.cotizacion.get('total', 0):.2f}")
    title = html.escape((estado.opcion_recomendada or {}).get("name", "Cotizacion de evento"))
    product_chips = renderizar_chips_productos(products)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760" viewBox="0 0 1200 760">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#111827"/>
      <stop offset="55%" stop-color="#1f2937"/>
      <stop offset="100%" stop-color="#3f2f1f"/>
    </linearGradient>
    <linearGradient id="table" x1="0" x2="1">
      <stop offset="0%" stop-color="#f8fafc"/>
      <stop offset="100%" stop-color="#e5e7eb"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="760" fill="url(#bg)"/>
  <circle cx="160" cy="120" r="70" fill="#f59e0b" opacity="0.22"/>
  <circle cx="1030" cy="120" r="95" fill="#ef4444" opacity="0.16"/>
  <rect x="120" y="235" width="960" height="300" rx="18" fill="url(#table)" opacity="0.96"/>
  <rect x="170" y="280" width="860" height="42" rx="21" fill="#d1d5db"/>
  <circle cx="300" cy="382" r="42" fill="#7c2d12"/>
  <circle cx="440" cy="382" r="42" fill="#991b1b"/>
  <circle cx="580" cy="382" r="42" fill="#1d4ed8"/>
  <circle cx="720" cy="382" r="42" fill="#047857"/>
  <circle cx="860" cy="382" r="42" fill="#92400e"/>
  <rect x="210" y="465" width="780" height="22" rx="11" fill="#9ca3af"/>
  <texto x="90" y="86" fill="#ffffff" font-family="Arial, sans-serif" font-size="42" font-weight="700">{title}</texto>
  <texto x="90" y="136" fill="#e5e7eb" font-family="Arial, sans-serif" font-size="25">{tipo_evento} para {asistentes} personas</texto>
  <texto x="90" y="174" fill="#d1d5db" font-family="Arial, sans-serif" font-size="22">{distrito} · {fecha_evento}</texto>
  <texto x="90" y="620" fill="#ffffff" font-family="Arial, sans-serif" font-size="28" font-weight="700">Productos y servicios cotizados</texto>
  <texto x="90" y="660" fill="#e5e7eb" font-family="Arial, sans-serif" font-size="22">{product_text}</texto>
  {product_chips}
  <rect x="820" y="584" width="290" height="96" rx="18" fill="#ffffff" opacity="0.95"/>
  <texto x="850" y="624" fill="#374151" font-family="Arial, sans-serif" font-size="20">Total referencial</texto>
  <texto x="850" y="664" fill="#111827" font-family="Arial, sans-serif" font-size="34" font-weight="700">{total}</texto>
</svg>
"""


# ARTEFACTO VISUAL: obtiene productos cotizados para mostrarlos en imagen o resumen.
def nombres_productos_cotizacion(estado: Any) -> list[str]:
    """Obtiene nombres visibles desde detalles de cotizacion o productos solicitados."""
    if estado.cotizacion:
        names = []
        for item in estado.cotizacion.get("details", []):
            names.append(str(item.get("product_name") or item.get("concept") or "item"))
        if names:
            return names
    return list(estado.productos_solicitados)


# ARTEFACTO VISUAL: renderiza etiquetas de productos dentro del SVG local.
def renderizar_chips_productos(products: list[str]) -> str:
    """Dibuja chips dentro del SVG para los principales productos."""
    chips = []
    for index, product in enumerate(products[:4]):
        x = 90 + index * 175
        label = html.escape(product[:18])
        chips.append(
            f'<rect x="{x}" y="690" width="150" height="38" rx="19" fill="#f59e0b" opacity="0.92"/>'
            f'<texto x="{x + 18}" y="715" fill="#111827" font-family="Arial, sans-serif" font-size="16" font-weight="700">{label}</texto>'
        )
    return "\n  ".join(chips)


# ARTEFACTO VISUAL: normaliza nombres de archivo para guardar imagenes sin caracteres problematicos.
def nombre_archivo_seguro(value: str) -> str:
    """Normaliza texto para usarlo como nombre de archivo."""
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_") or "artifact"


# ARTEFACTO VISUAL: normaliza nombres de producto antes de pintarlos o describirlos.
def normalizar_nombre_producto(value: str) -> str:
    """Normaliza nombres para mapearlos a descripciones visuales."""
    value = value.lower().strip()
    replacements = {
        "cerveza artesanal lata": "cerveza",
        "vino tinto reserva": "vino",
        "ron anejo botella": "ron",
        "gaseosa 1.5l": "gaseosa",
        "agua mineral 625ml": "agua",
        "bolsa de hielo": "hielo",
        "bar movil premium": "bar",
        "bartender por evento": "bartender",
    }
    if value in replacements:
        return replacements[value]
    for key in ["cerveza", "vino", "ron", "gaseosa", "agua", "hielo", "bar", "bartender"]:
        if key in value:
            return key
    return value
