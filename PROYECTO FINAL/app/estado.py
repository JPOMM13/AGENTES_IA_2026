from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any
from uuid import uuid4


@dataclass
class EstadoCotizacion:
    """Estado completo de una cotizacion conversacional durante la sesion."""
    id_sesion: str = field(default_factory=lambda: str(uuid4()))
    etapa: str = "inicio"
    intencion: str | None = None

    tipo_evento: str | None = None
    asistentes: int | None = None
    fecha_evento: str | None = None
    fecha_parcial: dict[str, int | None] = field(default_factory=lambda: {"dia": None, "mes": None, "anio": None})
    distrito: str | None = None
    presupuesto: float | None = None
    productos_solicitados: list[str] = field(default_factory=list)
    productos_solicitados_no_soportados: list[str] = field(default_factory=list)
    productos_sin_stock: list[str] = field(default_factory=list)
    preferencias: list[str] = field(default_factory=list)
    nombre_cliente: str | None = None
    contacto: str | None = None

    campos_faltantes: list[str] = field(default_factory=list)
    opciones_catalogo: list[dict[str, Any]] = field(default_factory=list)
    opciones_validas: list[dict[str, Any]] = field(default_factory=list)
    opciones_descartadas: list[dict[str, Any]] = field(default_factory=list)
    opcion_recomendada: dict[str, Any] | None = None
    dimensionamiento: dict[str, Any] | None = None
    cotizacion: dict[str, Any] | None = None

    cobertura_ok: bool | None = None
    disponibilidad_ok: bool | None = None
    politica_ok: bool | None = None

    derivacion_ofrecida: bool = False
    derivacion_confirmada: bool = False
    resumen_derivacion: dict[str, Any] | None = None
    imagen_solicitada: bool = False
    imagen_artefacto_cotizacion: str | None = None
    cambio_producto_limpio_no_soportados: bool = False
    estado_previo_pendiente: dict[str, Any] | None = None

    mensajes: list[dict[str, str]] = field(default_factory=list)
    trazas: list[dict[str, Any]] = field(default_factory=list)

    # Ejecuta la responsabilidad de registrar log.
    def registrar_log(self, evento: str, carga: dict[str, Any] | None = None) -> None:
        """Registra una traza interna del flujo para debugging y evals."""
        self.trazas.append({"evento": evento, "carga": carga or {}})

    # Ejecuta la responsabilidad de a diccionario panel.
    def a_diccionario_panel(self) -> dict[str, Any]:
        """Devuelve una vista compacta del estado para mostrar en el panel lateral."""
        return {
            "etapa": self.etapa,
            "intencion": self.intencion,
            "tipo_evento": self.tipo_evento,
            "asistentes": self.asistentes,
            "fecha_evento": self.fecha_evento,
            "fecha_parcial": self.fecha_parcial,
            "distrito": self.distrito,
            "presupuesto": self.presupuesto,
            "productos_solicitados": self.productos_solicitados,
            "productos_solicitados_no_soportados": self.productos_solicitados_no_soportados,
            "productos_sin_stock": self.productos_sin_stock,
            "nombre_cliente": self.nombre_cliente,
            "contacto": self.contacto,
            "preferencias": self.preferencias,
            "campos_faltantes": self.campos_faltantes,
            "cobertura_ok": self.cobertura_ok,
            "disponibilidad_ok": self.disponibilidad_ok,
            "recomendado": self.opcion_recomendada["name"] if self.opcion_recomendada else None,
            "total_cotizacion": self.cotizacion["total"] if self.cotizacion else None,
            "derivacion_ofrecida": self.derivacion_ofrecida,
            "derivacion_confirmada": self.derivacion_confirmada,
            "imagen_solicitada": self.imagen_solicitada,
            "imagen_artefacto_cotizacion": self.imagen_artefacto_cotizacion,
        }

    # Ejecuta la responsabilidad de a diccionario persistido.
    def a_diccionario_persistido(self) -> dict[str, Any]:
        """Serializa el estado para guardarlo en la memoria mock entre sesiones."""
        data = asdict(self)
        data["mensajes"] = data["mensajes"][-20:]
        data["trazas"] = data["trazas"][-50:]
        return data

    # Ejecuta la responsabilidad de desde diccionario persistido.
    @classmethod
    def desde_diccionario_persistido(cls, data: dict[str, Any]) -> "EstadoCotizacion":
        """Reconstruye un EstadoCotizacion desde datos guardados previamente."""
        data = normalizar_diccionario_estado(data)
        allowed = {field.name for field in fields(cls)}
        filtered = {key: value for key, value in data.items() if key in allowed}
        return cls(**filtered)


# Ejecuta la responsabilidad de normalizar diccionario estado.
def normalizar_diccionario_estado(data: dict[str, Any]) -> dict[str, Any]:
    """Permite leer memorias antiguas guardadas con nombres previos."""
    equivalencias = {
        "session_id": "id_sesion",
        "stage": "etapa",
        "intent": "intencion",
        "event_type": "tipo_evento",
        "attendees": "asistentes",
        "event_date": "fecha_evento",
        "partial_date": "fecha_parcial",
        "district": "distrito",
        "budget": "presupuesto",
        "requested_products": "productos_solicitados",
        "unsupported_requested_products": "productos_solicitados_no_soportados",
        "stock_shortage_products": "productos_sin_stock",
        "preferences": "preferencias",
        "customer_name": "nombre_cliente",
        "contact": "contacto",
        "missing_fields": "campos_faltantes",
        "catalog_options": "opciones_catalogo",
        "valid_options": "opciones_validas",
        "discarded_options": "opciones_descartadas",
        "recommended_option": "opcion_recomendada",
        "dimensioning": "dimensionamiento",
        "quote": "cotizacion",
        "coverage_ok": "cobertura_ok",
        "availability_ok": "disponibilidad_ok",
        "policy_ok": "politica_ok",
        "handoff_offered": "derivacion_ofrecida",
        "handoff_confirmed": "derivacion_confirmada",
        "handoff_summary": "resumen_derivacion",
        "image_requested": "imagen_solicitada",
        "quote_artifact_image": "imagen_artefacto_cotizacion",
        "product_change_cleared_unsupported": "cambio_producto_limpio_no_soportados",
        "pending_previous_state": "estado_previo_pendiente",
        "messages": "mensajes",
        "logs": "trazas",
    }
    normalizado = dict(data)
    for anterior, actual in equivalencias.items():
        if anterior in normalizado and actual not in normalizado:
            normalizado[actual] = normalizado.pop(anterior)
    fecha_parcial = normalizado.get("fecha_parcial")
    if isinstance(fecha_parcial, dict):
        normalizado["fecha_parcial"] = {
            "dia": fecha_parcial.get("dia", fecha_parcial.get("day")),
            "mes": fecha_parcial.get("mes", fecha_parcial.get("month")),
            "anio": fecha_parcial.get("anio", fecha_parcial.get("year")),
        }
    return normalizado
