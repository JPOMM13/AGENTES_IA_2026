from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.configuracion_llm import cargar_archivo_env


class ErrorConfiguracionPostgres(RuntimeError):
    """Error controlado cuando faltan variables o dependencias de PostgreSQL."""


# CONFIGURACION POSTGRES: centraliza host, credenciales y SSL para conectar a la BD eventos.
def obtener_parametros_postgres() -> dict:
    """Construye parametros de PostgreSQL desde variables de entorno."""
    cargar_archivo_env()
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB", "eventos")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    if not user or not password:
        raise ErrorConfiguracionPostgres("Faltan POSTGRES_USER o POSTGRES_PASSWORD para conectar a PostgreSQL.")

    parametros = {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
    }
    for env_name, param_name in {
        "POSTGRES_SSLMODE": "sslmode",
        "POSTGRES_SSLROOTCERT": "sslrootcert",
        "POSTGRES_SSLCERT": "sslcert",
        "POSTGRES_SSLKEY": "sslkey",
    }.items():
        value = os.getenv(env_name)
        if value:
            if env_name == "POSTGRES_SSLKEY":
                asegurar_permiso_llave_privada(value)
            parametros[param_name] = value
    return parametros


# CONFIGURACION POSTGRES/SSL: libpq rechaza llaves privadas con permisos de grupo u otros.
def asegurar_permiso_llave_privada(ruta_llave: str) -> None:
    """Asegura permisos 0600 para la llave privada SSL si existe localmente."""
    path = Path(ruta_llave)
    if not path.exists():
        return
    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        path.chmod(0o600)


def obtener_dsn_postgres() -> str:
    """Construye un DSN legible para diagnostico sin exponer la clave."""
    parametros = obtener_parametros_postgres()
    parametros_visibles = {key: value for key, value in parametros.items() if key != "password"}
    return " ".join(f"{key}={value}" for key, value in parametros_visibles.items())


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

    with psycopg.connect(**obtener_parametros_postgres(), row_factory=dict_row) as conexion:
        conexion.execute(
            sql.SQL("SET search_path TO {}, public").format(sql.Identifier(obtener_schema_postgres()))
        )
        yield conexion
