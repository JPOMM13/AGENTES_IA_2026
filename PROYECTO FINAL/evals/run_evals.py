from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.state import QuoteState
from app.workflow import manejar_mensaje
import app.redis_session_store as redis_session_store
import app.session_store as session_store


# Ejecuta la responsabilidad de main.
def principal() -> int:
    parser = argparse.ArgumentParser(description="Run agent behavior evals.")
    parser.add_argument("--cases", default=str(ROOT / "evals" / "cases.json"))
    parser.add_argument("--trace", action="store_true", help="Print workflow trace for each case.")
    parser.add_argument("--with-llm", action="store_true", help="Use configured LLM instead of deterministic mode.")
    args = parser.parse_args()

    if not args.with_llm:
        os.environ["LLM_ENABLED"] = "false"

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


# Ejecuta la responsabilidad de ejecutar caso.
def ejecutar_caso(case: dict[str, Any], trace: bool = False) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        session_store.STORE_PATH = temp_path / "mock_session_memory.json"
        redis_session_store.REDIS_MOCK_PATH = temp_path / "mock_redis_session.json"

        for setup_message in case.get("setup_messages", []):
            setup_state = QuoteState()
            manejar_mensaje(setup_message, setup_state)

        state = QuoteState()
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
            for registrar_log in state.logs:
                print(f"  {registrar_log['event']}: {json.dumps(registrar_log['payload'], ensure_ascii=False)}")
            print(f"  final_state: {json.dumps(snapshot, ensure_ascii=False)}")

        return {"passed": not errors, "errors": errors, "state": snapshot}


# Ejecuta la responsabilidad de capturar estado.
def capturar_estado(state: QuoteState) -> dict[str, Any]:
    return {
        **state.a_diccionario_panel(),
        "recommended_id": state.recommended_option["id"] if state.recommended_option else None,
        "recommended_source": state.recommended_option["source"] if state.recommended_option else None,
        "quote_generated": state.quote is not None,
        "quote_total": state.quote["total"] if state.quote else None,
        "stage": state.stage,
    }


# Ejecuta la responsabilidad de comparar esperado.
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
