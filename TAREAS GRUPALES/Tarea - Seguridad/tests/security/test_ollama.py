import pytest
from pydantic import BaseModel
from local_llm import OllamaChat,local_url,check_models

class Answer(BaseModel):
    answer:str

@pytest.mark.parametrize('url',['https://api.openai.com','http://192.168.1.2:11434','http://user:pass@localhost:11434','http://localhost:11434/api','http://localhost:11434?x=1'])
def test_remote_endpoints_forbidden(monkeypatch,url):
    monkeypatch.setenv('OLLAMA_BASE_URL',url)
    with pytest.raises(ValueError):local_url()


def test_native_schema_and_usage(monkeypatch):
    import httpx
    seen=[]
    def respond(request):
        import json
        seen.append(json.loads(request.content))
        assert request.url.host=='127.0.0.1'
        return httpx.Response(200,json={'message':{'content':'{"answer":"local"}'},'done':True,'prompt_eval_count':11,'eval_count':4})
    original=httpx.Client
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    chat=OllamaChat('llama3.2:latest')
    assert chat.generate([('human','hola')],Answer).answer=='local'
    assert chat.tokens==15 and chat.calls==1
    assert seen[0]['format']==Answer.model_json_schema() and seen[0]['stream'] is False


def test_cloud_model_metadata_rejected(monkeypatch):
    import httpx
    original=httpx.Client
    transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'remote_host':'cloud.example'}))
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:original(transport=transport,**kwargs))
    with pytest.raises(ValueError,match='localmente'):check_models(['remote'])
