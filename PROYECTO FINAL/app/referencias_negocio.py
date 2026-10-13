from __future__ import annotations

import unicodedata
from functools import lru_cache

from app.data.datos_mock import CATALOG, COVERED_DISTRICTS, PRODUCT_CATEGORIES, PRODUCTS
from app.fuente_datos import usar_postgres_negocio
from app.repositorios_postgres.conexion import conexion_postgres


# REFERENCIAS DE NEGOCIO: entrega tipos de evento, distritos y productos desde la fuente configurada.
def obtener_tipos_evento_soportados() -> list[str]:
    """Obtiene tipos de evento activos desde PostgreSQL o desde datos locales si el modo es mock."""
    if usar_postgres_negocio():
        return _obtener_tipos_evento_postgres()
    tipos = {tipo for paquete in CATALOG for tipo in paquete.get("event_types", [])}
    tipos.update(tipo for producto in PRODUCTS for tipo in producto.get("event_types", []))
    return sorted(tipos)


# REFERENCIAS DE NEGOCIO: entrega aliases generados desde tipos reales para interpretar lenguaje natural.
def obtener_aliases_tipos_evento() -> dict[str, list[str]]:
    """Genera aliases de tipos de evento desde los tipos disponibles en negocio."""
    return {tipo: _generar_aliases_tipo_evento(tipo) for tipo in obtener_tipos_evento_soportados()}


# REFERENCIAS DE NEGOCIO: entrega distritos cubiertos desde la fuente de negocio.
def obtener_distritos_referencia() -> list[str]:
    """Obtiene distritos activos desde PostgreSQL o desde datos locales si el modo es mock."""
    if usar_postgres_negocio():
        return _obtener_distritos_postgres()
    return sorted(distrito.title() for distrito in COVERED_DISTRICTS)


# REFERENCIAS DE NEGOCIO: entrega productos y servicios reconocibles desde catalogo activo.
def obtener_aliases_productos() -> dict[str, list[str]]:
    """Genera aliases de productos/servicios desde categorias activas de negocio."""
    categorias = obtener_categorias_productos_soportadas()
    aliases = {categoria: _generar_aliases_producto(categoria) for categoria in categorias}
    if "bar movil" in categorias:
        aliases["bar movil"] = ["bar movil", "bar móvil", "barra movil", "barra móvil"]
    if "bartenders" in categorias:
        aliases["bartenders"] = ["bartender", "bartenders"]
    return aliases


# REFERENCIAS DE NEGOCIO: entrega categorias activas de productos y servicios cotizables.
def obtener_categorias_productos_soportadas() -> list[str]:
    """Obtiene categorias de productos desde PostgreSQL o desde datos locales si el modo es mock."""
    if usar_postgres_negocio():
        return _obtener_categorias_productos_postgres()
    categorias = {producto["category"] for producto in PRODUCTS}
    categorias.update(PRODUCT_CATEGORIES.get("servicios", {}).get("categories", []))
    return sorted(categorias)


# REFERENCIAS DE NEGOCIO: entrega productos no soportados conocidos por alternativas comerciales.
def obtener_aliases_productos_no_soportados() -> dict[str, list[str]]:
    """Obtiene categorias no vendidas directamente para sugerir alternativas cuando existan."""
    if usar_postgres_negocio():
        categorias = _obtener_categorias_no_soportadas_postgres()
    else:
        soportadas = set(obtener_categorias_productos_soportadas())
        categorias = sorted(
            categoria
            for familia in PRODUCT_CATEGORIES.values()
            for categoria in familia.get("alternatives", {})
            if categoria not in soportadas
        )
    aliases = {categoria: _generar_aliases_producto(categoria) for categoria in categorias}
    aliases.update(
        {
            "whisky": ["whisky", "whiskey"],
            "champagne": ["champagne", "espumante"],
            "jugo": ["jugo", "jugos"],
            "snacks": ["snack", "snacks", "piqueos", "bocaditos"],
            "torta": ["torta", "tortas", "pastel"],
            "comida": ["comida", "catering", "buffet"],
        }
    )
    return aliases


@lru_cache(maxsize=1)
def _obtener_tipos_evento_postgres() -> list[str]:
    """Consulta tipos de evento desde paquetes y productos activos en PostgreSQL."""
    with conexion_postgres() as conexion:
        rows = conexion.execute(
            """
            SELECT DISTINCT tipo_evento
            FROM (
                SELECT unnest(tipos_evento) AS tipo_evento
                FROM jpomm_paquetes
                WHERE activo = true
                UNION
                SELECT unnest(tipos_evento) AS tipo_evento
                FROM jpomm_productos
                WHERE activo = true
            ) tipos
            WHERE tipo_evento IS NOT NULL AND tipo_evento <> ''
            ORDER BY tipo_evento
            """
        ).fetchall()
    return [row["tipo_evento"] for row in rows]


@lru_cache(maxsize=1)
def _obtener_distritos_postgres() -> list[str]:
    """Consulta distritos activos de cobertura desde PostgreSQL."""
    with conexion_postgres() as conexion:
        rows = conexion.execute(
            """
            SELECT distrito
            FROM jpomm_cobertura_distritos
            WHERE activo = true
            ORDER BY distrito
            """
        ).fetchall()
    return [str(row["distrito"]).title() for row in rows]


@lru_cache(maxsize=1)
def _obtener_categorias_productos_postgres() -> list[str]:
    """Consulta categorias de productos y servicios cotizables desde PostgreSQL."""
    with conexion_postgres() as conexion:
        rows = conexion.execute(
            """
            SELECT DISTINCT categoria
            FROM jpomm_productos
            WHERE activo = true
            UNION
            SELECT DISTINCT 'bar movil' AS categoria
            FROM jpomm_paquetes
            WHERE activo = true
              AND (
                  lower(nombre) LIKE '%bar movil%'
                  OR lower(nombre) LIKE '%bar móvil%'
                  OR EXISTS (
                      SELECT 1 FROM unnest(incluye) item
                      WHERE lower(item) LIKE '%barra movil%'
                         OR lower(item) LIKE '%barra móvil%'
                  )
              )
            ORDER BY categoria
            """
        ).fetchall()
    return [row["categoria"] for row in rows]


@lru_cache(maxsize=1)
def _obtener_categorias_no_soportadas_postgres() -> list[str]:
    """Consulta categorias con alternativas que no estan como producto activo."""
    with conexion_postgres() as conexion:
        rows = conexion.execute(
            """
            SELECT DISTINCT categoria
            FROM jpomm_categoria_alternativas
            WHERE categoria NOT IN (
                SELECT categoria
                FROM jpomm_productos
                WHERE activo = true
            )
            ORDER BY categoria
            """
        ).fetchall()
    return [row["categoria"] for row in rows]


def _generar_aliases_tipo_evento(tipo: str) -> list[str]:
    """Genera aliases linguisticos sin cambiar la fuente de verdad de negocio."""
    normalizado = _sin_tildes(tipo.lower())
    aliases = {tipo.lower(), normalizado}
    if normalizado == "matrimonio":
        aliases.update({"boda", "matriminio"})
    if normalizado == "cumpleanos":
        aliases.update({"cumpleanos", "cumpleaños", "cumple"})
    if normalizado == "reunion":
        aliases.update({"reunion", "reunión"})
    if normalizado == "fin de ano":
        aliases.update({"fin de ano", "fin de año"})
    return sorted(aliases)


def _generar_aliases_producto(categoria: str) -> list[str]:
    """Genera aliases basicos de producto desde la categoria real."""
    base = categoria.lower()
    sin_tilde = _sin_tildes(base)
    aliases = {base, sin_tilde}
    if not base.endswith("s"):
        aliases.add(f"{base}s")
        aliases.add(f"{sin_tilde}s")
    return sorted(aliases)


def _sin_tildes(texto: str) -> str:
    """Normaliza texto para comparar entradas del usuario contra datos de negocio."""
    return "".join(
        caracter for caracter in unicodedata.normalize("NFD", texto) if unicodedata.category(caracter) != "Mn"
    )
