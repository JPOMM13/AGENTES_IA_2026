"""python -m evaluation.run_evaluation [--offline]."""
import argparse
import hashlib
import json
import os
from datetime import datetime
from uuid import uuid4
from langsmith import Client, tracing_context
from config import Settings, ROOT, require_key
from agent.graph import QuoteAgent, OpenAIInterpreter
from agent.state import Extraction
from agent.prompts import OPENINGS
from repositories.json_repository import JsonDataRepository
from evaluation.dataset import cases
from evaluation.evaluators import make_evaluators, make_judge, SemanticGrades, METRICS

class ScriptedInterpreter:
    """Doble de extracción SOLO para pruebas locales, no mide comprensión del LLM."""
    # Relaciona cada mensaje del caso con su extracción simulada para las pruebas offline.
    def __init__(self, turns):
        self.by_message = {t["message"]:t["extraction"] for t in turns}
    # Devuelve la extracción de prueba validada con Pydantic; no llama a OpenAI.
    def extract(self, message, state, now, event_types):
        return Extraction.model_validate(self.by_message[message])
    # Devuelve una apertura fija para que las pruebas locales sean reproducibles.
    def opening(self, response):
        return OPENINGS[1]

class FaultRepository(JsonDataRepository):
    # Provoca un timeout controlado para comprobar los reintentos y la derivación por fallo persistente.
    def get_products(self):
        raise TimeoutError("Fallo sintético de lectura")


# Construye la función que ejecutará cada caso, usando un intérprete real o simulado según el modo.
def target_for(settings, offline):
    # Crea una sesión aislada, envía los turnos al agente y devuelve el estado final que evaluarán las métricas.
    def target(inputs):
        repo = (FaultRepository if inputs.get("fault") else JsonDataRepository)(settings.data_path)
        interpreter = ScriptedInterpreter(inputs["turns"]) if offline else OpenAIInterpreter(settings)
        agent = QuoteAgent(repo, interpreter, settings.reference_datetime)
        state = None
        # Cada mensaje se envía realmente al grafo; los turnos del mismo caso comparten estado.
        for turn in inputs["turns"]:
            state = agent.respond(turn["message"], state, trusted_customer_id=inputs.get("trusted_customer_id"))
        return state
    return target


# Guarda resultados JSON y un resumen Markdown con aprobación por caso y promedio por métrica.
def write_report(rows, mode):
    directory = ROOT / "reports"
    directory.mkdir(exist_ok=True)
    stem = directory / (mode + "-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6])
    passed = 0
    details = []
    expected_keys = set(METRICS)
    if mode == "langsmith":
        expected_keys |= set(SemanticGrades.model_fields)
    for row in rows:
        feedback = row["feedback"]
        # Un caso requiere todas las métricas: una nota ausente nunca equivale a aprobar.
        complete = {f["key"] for f in feedback} == expected_keys
        # Umbrales: 1 para cada regla y al menos 4/5 para cada criterio del juez.
        ok = complete and all(f.get("score") is not None and f["score"] >= (4 if f["key"] in SemanticGrades.model_fields else 1) for f in feedback)
        passed += int(ok)
        failures = [f["key"] for f in feedback if f.get("score") is None or f["score"] < (4 if f["key"] in SemanticGrades.model_fields else 1)]
        if not complete:
            failures.append("evaluaciones_faltantes")
        details.append(f"| {row['id']} | {'APROBADO' if ok else 'FALLIDO/INCOMPLETO'} | {', '.join(failures) or '—'} |")
    stem.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    text = f"# Evaluación {mode}\n\nCasos aprobados: {passed}/{len(rows)}.\n\n"
    if mode == "offline":
        text += "Solo reglas con extracción simulada. SIN OpenAI, juez, trazas remotas ni experimento LangSmith. No es evidencia de calidad end-to-end.\n\n"
    text += "| Caso | Resultado | Métricas que requieren revisión |\n|---|---|---|\n" + "\n".join(details) + "\n"
    text += "\n## Resumen por métrica\n\n| Métrica | Notas disponibles | Promedio | Escala |\n|---|---:|---:|---|\n"
    for key in sorted(expected_keys):
        # Promedia las notas disponibles; muestra su cantidad para hacer visibles las faltantes.
        values = [f["score"] for row in rows for f in row["feedback"] if f["key"] == key and f.get("score") is not None]
        average = f"{sum(values)/len(values):.3f}" if values else "Sin nota"
        text += f"| {key} | {len(values)}/{len(rows)} | {average} | {'1–5' if key in SemanticGrades.model_fields else '0–1'} |\n"
    stem.with_suffix(".md").write_text(text, encoding="utf-8")
    print(f"{passed}/{len(rows)} aprobados; {len(rows)-passed} fallidos o incompletos. Reporte: {stem.with_suffix('.md')}")
    return 0 if passed == len(rows) else 1


# Carga los casos y coordina su ejecución: reglas locales en offline o experimento con trazas y juez en LangSmith.
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Solo reglas con extracción simulada; no consume APIs")
    args = parser.parse_args(argv)
    settings = Settings.load()
    # Aquí se cargan los 15 mensajes de prueba y las referencias con las que se compararán.
    dataset = cases()
    repo = JsonDataRepository(settings.data_path)
    evaluators = make_evaluators(repo, settings.reference_datetime)
    target = target_for(settings, args.offline)
    if args.offline:
        # Offline ejecuta el grafo con extracción simulada; desactiva trazas remotas y no usa juez.
        with tracing_context(enabled=False):
            rows = []
            for case in dataset:
                # Primero ejecutar el agente; después calificar la salida obtenida con las referencias.
                output = target(case["inputs"])
                rows.append({"id":case["id"], "output":output,
                             "feedback":[fn(output, case["outputs"]) for fn in evaluators]})
        return write_report(rows, "offline")
    try:
        require_key("LANGSMITH_API_KEY")
        require_key("OPENAI_API_KEY")
    except ValueError as exc:
        print(exc)
        return 2
    judge = make_judge(settings)
    client = Client()
    # El hash cambia si cambian casos o datos mock, creando una versión distinta del dataset.
    digest = hashlib.sha256(json.dumps(dataset, sort_keys=True).encode() + settings.data_path.read_bytes()).hexdigest()[:12]
    name = f"utec-eventos-v1-{digest}"
    if client.has_dataset(dataset_name=name):
        ds = client.read_dataset(dataset_name=name)
    else:
        ds = client.create_dataset(dataset_name=name, description="15 casos sintéticos de agente de cotizaciones; referencias explícitas.")
    # Recuperación de cargas interrumpidas sin duplicar casos.
    existing = {e.metadata.get("case_id") for e in client.list_examples(dataset_id=ds.id) if e.metadata}
    for case in dataset:
        if case["id"] not in existing:
            client.create_example(dataset_id=ds.id, inputs=case["inputs"], outputs=case["outputs"], metadata={"case_id":case["id"]})
    # Habilita el registro remoto de las ejecuciones que se realizarán dentro de este bloque.
    with tracing_context(enabled=True):
        # evaluate ejecuta target por cada ejemplo: genera runs/trazas y luego aplica los evaluadores.
        # Crear el dataset arriba no ejecuta el agente ni produce por sí solo sus trazas.
        results = client.evaluate(target, data=name, evaluators=evaluators+[judge],
                                  experiment_prefix="cotizaciones", max_concurrency=1,
                                  metadata={"agent_model":settings.model,"judge_model":settings.judge_model,
                                            "reference_datetime":settings.reference_datetime.isoformat(), "dataset_hash":digest})
        rows = []
        for row in results:
            # Recupera las notas y explicaciones que los evaluadores asociaron a la ejecución.
            feedback = [r.model_dump() for r in row["evaluation_results"]["results"]]
            rows.append({"id":row["example"].metadata["case_id"], "output":row["run"].outputs, "feedback":feedback})
    print("Experimento:", results.experiment_name)
    print("Abre el enlace del experimento mostrado por LangSmith para obtener capturas reales.")
    return write_report(rows, "langsmith")

if __name__ == "__main__":
    raise SystemExit(main())
