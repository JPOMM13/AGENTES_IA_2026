from __future__ import annotations

from langchain.tools import tool


# Ejecuta la responsabilidad de consultar catalogo mock.
@tool
def consultar_catalogo_mock(descripcion: str) -> str:
    """TOOL MOCK: REPRESENTA LA CONSULTA AGENTICA AL CATALOGO REAL DE PRODUCTOS Y SERVICIOS."""
    return f"Catalogo mock consultado para: {descripcion}"


# Ejecuta la responsabilidad de validar cobertura mock.
@tool
def validar_cobertura_mock(distrito: str) -> str:
    """TOOL MOCK: REPRESENTA LA VALIDACION AGENTICA DE COBERTURA OPERATIVA."""
    return f"Cobertura mock consultada para distrito: {distrito}"


# Ejecuta la responsabilidad de validar stock mock.
@tool
def validar_stock_mock(productos: str) -> str:
    """TOOL MOCK: REPRESENTA LA VALIDACION AGENTICA DE STOCK/DISPONIBILIDAD."""
    return f"Stock mock consultado para productos: {productos}"


# Ejecuta la responsabilidad de generar cotizacion mock.
@tool
def generar_cotizacion_mock(resumen: str) -> str:
    """TOOL MOCK: REPRESENTA LA GENERACION AGENTICA DE COTIZACION FORMAL."""
    return f"Cotizacion mock solicitada con resumen: {resumen}"


# Ejecuta la responsabilidad de obtener tools agenticas negocio.
def obtener_tools_agenticas_negocio() -> list:
    """Devuelve las tools mock que documentan las capacidades agenticas de negocio."""
    return [
        consultar_catalogo_mock,
        validar_cobertura_mock,
        validar_stock_mock,
        generar_cotizacion_mock,
    ]
