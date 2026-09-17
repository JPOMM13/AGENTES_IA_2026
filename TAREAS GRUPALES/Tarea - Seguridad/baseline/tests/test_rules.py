import os
os.environ["LANGSMITH_TRACING"] = "false"
from copy import deepcopy
from datetime import timedelta
import pytest
from config import Settings
from agent.graph import QuoteAgent
from agent.state import Extraction
from agent import tools
from repositories.json_repository import JsonDataRepository
from evaluation.dataset import cases, BASE
from evaluation.run_evaluation import target_for, ScriptedInterpreter
from evaluation.evaluators import scores, make_evaluators, make_judge

# Prepara la configuración compartida que necesitan las pruebas.
@pytest.fixture
def settings():
    return Settings.load()

# Prepara un repositorio mock nuevo para cada prueba que lo solicita.
@pytest.fixture
def repo(settings):
    return JsonDataRepository(settings.data_path)

# Ejecuta cada caso con extracción simulada y exige que cumpla las once métricas determinísticas.
@pytest.mark.parametrize("case", cases(), ids=lambda c:c["id"])
def test_dataset_rules(case, settings, repo):
    output = target_for(settings, True)(case["inputs"])
    result = scores(output, case["outputs"], repo, settings.reference_datetime)
    assert all(result.values()), result

# Altera un campo de una salida válida y comprueba que la métrica correspondiente detecte el error.
@pytest.mark.parametrize("field,value,metric", [
    ("intent", "information", "intent_accuracy"),
    ("missing_fields", ["location"], "required_fields_detection"),
    ("tools_called", [], "tool_selection"),
    ("validated_coverage", False, "coverage_compliance"),
    ("validated_availability", False, "availability_compliance"),
    ("needs_human", True, "handoff_accuracy"),
    ("preferences_used", ["grande"], "consent_compliance"),
    ("attendees", 1000, "business_rule_compliance"),
])
def test_metrics_reject_mutated_output(settings, repo, field, value, metric):
    case = cases()[0]
    out = target_for(settings, True)(case["inputs"])
    out[field] = value
    assert not scores(out, case["outputs"], repo, settings.reference_datetime)[metric]

# Adultera importes, texto o producto para verificar que el evaluador no apruebe cotizaciones incorrectas.
@pytest.mark.parametrize("mutation", ["total", "text", "bare_price", "inactive", "missing_quote"])
def test_corrupted_quotes(settings, repo, mutation):
    case = cases()[0]
    out = target_for(settings, True)(case["inputs"])
    if mutation == "total":
        out["quote"]["total"] = "1.00"
    elif mutation == "text":
        out["response"] = out["response"].replace("590.00", "1.00")
    elif mutation == "bare_price":
        out["response"] += " Precio especial de 1 sol."
    elif mutation == "inactive":
        out["recommended_option"]["id"] = "P3"
    else:
        out["quote"] = None
    result = scores(out, case["outputs"], repo, settings.reference_datetime)
    assert not result["no_hallucinated_price"]
    if mutation == "inactive":
        assert not result["inactive_product_rejection"]


# Ejecuta una conversación simulada conservando estado y devuelve las salidas de todos sus turnos.
def run_turns(repo, settings, turns, now=None):
    agent = QuoteAgent(repo, ScriptedInterpreter(turns), now or settings.reference_datetime)
    state = None
    outputs = []
    for t in turns:
        state = agent.respond(t["message"], state)
        outputs.append(state)
    return outputs


# Verifica que una fecha aportada después complete los datos sin perder el contexto de la conversación.
def test_missing_field_followup(settings, repo):
    turns = [{"message":"Sin fecha", "extraction":{**BASE, "event_date":None}},
             {"message":"El doce", "extraction":{"event_date":BASE["event_date"]}}]
    first, second = run_turns(repo, settings, turns)
    assert first["missing_fields"] == ["event_date"]
    assert second["quote"]["total"] == "590.00"
    assert len(second["messages"]) == 4
    assert len(first["messages"]) == 2

# Comprueba que un cambio incompatible elimine la cotización anterior y derive con el motivo esperado.
@pytest.mark.parametrize("patch,expected", [({"location":"Iquitos"}, "no_coverage"), ({"attendees":150},"no_catalog_option"), ({"event_date":"2026-09-07T20:00:00-05:00"},"lead_time")])
def test_change_invalidates_previous_quote(settings, repo, patch, expected):
    turns = [{"message":"Original", "extraction":BASE},
             {"message":"Cambiar", "extraction":{"intent":"modify_request", **patch}}]
    first, second = run_turns(repo, settings, turns)
    assert first["quote"]
    assert second["quote"] is None
    assert second["recommended_option"] is None
    assert second["handoff_reason"] == expected


# Verifica que retirar la ubicación elimine la cotización y vuelva a solicitar ese dato.
def test_clear_field(settings, repo):
    first, second = run_turns(repo, settings, [{"message":"Primero", "extraction":BASE},
        {"message":"Aún no sé dónde", "extraction":{"intent":"modify_request","clear_fields":["location"]}}])
    assert second["missing_fields"] == ["location"]
    assert second["quote"] is None


# Prueba la frontera: exactamente 72 horas permite cotizar y un segundo menos requiere derivación.
def test_exact_72_hours(settings, repo):
    from datetime import datetime
    now = datetime.fromisoformat(BASE["event_date"]) - timedelta(hours=72)
    result = run_turns(repo, settings, [{"message":"Evento", "extraction":BASE}], now)[0]
    assert result["quote"]
    result = run_turns(repo, settings, [{"message":"Evento", "extraction":BASE}], now+timedelta(seconds=1))[0]
    assert result["handoff_reason"] == "lead_time"


# Elimina el stock del día de recojo y comprueba que no se asuma disponibilidad.
def test_unknown_availability_fails_closed(settings, repo):
    repo._data["disponibilidad"] = [r for r in repo._data["disponibilidad"] if r["date"] != "2026-09-13"]
    result = run_turns(repo, settings, [{"message":"Evento", "extraction":BASE}])[0]
    assert result["handoff_reason"] == "no_availability"
    assert not result["quote"]


# Comprueba que solo un identificador autorizado y con consentimiento permita leer preferencias.
def test_consent_requires_trusted_identity(repo):
    assert repo.get_preferences(None) == []
    assert repo.get_preferences("C2") == []
    assert repo.get_preferences("C1") == ["grande"]


# Simula cinco fallos transitorios seguidos de éxito y verifica el límite de seis intentos totales.
def test_safe_retry_bound(settings, repo):
    calls = []
    original = repo.get_products
    # Simula una lectura que falla cinco veces y después devuelve el catálogo original.
    def flaky():
        calls.append(1)
        if len(calls) < 6:
            raise TimeoutError()
        return original()
    repo.get_products = flaky
    result = run_turns(repo, settings, [{"message":"Evento", "extraction":BASE}])[0]
    assert result["quote"] and len(calls) == 6


# Verifica que un error permanente provoque derivación sin reintentos.
def test_no_retry_permanent_error(settings, repo):
    calls = []
    # Simula un fallo permanente del repositorio y registra cuántas veces se intentó leer.
    def broken():
        calls.append(1)
        raise ValueError("Invalid repository")
    repo.get_products = broken
    result = run_turns(repo, settings, [{"message":"Evento", "extraction":BASE}])[0]
    assert result["handoff_reason"] == "persistent_failure" and len(calls) == 1


# Comprueba que informar no requiera datos del evento y que recomendar no emita una cotización.
def test_information_and_recommendation(settings, repo):
    info = run_turns(repo, settings, [{"message":"Qué haces", "extraction":{"intent":"information"}}])[0]
    assert info["current_stage"] == "information"
    rec = run_turns(repo, settings, [{"message":"Recomienda", "extraction":{**BASE,"intent":"recommendation"}}])[0]
    assert rec["recommended_option"] and rec["quote"] is None


# Comprueba que el presupuesto se compare con el precio incluido el impuesto.
def test_budget_with_tax(settings, repo):
    out = run_turns(repo, settings, [{"message":"Presupuesto", "extraction":{**BASE,"budget":589.99}}])[0]
    assert out["handoff_reason"] == "budget"


# Verifica que el esquema rechace campos extra de precio, consentimiento o identidad confiable.
def test_llm_cannot_set_price_or_consent():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Extraction.model_validate({"price":1,"consent":True,"trusted_customer_id":"C1"})


# Comprueba que entradas malformadas a los evaluadores den cero, nunca un aprobado.
def test_evaluators_fail_closed(settings, repo):
    for evaluator in make_evaluators(repo, settings.reference_datetime):
        assert evaluator({}, {})["score"] == 0


# Adapta los evaluadores al SDK y verifica sus resultados usando Run y Example locales, sin red.
def test_langsmith_evaluator_signatures(settings, repo):
    from langsmith.evaluation import run_evaluator
    from langsmith.schemas import Run, Example
    from uuid import uuid4
    from datetime import datetime, timezone
    case = cases()[0]
    output = target_for(settings, True)(case["inputs"])
    run = Run(id=uuid4(), name="test", start_time=datetime.now(timezone.utc), run_type="chain", inputs=case["inputs"], outputs=output)
    example = Example(id=uuid4(), dataset_id=uuid4(), inputs=case["inputs"], outputs=case["outputs"])
    for evaluator in make_evaluators(repo, settings.reference_datetime):
        result = run_evaluator(evaluator).evaluate_run(run, example)
        assert result.score == 1


# Sustituye el LLM por un doble para comprobar notas válidas y notas ausentes cuando falla.
def test_judge_schema_and_failure(monkeypatch, settings):
    from evaluation.evaluators import SemanticGrades
    from langsmith.evaluation import run_evaluator
    class FakeModel:
        fail = False
        # Acepta los argumentos del cliente simulado sin abrir ninguna conexión.
        def __init__(self, **kwargs): pass
        # Imita la configuración de salida estructurada y devuelve el mismo doble de prueba.
        def with_structured_output(self, schema): return self
        # Simula cuatro notas semánticas válidas o un timeout, según la condición de la prueba.
        def invoke(self, messages):
            if self.fail:
                raise TimeoutError()
            return SemanticGrades.model_validate({k:{"score":4,"explanation":"Respuesta útil."} for k in SemanticGrades.model_fields})
    import langchain_openai
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeModel)
    judge = make_judge(settings)
    run_evaluator(judge)  # El SDK acepta la firma inputs/outputs.
    result = judge(cases()[0]["inputs"], {"response":"Respuesta"})
    assert len(result["results"]) == 4
    assert all(r["score"] == 4 for r in result["results"])
    FakeModel.fail = True
    result = judge(cases()[0]["inputs"], {"response":"Respuesta"})
    assert all(r["score"] is None for r in result["results"])


# Comprueba que un reporte sin métricas se clasifique como incompleto y devuelva código de fallo.
def test_empty_feedback_never_passes(monkeypatch, tmp_path):
    import evaluation.run_evaluation as runner
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    assert runner.write_report([{"id":"broken", "feedback":[]}], "langsmith") == 1


# Verifica que los patrones de correo y teléfono se oculten antes del procesamiento.
def test_contact_redaction():
    from agent.graph import redact
    assert "persona@example.com" not in redact("Mi correo persona@example.com")
    assert "999888777" not in redact("Mi teléfono 999888777")


# Distingue saldo agotado de límites transitorios sin exponer el texto del error ni credenciales.
@pytest.mark.parametrize("code,body,status,expected", [
    ("insufficient_quota", None, 429, "cuota o saldo"),
    (None, {"error":{"type":"insufficient_quota", "code":"credit_balance_exhausted"}}, 429, "cuota o saldo"),
    (None, {"code":"credit_balance_exhausted"}, 429, "cuota o saldo"),
    ("rate_limit_exceeded", None, 429, "limitó las solicitudes"),
    (None, None, 401, "autenticación"),
    (None, None, 400, "parámetros"),
    (None, None, 404, "modelo no disponible"),
    (None, None, None, "revisa la traza"),
])
def test_judge_error_diagnostics(code, body, status, expected):
    from evaluation.evaluators import judge_error_comment
    exc = Exception("SECRET_FOR_TEST_DO_NOT_EXPOSE")
    exc.code, exc.body, exc.status_code = code, body, status
    comment = judge_error_comment(exc)
    assert expected in comment
    assert "SECRET_FOR_TEST_DO_NOT_EXPOSE" not in comment
    assert "no se asignó nota" in comment
