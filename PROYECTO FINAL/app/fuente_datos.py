from __future__ import annotations

import os

from app.configuracion_llm import cargar_archivo_env


# CONFIGURACION DATOS: define si las tools de negocio leen datos locales o PostgreSQL.
def usar_postgres_negocio() -> bool:
    """Indica si catalogo, stock, cobertura, RAG y calendario deben usar PostgreSQL."""
    cargar_archivo_env()
    return os.getenv("BUSINESS_DATA_SOURCE", "mock").strip().lower() == "postgres"
