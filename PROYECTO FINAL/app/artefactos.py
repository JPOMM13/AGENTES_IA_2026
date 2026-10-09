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


# ARTEFACTO MULTIMODAL: genera o reutiliza la imagen visual asociada a la cotizacion final.
def generar_artefacto_visual_cotizacion(estado: Any) -> str:
    """Genera la imagen visual de la cotizacion y devuelve su ruta."""
    if not estado.cotizacion:
        return ""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    # PRUEBAS DE FLUJO: SE COMENTA LA LLAMADA A OPENAI IMAGES PARA NO CONSUMIR API.
    # AL ESTAR COMENTADO, LA APP USA EL SVG MOCK LOCAL GENERADO MAS ABAJO.
    # image_path = generar_imagen_multimodal_evento(estado)
    # if image_path:
    #     return image_path

    # MOCK: RESPALDO LOCAL CUANDO NO HAY PROVEEDOR MULTIMODAL CONFIGURADO.
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


# MULTIMODAL/IMAGEN: punto donde se llamaria a la API de imagen; ahora puede usar mock si esta comentada.
def generar_imagen_multimodal_evento(estado: Any) -> str:
    """Llama al proveedor multimodal configurado y guarda un PNG del evento."""
    estado.registrar_log("generar_imagen_multimodal_evento", {"mensaje": "IMAGEN MOCK NO GENERADA"})
    return ""

    # CODIGO DESACTIVADO PARA PRUEBAS: DESCOMENTAR ESTE BLOQUE PARA VOLVER A CONSUMIR OPENAI IMAGES.
    # config = obtener_configuracion_generacion_imagen()
    # if not config.listo:
    #     estado.registrar_log(
    #         "generate_multimodal_event_image_skipped",
    #         {"reason": "IMAGE_GENERATION_ENABLED apagado o API key no configurada"},
    #     )
    #     return ""
    #
    # prompt = construir_prompt_imagen_evento(estado)
    # quote_id = estado.cotizacion.get("quote_id", "cotizacion")
    # filename = f"{nombre_archivo_seguro(quote_id)}_{nombre_archivo_seguro(estado.id_sesion[:8])}.png"
    # path = ARTIFACT_DIR / filename
    #
    # try:
    #     # MOCK: EN ESTA POC SOLO SE ENVIA EL PROMPT A OPENAI IMAGES.
    #     # EN PRODUCCION EL PROMPT Y LA IMAGEN GENERADA PUEDEN AUDITARSE EN STORAGE/POSTGRES.
    #     carga = {
    #         "model": config.model,
    #         "prompt": prompt,
    #         "n": 1,
    #         "size": config.size,
    #         "quality": config.quality,
    #     }
    #     request = Request(
    #         config.url_imagen,
    #         data=json.dumps(carga).encode("utf-8"),
    #         headers={
    #             "Authorization": f"Bearer {config.clave_api}",
    #             "Content-Type": "application/json",
    #         },
    #         method="POST",
    #     )
    #     with urlopen(request, timeout=config.segundos_timeout) as respuesta:
    #         response_data = json.loads(respuesta.read().decode("utf-8"))
    #
    #     b64_data = response_data["data"][0].get("b64_json")
    #     if not b64_data:
    #         estado.registrar_log("generate_multimodal_event_image_empty", {"proveedor": config.proveedor})
    #         return ""
    #
    #     path.write_bytes(base64.b64decode(b64_data))
    #     estado.registrar_log("generar_imagen_multimodal_evento", {"path": str(path), "proveedor": config.proveedor, "model": config.model})
    #     return str(path)
    # except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
    #     estado.registrar_log("generate_multimodal_event_image_error", {"error": str(exc), "proveedor": config.proveedor})
    #     return ""


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


# IMAGEN MOCK: construye SVG local cuando no se usa API multimodal real.
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


# ARTEFACTO VISUAL: renderiza etiquetas de productos dentro del SVG mock.
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
