from __future__ import annotations

import json
import re
import sys
from pathlib import Path


RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from psycopg import sql
from psycopg.types.json import Jsonb

from app.almacen_sesion import STORE_PATH
from app.configuracion_llm import cargar_archivo_env
from app.repositorios_postgres.conexion import conexion_postgres


# SCRIPT POSTGRES/MEMORIA: migra mock_session_memory.json a memory.jpomm_memoria_cotizaciones.
def main() -> None:
    """Migra la memoria persistente mock a PostgreSQL JSONB de forma idempotente."""
    cargar_archivo_env()
    memorias = leer_memoria_mock()
    if not memorias:
        print("No hay memorias mock para migrar.")
        return

    schema = obtener_schema_memoria()
    with conexion_postgres() as conexion:
        for clave_contacto, estado in memorias.items():
            contacto = str(estado.get("contacto") or clave_contacto)
            nombre_cliente = estado.get("nombre_cliente")
            clave_cliente = normalizar_contacto(contacto)
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
                (contacto, nombre_cliente, clave_cliente, Jsonb(estado)),
            )
        conexion.commit()
    print(f"Memorias migradas a PostgreSQL: {len(memorias)}")


# SCRIPT POSTGRES/MEMORIA: lee el JSON mock sin fallar si esta vacio o no existe.
def leer_memoria_mock() -> dict:
    """Lee app/data/mock_session_memory.json."""
    ruta = RAIZ_PROYECTO / STORE_PATH
    if not ruta.exists():
        return {}
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


# SCRIPT POSTGRES/MEMORIA: obtiene el schema destino para JSONB.
def obtener_schema_memoria() -> str:
    """Lee POSTGRES_MEMORY_SCHEMA con fallback memory."""
    import os

    return os.getenv("POSTGRES_MEMORY_SCHEMA", "memory").strip() or "memory"


# SCRIPT POSTGRES/MEMORIA: normaliza telefono o correo para busqueda.
def normalizar_contacto(contacto: str) -> str:
    """Normaliza el contacto usado como clave de cliente."""
    return re.sub(r"\D+", "", contacto.lower()) or contacto.strip().lower()


if __name__ == "__main__":
    main()
