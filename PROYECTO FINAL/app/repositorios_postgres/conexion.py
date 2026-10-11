from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from app.configuracion_llm import cargar_archivo_env


class ErrorConfiguracionPostgres(RuntimeError):
    """Error controlado cuando faltan variables o dependencias de PostgreSQL."""


def obtener_dsn_postgres() -> str:
    """Construye el DSN de PostgreSQL desde variables de entorno."""
    cargar_archivo_env()
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB", "eventos")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    if not user or not password:
        raise ErrorConfiguracionPostgres("Faltan POSTGRES_USER o POSTGRES_PASSWORD para conectar a PostgreSQL.")
    return f"host={host} port={port} dbname={dbname} user={user} password={password}"


# CONFIGURACION POSTGRES: define el schema donde viven las tablas jpomm_* de negocio.
def obtener_schema_postgres() -> str:
    """Devuelve el schema PostgreSQL usado para datos de negocio."""
    cargar_archivo_env()
    schema = os.getenv("POSTGRES_SCHEMA", "negocio").strip()
    if not schema:
        raise ErrorConfiguracionPostgres("POSTGRES_SCHEMA no puede estar vacio.")
    return schema


@contextmanager
def conexion_postgres() -> Iterator:
    """Abre una conexion PostgreSQL y apunta el search_path al schema de negocio."""
    try:
        import psycopg
        from psycopg import sql
        from psycopg.rows import dict_row
    except ImportError as error:
        raise ErrorConfiguracionPostgres("Instala psycopg para usar BUSINESS_DATA_SOURCE=postgres.") from error

    with psycopg.connect(obtener_dsn_postgres(), row_factory=dict_row) as conexion:
        conexion.execute(
            sql.SQL("SET search_path TO {}, public").format(sql.Identifier(obtener_schema_postgres()))
        )
        yield conexion
