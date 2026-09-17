"""Fixtures exclusivamente para tests de seguridad, sin evaluación funcional."""
from agent.state import Extraction
from agent.prompts import OPENINGS
BASE=dict(intent='quotation',event_type='cumpleanos',attendees=40,event_date='2026-09-12T20:00:00-05:00',location='Miraflores')
class ScriptedInterpreter:
    def __init__(self,turns):self.by_message={t['message']:t['extraction'] for t in turns}
    def extract(self,message,*args):return Extraction.model_validate(self.by_message[message])
    def opening(self,*args):return OPENINGS[1]
