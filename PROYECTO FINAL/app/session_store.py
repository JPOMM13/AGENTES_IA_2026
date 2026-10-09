from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.estado import EstadoCotizacion


STORE_PATH = Path(__file__).resolve().parent / "data" / "mock_session_memory.json"


# Ejecuta la responsabilidad de guardar estado conversacion.
def guardar_estado_conversacion(estado: EstadoCotizacion) -> None:
    """Guarda el estado si ya existe una identidad minima del cotizante."""
    # MOCK: ESTA MEMORIA ENTRE SESIONES DEBERIA GUARDARSE EN POSTGRESQL/NOSQL USANDO CONTACT COMO IDENTIFICADOR PRINCIPAL.
    if not estado.contacto:
        return
    if not _tiene_datos_para_memoria_persistente(estado):
        return

    store = _leer_almacen()
    record = estado.a_diccionario_persistido()
    record["updated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    store[_clave_contacto(estado.contacto)] = record
    _escribir_almacen(store)


# Ejecuta la responsabilidad de buscar conversacion previa.
def buscar_conversacion_previa(nombre_cliente: str | None, contacto: str | None) -> EstadoCotizacion | None:
    """Busca una conversacion anterior usando contacto como identidad principal."""
    # MOCK: ESTA CONSULTA DEBERIA IR A POSTGRESQL O NOSQL BUSCANDO POR TELEFONO/CORREO, NO POR NOMBRE.
    if not contacto:
        return None
    record = _leer_almacen().get(_clave_contacto(contacto))
    if not record:
        return None
    return EstadoCotizacion.desde_diccionario_persistido(record)


# Ejecuta la responsabilidad de hidratar estado.
def hidratar_estado(destino: EstadoCotizacion, origen: EstadoCotizacion) -> EstadoCotizacion:
    """Carga una conversacion previa dentro de la nueva sesion actual."""
    current_session_id = destino.id_sesion
    restored = origen.a_diccionario_persistido()
    restored["id_sesion"] = current_session_id
    restored["mensajes"] = destino.mensajes
    restored["trazas"] = destino.trazas + origen.trazas[-20:]
    return EstadoCotizacion.desde_diccionario_persistido(restored)


# Ejecuta logica interna para clave contacto.
def _clave_contacto(contacto: str) -> str:
    """Normaliza telefono o correo para identificar al cliente."""
    return re.sub(r"\D+", "", contacto.lower()) or contacto.strip().lower()


# Ejecuta logica interna para tiene datos para memoria persistente.
def _tiene_datos_para_memoria_persistente(estado: EstadoCotizacion) -> bool:
    """Evita guardar busquedas vacias como si fueran cotizaciones previas."""
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


# Ejecuta logica interna para leer almacen.
def _leer_almacen() -> dict[str, Any]:
    """Lee el archivo local de memoria mock y devuelve un diccionario seguro."""
    if not STORE_PATH.exists():
        return {}
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


# Ejecuta logica interna para escribir almacen.
def _escribir_almacen(store: dict[str, Any]) -> None:
    """Persiste el diccionario de memoria mock en disco."""
    STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
