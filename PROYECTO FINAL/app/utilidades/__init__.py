"""Utilidades puras (sin estado ni I/O) compartidas por tools y extractor.

Por que existe este paquete: la resolucion de fechas y numeros en espanol es
logica determinista que antes vivia dispersa en regex dentro de extraccion.py.
Aislarla permite probarla con `hoy` inyectable (sin depender del reloj real)
y reutilizarla desde las reglas, el extractor LLM y las tools de negocio.
"""
