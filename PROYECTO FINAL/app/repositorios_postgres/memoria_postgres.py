from __future__ import annotations

import os
import re

from psycopg import sql
from psycopg.types.json import Jsonb

from app.configuracion_llm import cargar_archivo_env
from app.estado import EstadoCotizacion
from app.repositorios_postgres.conexion import conexion_postgres


# CONFIGURACION MEMORIA POSTGRES: carga .env como fuente principal de runtime.
def leer_variable_entorno(nombre: str, valor_por_defecto: str) -> str:
    """Lee una variable de entorno desde .env o entorno."""
    cargar_archivo_env()
    return os.getenv(nombre, valor_por_defecto)


# CONFIGURACION MEMORIA POSTGRES: define el schema JSONB para memoria persistente.
def obtener_schema_memoria() -> str:
    """Devuelve el schema PostgreSQL donde se guarda la memoria persistente."""
    schema = leer_variable_entorno("POSTGRES_MEMORY_SCHEMA", "memory").strip()
    return schema or "memory"


# MEMORIA PERSISTENTE POSTGRES: normaliza telefono celular para busquedas consistentes.
def normalizar_contacto(contacto: str) -> str:
    """Normaliza el contacto usado como identidad principal del cliente."""
    return re.sub(r"\D+", "", contacto.lower()) or contacto.strip().lower()


# VALIDACION DE MEMORIA: evita guardar estados vacios como cotizaciones retomables.
def tiene_datos_para_memoria_persistente(estado: EstadoCotizacion) -> bool:
    """Indica si el estado tiene informacion suficiente para persistirse."""
    return any(
        [
            estado.tipo_evento,
            estado.asistentes,
            estado.fecha_evento,
            estado.distrito,
            estado.productos_solicitados,
            estado.opcion_recomendada,
            estado.cotizacion,
        ]
    )


# MEMORIA PERSISTENTE POSTGRES: guarda la ultima version de la cotizacion por contacto.
def guardar_estado_conversacion_postgres(estado: EstadoCotizacion) -> None:
    """Persiste el estado de cotizacion en PostgreSQL JSONB."""
    if not estado.contacto:
        return
    if not tiene_datos_para_memoria_persistente(estado):
        return

    schema = obtener_schema_memoria()
    contacto = estado.contacto
    nombre_cliente = estado.nombre_cliente
    clave_cliente = normalizar_contacto(contacto)
    estado_json = estado.a_diccionario_persistido()

    with conexion_postgres() as conexion:
        conexion.execute(
            sql.SQL(
                """
                INSERT INTO {}.jpomm_memoria_cotizaciones (
                    contacto, nombre_cliente, clave_cliente, estado_cotizacion
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (contacto) DO UPDATE SET
                    nombre_cliente = EXCLUDED.nombre_cliente,
                    clave_cliente = EXCLUDED.clave_cliente,
                    estado_cotizacion = EXCLUDED.estado_cotizacion
                """
            ).format(sql.Identifier(schema)),
            (contacto, nombre_cliente, clave_cliente, Jsonb(estado_json)),
        )
        conexion.commit()


# MEMORIA PERSISTENTE POSTGRES: busca una cotizacion previa por telefono celular.
def buscar_conversacion_previa_postgres(contacto: str | None) -> EstadoCotizacion | None:
    """Recupera una memoria previa desde PostgreSQL JSONB usando el contacto."""
    if not contacto:
        return None

    schema = obtener_schema_memoria()
    contacto_normalizado = normalizar_contacto(contacto)
    with conexion_postgres() as conexion:
        fila = conexion.execute(
            sql.SQL(
                """
                SELECT estado_cotizacion
                FROM {}.jpomm_memoria_cotizaciones
                WHERE contacto = %s OR clave_cliente = %s
                ORDER BY actualizado_en DESC
                LIMIT 1
                """
            ).format(sql.Identifier(schema)),
            (contacto, contacto_normalizado),
        ).fetchone()

    if not fila:
        return None
    return EstadoCotizacion.desde_diccionario_persistido(dict(fila["estado_cotizacion"]))
