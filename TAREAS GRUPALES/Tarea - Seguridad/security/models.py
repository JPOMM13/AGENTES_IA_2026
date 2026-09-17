"""Modelos DeepTeam con presupuesto conservador compartido; ninguna clave se exporta."""
import os
import threading
from security.config import Limits,local_only
local_only()
from deepeval.models import DeepEvalBaseLLM

class BudgetExceeded(RuntimeError): pass

class Budget:
    def __init__(self):
        self.max_calls=int(os.getenv('SECURITY_MAX_CAMPAIGN_CALLS','500'))
        self.max_output_tokens=int(os.getenv('SECURITY_MAX_CAMPAIGN_OUTPUT_TOKENS','600000'))
        if self.max_calls<1 or self.max_output_tokens<1: raise ValueError('Presupuesto debe ser positivo')
        self.calls=0;self.output_tokens_reserved=0;self.actual_tokens=0;self.lock=threading.Lock()
    def reserve(self,calls=1):
        with self.lock:
            tokens=calls*Limits.load().output_tokens
            if self.calls+calls>self.max_calls or self.output_tokens_reserved+tokens>self.max_output_tokens:
                raise BudgetExceeded('Presupuesto de campaña agotado')
            self.calls+=calls;self.output_tokens_reserved+=tokens
    def settle_target(self, reserved, result):
        # Ante error/timeout conservamos la reserva completa: consumo desconocido.
        if result["status"] == "error": return
        unused=max(0,reserved-result.get("api_calls",reserved))
        with self.lock:
            self.calls-=unused
            self.output_tokens_reserved-=unused*Limits.load().output_tokens
            self.actual_tokens+=result.get("tokens",0)
    def public(self):
        return {k:v for k,v in vars(self).items() if k!='lock'}

class BoundedModel(DeepEvalBaseLLM):
    def __init__(self,name,budget):
        self.budget=budget
        super().__init__(name)
    def load_model(self):
        from local_llm import OllamaChat
        return OllamaChat(self.name)
    def get_model_name(self): return self.name
    def generate(self,prompt,schema=None,**kwargs):
        self.budget.reserve()
        before=self.model.tokens
        result=self.model.generate([('user',prompt)],schema)
        self.budget.actual_tokens+=self.model.tokens-before
        return result
    async def a_generate(self,prompt,schema=None,**kwargs):
        return self.generate(prompt,schema,**kwargs)
