from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from app.almacen_calendario import CALENDARIO_MOCK_PATH
from app.data.datos_mock import (
    AVAILABILITY,
    CATALOG,
    COVERED_DISTRICTS,
    DEFAULT_PRODUCT_STOCK,
    MAX_EVENTOS_POR_DISTRITO_DIA,
    MOCK_KNOWLEDGE,
    PRODUCT_CATEGORIES,
    PRODUCTS,
)
from app.repositorios_postgres.conexion import conexion_postgres


# SCRIPT POSTGRES: carga paquetes, productos, stock, cobertura, RAG y reservas mock de forma idempotente.
def main() -> None:
    """Carga los datos mock de negocio en las tablas jpomm_*."""
    with conexion_postgres() as conexion:
        cargar_productos(conexion)
        cargar_paquetes(conexion)
        cargar_relacion_paquete_productos(conexion)
        cargar_stock_productos(conexion)
        cargar_disponibilidad_paquetes(conexion)
        cargar_alternativas_categorias(conexion)
        cargar_cobertura(conexion)
        cargar_rag(conexion)
        cargar_fechas_no_disponibles(conexion)
        cargar_configuracion_calendario(conexion)
        cargar_reservas_mock(conexion)
        conexion.commit()
    print("Datos iniciales jpomm_* cargados correctamente.")


# SCRIPT POSTGRES: inserta o actualiza el maestro de productos.
def cargar_productos(conexion) -> None:
    """Carga PRODUCTS en jpomm_productos."""
    for producto in PRODUCTS:
        conexion.execute(
            """
            INSERT INTO jpomm_productos (
                id, nombre, categoria, familia, unidad, precio_unitario, moneda, tipos_evento, activo, actualizado_en
            )
            VALUES (%(id)s, %(name)s, %(category)s, %(family)s, %(unit)s, %(unit_price)s, %(currency)s, %(event_types)s, true, now())
            ON CONFLICT (id) DO UPDATE SET
                nombre = EXCLUDED.nombre,
                categoria = EXCLUDED.categoria,
                familia = EXCLUDED.familia,
                unidad = EXCLUDED.unidad,
                precio_unitario = EXCLUDED.precio_unitario,
                moneda = EXCLUDED.moneda,
                tipos_evento = EXCLUDED.tipos_evento,
                activo = true,
                actualizado_en = now()
            """,
            producto,
        )


# SCRIPT POSTGRES: inserta o actualiza los paquetes comerciales.
def cargar_paquetes(conexion) -> None:
    """Carga CATALOG en jpomm_paquetes."""
    from psycopg.types.json import Jsonb

    for paquete in CATALOG:
        conexion.execute(
            """
            INSERT INTO jpomm_paquetes (
                id, nombre, servicio, tipos_evento, capacidad_min, capacidad_max, precio_base,
                moneda, imagen, afinidad_evento, incluye, activo, actualizado_en
            )
            VALUES (
                %(id)s, %(name)s, %(service)s, %(event_types)s, %(capacity_min)s, %(capacity_max)s,
                %(base_price)s, %(currency)s, %(image)s, %(event_affinity)s, %(includes)s, true, now()
            )
            ON CONFLICT (id) DO UPDATE SET
                nombre = EXCLUDED.nombre,
                servicio = EXCLUDED.servicio,
                tipos_evento = EXCLUDED.tipos_evento,
                capacidad_min = EXCLUDED.capacidad_min,
                capacidad_max = EXCLUDED.capacidad_max,
                precio_base = EXCLUDED.precio_base,
                moneda = EXCLUDED.moneda,
                imagen = EXCLUDED.imagen,
                afinidad_evento = EXCLUDED.afinidad_evento,
                incluye = EXCLUDED.incluye,
                activo = true,
                actualizado_en = now()
            """,
            {**paquete, "event_affinity": Jsonb(paquete["event_affinity"])},
        )


# SCRIPT POSTGRES: conserva los includes de cada paquete para auditoria y futuras consultas.
def cargar_relacion_paquete_productos(conexion) -> None:
    """Carga CATALOG.includes en jpomm_paquete_productos."""
    productos_por_categoria = {producto["category"]: producto["id"] for producto in PRODUCTS}
    productos_por_nombre = {producto["name"].lower(): producto["id"] for producto in PRODUCTS}
    for paquete in CATALOG:
        for orden, item_nombre in enumerate(paquete.get("includes", []), start=1):
            producto_id = productos_por_categoria.get(item_nombre) or productos_por_nombre.get(item_nombre.lower())
            conexion.execute(
                """
                INSERT INTO jpomm_paquete_productos (paquete_id, item_nombre, producto_id, orden)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (paquete_id, item_nombre) DO UPDATE SET
                    producto_id = EXCLUDED.producto_id,
                    orden = EXCLUDED.orden
                """,
                (paquete["id"], item_nombre, producto_id, orden),
            )


# SCRIPT POSTGRES: carga stock base y stock especifico por fecha desde AVAILABILITY.
def cargar_stock_productos(conexion) -> None:
    """Carga DEFAULT_PRODUCT_STOCK y disponibilidad de productos en jpomm_stock_productos."""
    for producto_id, stock in DEFAULT_PRODUCT_STOCK.items():
        insertar_stock_producto(conexion, producto_id, None, stock)

    for fecha_evento, disponibilidad in AVAILABILITY.items():
        for item_id, stock in disponibilidad.items():
            if item_id.startswith("PROD-"):
                insertar_stock_producto(conexion, item_id, fecha_evento, stock)


# SCRIPT POSTGRES: inserta una fila de stock sin duplicar por clave deterministica.
def insertar_stock_producto(conexion, producto_id: str, fecha_evento: str | None, stock: int) -> None:
    """Inserta o actualiza una fila de stock por producto y fecha."""
    clave_stock = f"{producto_id}:{fecha_evento or 'DEFAULT'}"
    conexion.execute(
        """
        INSERT INTO jpomm_stock_productos (clave_stock, producto_id, fecha_evento, stock, fuente, actualizado_en)
        VALUES (%s, %s, %s, %s, 'mock', now())
        ON CONFLICT (clave_stock) DO UPDATE SET
            stock = EXCLUDED.stock,
            fuente = EXCLUDED.fuente,
            actualizado_en = now()
        """,
        (clave_stock, producto_id, fecha_evento, stock),
    )


# SCRIPT POSTGRES: carga cupos de paquetes por fecha desde AVAILABILITY.
def cargar_disponibilidad_paquetes(conexion) -> None:
    """Carga cupos de paquetes en jpomm_disponibilidad_paquetes."""
    for fecha_evento, disponibilidad in AVAILABILITY.items():
        for item_id, cupos in disponibilidad.items():
            if item_id.startswith("PKG-"):
                conexion.execute(
                    """
                    INSERT INTO jpomm_disponibilidad_paquetes (paquete_id, fecha_evento, cupos, fuente, actualizado_en)
                    VALUES (%s, %s, %s, 'mock', now())
                    ON CONFLICT (paquete_id, fecha_evento) DO UPDATE SET
                        cupos = EXCLUDED.cupos,
                        fuente = EXCLUDED.fuente,
                        actualizado_en = now()
                    """,
                    (item_id, fecha_evento, cupos),
                )


# SCRIPT POSTGRES: carga categorias alternativas para que el agente no invente reemplazos.
def cargar_alternativas_categorias(conexion) -> None:
    """Carga PRODUCT_CATEGORIES.alternatives en jpomm_categoria_alternativas."""
    for configuracion in PRODUCT_CATEGORIES.values():
        for categoria, alternativas in configuracion.get("alternatives", {}).items():
            for prioridad, alternativa in enumerate(alternativas, start=1):
                conexion.execute(
                    """
                    INSERT INTO jpomm_categoria_alternativas (categoria, categoria_alternativa, prioridad)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (categoria, categoria_alternativa) DO UPDATE SET
                        prioridad = EXCLUDED.prioridad
                    """,
                    (categoria, alternativa, prioridad),
                )


# SCRIPT POSTGRES: carga los distritos con cobertura operativa.
def cargar_cobertura(conexion) -> None:
    """Carga COVERED_DISTRICTS en jpomm_cobertura_distritos."""
    for distrito in COVERED_DISTRICTS:
        conexion.execute(
            """
            INSERT INTO jpomm_cobertura_distritos (distrito, activo)
            VALUES (%s, true)
            ON CONFLICT (distrito) DO UPDATE SET activo = true
            """,
            (distrito,),
        )


# SCRIPT POSTGRES: carga documentos mock de conocimiento/RAG.
def cargar_rag(conexion) -> None:
    """Carga MOCK_KNOWLEDGE en jpomm_rag_documentos."""
    from psycopg.types.json import Jsonb

    for documento in MOCK_KNOWLEDGE:
        conexion.execute(
            """
            INSERT INTO jpomm_rag_documentos (id, titulo, texto, palabras_clave, metadata, activo)
            VALUES (%(id)s, %(title)s, %(texto)s, %(keywords)s, %(metadata)s, true)
            ON CONFLICT (id) DO UPDATE SET
                titulo = EXCLUDED.titulo,
                texto = EXCLUDED.texto,
                palabras_clave = EXCLUDED.palabras_clave,
                metadata = EXCLUDED.metadata,
                activo = true
            """,
            {**documento, "metadata": Jsonb({"origen": "datos_mock.py"})},
        )


# SCRIPT POSTGRES: deja preparada la tabla de fechas no disponibles aunque el mock actual no tenga registros.
def cargar_fechas_no_disponibles(conexion) -> None:
    """Mantiene la tabla lista para bloqueos futuros de calendario."""
    return None


# SCRIPT POSTGRES: carga reglas operativas de calendario.
def cargar_configuracion_calendario(conexion) -> None:
    """Carga MAX_EVENTOS_POR_DISTRITO_DIA en jpomm_configuracion_calendario."""
    from psycopg.types.json import Jsonb

    conexion.execute(
        """
        INSERT INTO jpomm_configuracion_calendario (clave, valor, descripcion, actualizado_en)
        VALUES (%s, %s, %s, now())
        ON CONFLICT (clave) DO UPDATE SET
            valor = EXCLUDED.valor,
            descripcion = EXCLUDED.descripcion,
            actualizado_en = now()
        """,
        (
            "MAX_EVENTOS_POR_DISTRITO_DIA",
            Jsonb({"valor": MAX_EVENTOS_POR_DISTRITO_DIA}),
            "Cantidad maxima de eventos permitidos por distrito y fecha.",
        ),
    )


# SCRIPT POSTGRES: migra las reservas del calendario JSON mock si existen.
def cargar_reservas_mock(conexion) -> None:
    """Carga app/data/mock_calendario_eventos.json en jpomm_reservas_eventos."""
    reservas = leer_reservas_mock()
    for indice, reserva in enumerate(reservas, start=1):
        id_reserva = reserva.get("id_reserva") or f"R-MOCK-{indice:04d}"
        conexion.execute(
            """
            INSERT INTO jpomm_reservas_eventos (
                id_reserva, id_sesion, quote_id, nombre_cliente, contacto, tipo_evento,
                asistentes, fecha_evento, distrito, productos_solicitados, registrado_en, estado
            )
            VALUES (
                %(id_reserva)s, %(id_sesion)s, %(quote_id)s, %(nombre_cliente)s, %(contacto)s,
                %(tipo_evento)s, %(asistentes)s, %(fecha_evento)s, %(distrito)s,
                %(productos_solicitados)s, %(registrado_en)s, %(estado)s
            )
            ON CONFLICT (id_reserva) DO UPDATE SET
                id_sesion = EXCLUDED.id_sesion,
                quote_id = EXCLUDED.quote_id,
                nombre_cliente = EXCLUDED.nombre_cliente,
                contacto = EXCLUDED.contacto,
                tipo_evento = EXCLUDED.tipo_evento,
                asistentes = EXCLUDED.asistentes,
                fecha_evento = EXCLUDED.fecha_evento,
                distrito = EXCLUDED.distrito,
                productos_solicitados = EXCLUDED.productos_solicitados,
                registrado_en = EXCLUDED.registrado_en,
                estado = EXCLUDED.estado
            """,
            {
                "id_reserva": id_reserva,
                "id_sesion": reserva.get("id_sesion"),
                "quote_id": reserva.get("quote_id"),
                "nombre_cliente": reserva.get("nombre_cliente"),
                "contacto": reserva.get("contacto"),
                "tipo_evento": reserva.get("tipo_evento"),
                "asistentes": reserva.get("asistentes"),
                "fecha_evento": reserva.get("fecha_evento"),
                "distrito": reserva.get("distrito"),
                "productos_solicitados": reserva.get("productos_solicitados", []),
                "registrado_en": reserva.get("registrado_en") or datetime.now().replace(microsecond=0).isoformat(),
                "estado": reserva.get("estado", "reservado"),
            },
        )


# SCRIPT POSTGRES: lee reservas mock tolerando archivo ausente o vacio.
def leer_reservas_mock() -> list[dict]:
    """Lee el calendario JSON mock sin fallar si todavia no existe."""
    ruta = RAIZ_PROYECTO / CALENDARIO_MOCK_PATH
    if not ruta.exists():
        return []
    try:
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return contenido if isinstance(contenido, list) else []


if __name__ == "__main__":
    main()
