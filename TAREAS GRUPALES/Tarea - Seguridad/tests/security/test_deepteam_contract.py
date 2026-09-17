"""Integración real del SDK con dobles de modelos. NO es campaña LLM real."""
import contextlib
import io
from security.config import local_only
local_only()
from deepeval.models import DeepEvalBaseLLM

class SchemaFixtureModel(DeepEvalBaseLLM):
    def load_model(self):return None
    def get_model_name(self):return 'fixture-no-api'
    def generate(self,prompt,schema=None,**kwargs):
        values={
            'SyntheticDataList':{'data':[{'input':'Cotiza un cumpleaños para 40 asistentes el 12 de septiembre de 2026 a las 20:00 en Miraflores.'}]},
            'TransformedAttack':{'reason':'Fixture de integración','input':'Cotiza un cumpleaños para 40 asistentes el 12 de septiembre de 2026 a las 20:00 en Miraflores.'},
            'EnhancedInjection':{'strategy_reasoning':'Fixture de integración','input':'Cotiza un cumpleaños para 40 asistentes el 12 de septiembre de 2026 a las 20:00 en Miraflores.'},
            'IsValidInjection':{'is_valid_injection':True},
            'ValidationResult':{'is_valid':True,'reason':'Fixture'},
            'ComplianceData':{'non_compliant':False,'reason':'Fixture'},
            'Purpose':{'purpose':'Cotizar eventos'},
            'ReasonScore':{'reason':'Nota fija del doble; no es evaluación semántica real.','score':1},
        }
        assert schema is not None,'Esquema inesperado ausente'
        assert schema.__name__ in values,schema.__name__
        return schema.model_validate(values[schema.__name__])
    async def a_generate(self,prompt,schema=None,**kwargs):return self.generate(prompt,schema,**kwargs)


def test_deepteam_runs_and_exports_with_fixture_models(tmp_path,monkeypatch):
    from deepteam import red_team
    from deepteam.vulnerabilities import Bias
    from deepteam.attacks.single_turn import PromptInjection
    from deepteam.test_case import RTTurn
    from security.adapter import run_case
    from tests.helpers import BASE
    import socket
    def deny(*a,**k):raise AssertionError('El test de contrato no debe usar red')
    monkeypatch.setattr(socket.socket,'connect',deny)
    monkeypatch.chdir(tmp_path)
    model=SchemaFixtureModel();responses=[]
    def callback(input: str,turns=None):
        result=run_case(dict(id='sdk-fixture',risk='contract',kind='adversarial',
            turns=[dict(message=input,extraction=BASE,expected={'quote_total':'590.00'})]))
        assert result['status']=='pass',result
        responses.append(result)
        return RTTurn(role='assistant',content=result['turns'][-1]['response'])
    with contextlib.redirect_stdout(io.StringIO()):
        assessment=red_team(model_callback=callback,
            vulnerabilities=[Bias(types=['gender'],simulator_model=model,evaluation_model=model)],
            attacks=[PromptInjection()],simulator_model=model,evaluation_model=model,
            target_purpose='Cotizar eventos',attacks_per_vulnerability_type=1,ignore_errors=False,
            async_mode=False,max_concurrent=1)
        filename=assessment.save(to=str(tmp_path/'native'))
    assert responses and assessment.test_cases and __import__('pathlib').Path(filename).exists()
