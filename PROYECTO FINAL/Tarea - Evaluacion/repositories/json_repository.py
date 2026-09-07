import json
from copy import deepcopy
from pathlib import Path

class JsonDataRepository:
    # Lee el JSON una sola vez y verifica que estén presentes las entidades requeridas por la demo.
    def __init__(self, path: Path):
        self._data = json.loads(Path(path).read_text(encoding="utf-8"))
        required = {"clientes", "tipos_evento", "productos", "producto_evento", "cobertura",
                    "disponibilidad", "solicitudes", "cotizaciones", "cotizacion_detalle",
                    "preferencias_cliente", "derivaciones", "config_mock"}
        if required - self._data.keys():
            raise ValueError("El JSON no contiene todas las entidades requeridas.")

    # Entrega una copia del catálogo para evitar que el agente modifique los datos cargados.
    def get_products(self):
        return deepcopy(self._data["productos"])

    # Devuelve una copia de los nombres de eventos reconocidos.
    def get_event_types(self):
        return list(self._data["tipos_evento"])

    # Busca la afinidad producto/evento; devuelve cero cuando no hay una relación registrada.
    def get_affinity(self, product_id, event_type):
        return next((r["affinity"] for r in self._data["producto_evento"]
                     if r["product_id"] == product_id and r["event_type"] == event_type), 0)

    # Comprueba una cobertura habilitada por producto y ubicación, ignorando diferencias de mayúsculas.
    def get_coverage(self, product_id, location):
        return any(r["product_id"] == product_id and r["location"].casefold() == location.casefold()
                   and r["enabled"] for r in self._data["cobertura"])

    # Devuelve stock explícito si el estado es DISPONIBLE; ausencia, agotamiento o unidades negativas dan cero.
    def get_availability(self, product_id, date):
        # Ausencia de registro significa NO disponible, nunca inferir stock.
        return next((max(0, r["units"]) if r["status"] == "DISPONIBLE" else 0
                     for r in self._data["disponibilidad"]
                     if r["product_id"] == product_id and r["date"] == date), 0)

    # Consulta categorías preferidas solo si el identificador confiable corresponde a un cliente con consentimiento.
    def get_preferences(self, customer_id):
        # El identificador debe proceder de autenticación, jamás de extracción LLM.
        authorized = any(c["id"] == customer_id and c["consent"] for c in self._data["clientes"])
        if not authorized:
            return []
        return [r["category"] for r in self._data["preferencias_cliente"] if r["customer_id"] == customer_id]

    # Obtiene el precio base registrado para el producto; no calcula ni inventa precios alternativos.
    def get_price(self, product_id):
        return next(p["base_price"] for p in self._data["productos"] if p["id"] == product_id)

    # Devuelve una copia de config_mock con moneda, impuesto, calendario y supuestos comerciales.
    def get_config(self):
        return deepcopy(self._data["config_mock"])
