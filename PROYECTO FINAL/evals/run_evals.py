from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# EVALS / AISLAMIENTO GLOBAL:
# Evita que el archivo .env productivo sobrescriba estas variables durante los evals.
# Asi los casos corren sin depender de OpenAI, LangSmith, Redis real ni PostgreSQL real.
os.environ["COTIZADOR_NO_SOBRESCRIBIR_ENV"] = "true"
os.environ["SESSION_STORE"] = "mock"
os.environ["MEMORY_DATA_SOURCE"] = "mock"
os.environ["BUSINESS_DATA_SOURCE"] = "mock"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["IMAGE_GENERATION_ENABLED"] = "false"

from app.estado import EstadoCotizacion
from app.flujo import manejar_mensaje
import app.almacen_calendario as almacen_calendario
import app.almacen_sesion as almacen_sesion
import app.almacen_sesion_redis as almacen_sesion_redis


# EVALS / MAIN: ejecuta casos conversacionales completos contra el workflow actual.
def principal() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta evals de comportamiento del agente.")
    parser.add_argument("--cases", default=str(ROOT / "evals" / "cases.json"))
    parser.add_argument("--trace", action="store_true", help="Print workflow trace for each case.")
    parser.add_argument("--with-llm", action="store_true", help="Use configured LLM instead of deterministic mode.")
    args = parser.parse_args()

    if not args.with_llm:
        os.environ["LLM_ENABLED"] = "false"

    # EVALS / LOGS:
    # Por defecto los evals muestran solo PASS/FAIL. Con --trace se habilita detalle del grafo.
    if not args.trace:
        logging.getLogger("cotizador.flujo").setLevel(logging.WARNING)

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    failures = []
    for case in cases:
        result = ejecutar_caso(case, trace=args.trace)
        if result["passed"]:
            print(f"PASS {case['name']}")
        else:
            failures.append(result)
            print(f"FAIL {case['name']}")
            for error in result["errors"]:
                print(f"  - {error}")

    print(f"\n{len(cases) - len(failures)}/{len(cases)} evals passed")
    return 1 if failures else 0


# EVALS / CASO: aisla memoria local, ejecuta setup y luego los mensajes del caso.
def ejecutar_caso(case: dict[str, Any], trace: bool = False) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        almacen_sesion.STORE_PATH = temp_path / "mock_session_memory.json"
        almacen_sesion_redis.REDIS_MOCK_PATH = temp_path / "mock_redis_session.json"
        almacen_calendario.CALENDARIO_MOCK_PATH = temp_path / "mock_calendario_eventos.json"
        almacen_calendario.CALENDARIO_MOCK_PATH.write_text("[]", encoding="utf-8")

        # EVALS / AISLAMIENTO:
        # Fuerza mocks locales para que los evals no dependan de Redis real ni PostgreSQL memory real.
        os.environ["SESSION_STORE"] = "mock"
        os.environ["MEMORY_DATA_SOURCE"] = "mock"
        os.environ.setdefault("BUSINESS_DATA_SOURCE", "mock")

        for setup_message in case.get("setup_messages", []):
            setup_state = EstadoCotizacion()
            manejar_mensaje(setup_message, setup_state)

        state = EstadoCotizacion()
        responses = []
        for message in case["messages"]:
            response, state = manejar_mensaje(message, state)
            responses.append(response)

        snapshot = capturar_estado(state)
        errors = comparar_esperado(case["expected"], snapshot, responses[-1] if responses else "")

        if trace:
            print(f"\nTRACE {case['name']}")
            for index, message in enumerate(case["messages"], start=1):
                print(f"  user[{index}]: {message}")
            for traza in state.trazas:
                print(f"  {traza['evento']}: {json.dumps(traza['carga'], ensure_ascii=False)}")
            print(f"  final_state: {json.dumps(snapshot, ensure_ascii=False)}")

        return {"passed": not errors, "errors": errors, "state": snapshot}


# EVALS / SNAPSHOT: expone alias antiguos y actuales para comparar cases.json sin reescribirlo completo.
def capturar_estado(state: EstadoCotizacion) -> dict[str, Any]:
    recomendado = state.opcion_recomendada or {}
    cotizacion = state.cotizacion or {}
    return {
        **state.a_diccionario_panel(),
        "event_type": state.tipo_evento,
        "event_date": state.fecha_evento,
        "attendees": state.asistentes,
        "district": state.distrito,
        "customer_name": state.nombre_cliente,
        "contact": state.contacto,
        "requested_products": state.productos_solicitados,
        "unsupported_requested_products": state.productos_solicitados_no_soportados,
        "stock_shortage_products": state.productos_sin_stock,
        "missing_fields": _campos_faltantes_alias(state.campos_faltantes),
        "availability_ok": state.disponibilidad_ok,
        "recommended_id": recomendado.get("id"),
        "recommended_source": recomendado.get("origen") or recomendado.get("source"),
        "quote_generated": state.cotizacion is not None,
        "quote_total": cotizacion.get("total"),
        "handoff_confirmed": state.derivacion_confirmada,
        "stage": state.etapa,
    }


# EVALS / COMPATIBILIDAD: traduce nombres actuales a los nombres historicos de cases.json.
def _campos_faltantes_alias(campos: list[str]) -> list[str]:
    equivalencias = {
        "tipo_evento": "event_type",
        "asistentes": "attendees",
        "fecha_evento": "event_date",
        "distrito": "district",
        "nombre_cliente": "customer_name",
        "contacto": "contact",
        "productos_solicitados": "requested_products",
    }
    return [equivalencias.get(campo, campo) for campo in campos]


# EVALS / ASSERTS: compara estado final y respuesta final contra lo esperado del caso.
def comparar_esperado(expected: dict[str, Any], snapshot: dict[str, Any], last_response: str) -> list[str]:
    errors = []
    for key, expected_value in expected.items():
        if key == "last_response_contains":
            for text in expected_value:
                if text not in last_response:
                    errors.append(f"last_response should contain {text!r}")
            continue
        if key == "last_response_not_contains":
            for text in expected_value:
                if text in last_response:
                    errors.append(f"last_response should not contain {text!r}")
            continue
        if key == "not_requested_products":
            actual_products = snapshot.get("requested_products", [])
            for product in expected_value:
                if product in actual_products:
                    errors.append(f"requested_products should not include {product!r}; got {actual_products!r}")
            continue

        actual_value = snapshot.get(key)
        if isinstance(expected_value, list):
            if actual_value != expected_value:
                errors.append(f"{key}: expected {expected_value!r}, got {actual_value!r}")
        elif actual_value != expected_value:
            errors.append(f"{key}: expected {expected_value!r}, got {actual_value!r}")
    return errors


if __name__ == "__main__":
    raise SystemExit(principal())
