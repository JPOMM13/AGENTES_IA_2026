"""Cliente nativo Ollama: solo loopback, sin proxies, redirects ni fallback cloud."""
import json
import os
from urllib.parse import urlparse
import httpx
from pydantic import BaseModel
from typing import Literal
from security.config import Limits


def local_url():
    url=os.getenv('OLLAMA_BASE_URL','http://127.0.0.1:11434').rstrip('/')
    p=urlparse(url)
    if p.scheme!='http' or p.hostname not in ('localhost','127.0.0.1','::1') or p.username or p.password or p.path or p.query or p.fragment:
        raise ValueError('OLLAMA_BASE_URL debe ser HTTP local (localhost/127.0.0.1/::1), sin credenciales ni rutas.')
    return url


def check_models(names):
    with httpx.Client(base_url=local_url(),trust_env=False,follow_redirects=False,timeout=10) as client:
        try:
            for name in set(names):
                res=client.post('/api/show',json={'model':name})
                if res.status_code==404: raise ValueError('Modelo no instalado en Ollama: '+name)
                res.raise_for_status();info=res.json()
                if info.get('remote_host') or info.get('remote_model') or 'cloud' in name.lower():
                    raise ValueError('Solo se permiten modelos ejecutados localmente en Ollama.')
        except httpx.HTTPError:
            raise ValueError('No se pudo consultar Ollama local. Abre Ollama o ejecuta ollama serve.') from None


class OllamaChat:
    def __init__(self,model,**kwargs):
        if 'cloud' in model.lower(): raise ValueError('Modelo cloud no permitido')
        self.model=model;self.calls=0;self.tokens=0;self.schema=None
    def with_structured_output(self,schema):
        parent=self
        class Structured:
            def invoke(self,messages): return parent.generate(messages,schema)
        return Structured()
    def generate(self,messages,schema=None):
        limits=Limits.load()
        self.calls+=1
        payload={'model':self.model,'messages':[{'role':('user' if role=='human' else role),'content':text} for role,text in messages],
                 'stream':False,'options':{'temperature':0,'num_predict':limits.output_tokens,'num_ctx':8192},'keep_alive':'10m'}
        if schema:
            payload['format']=schema.model_json_schema()
            payload['messages'].insert(0,{'role':'system','content':'Devuelve exclusivamente un objeto JSON que cumpla este esquema. No copies sus definiciones; completa los campos con valores correspondientes a la solicitud: '+json.dumps(payload['format'],ensure_ascii=False)})
        try:
            with httpx.Client(trust_env=False,follow_redirects=False,timeout=limits.call_seconds) as client:
                response=client.post(local_url()+'/api/chat',json=payload)
                response.raise_for_status();data=response.json()
        except httpx.TimeoutException: raise TimeoutError('OllamaTimeout') from None
        except httpx.ConnectError: raise ConnectionError('OllamaUnavailable') from None
        except httpx.HTTPError: raise RuntimeError('OllamaRequestFailed') from None
        self.tokens+=data.get('prompt_eval_count',0)+data.get('eval_count',0)
        content=data.get('message',{}).get('content','')
        if not content or not data.get('done'): raise ValueError('OllamaIncompleteResponse')
        return schema.model_validate_json(content) if schema else content


class Opening(BaseModel):
    choice:Literal[0,1,2]

class OllamaInterpreter:
    def __init__(self,settings):
        from agent.state import Extraction
        self.llm=OllamaChat(settings.model)
        self.extractor=self.llm.with_structured_output(Extraction)
        self.calls=0
    def reset_budget(self):
        self.calls=0;self.llm.calls=0;self.llm.tokens=0
    def _charge(self):
        if self.calls>=Limits.load().turn_calls: raise RuntimeError('Presupuesto de llamadas por turno agotado')
        self.calls+=1
    def extract(self,message,state,now,event_types):
        from agent.prompts import EXTRACT_PROMPT
        self._charge()
        context={k:state.get(k) for k in ('event_type','attendees','event_date','location','budget','product_categories')}
        return self.extractor.invoke([('system',EXTRACT_PROMPT+' Intenciones: quotation cuando pide cotizar o un presupuesto para un evento; information solo para preguntas generales sobre capacidades; modify_request al cambiar datos; recommendation al pedir recomendar; human_support al pedir asesor. Extrae todos los datos explícitos, sin reemplazarlos por valores por defecto del esquema.'),('human',json.dumps({'reference_datetime':now.isoformat(),'event_types':event_types,'previous_state':context,'message':message},ensure_ascii=False))])
    def opening(self,response):
        from agent.prompts import OPENINGS
        self._charge()
        result=self.llm.with_structured_output(Opening).invoke([('system','Selecciona una apertura aprobada y devuelve su índice: '+str(OPENINGS)),('human',response)])
        return OPENINGS[result.choice]
