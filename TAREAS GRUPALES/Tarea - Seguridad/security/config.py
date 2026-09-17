"""Configuración del laboratorio sin secretos en los manifiestos."""
import os
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Limits:
    message_chars: int = 4000
    session_turns: int = 20
    history_chars: int = 24000
    call_seconds: int = 90
    turn_seconds: int = 240
    retries: int = 2
    output_tokens: int = 1200
    turn_calls: int = 8

    @classmethod
    def load(cls):
        values = {k: int(os.getenv('SECURITY_' + k.upper(), v.default))
                  for k, v in cls.__dataclass_fields__.items()}
        if any(v < 0 for v in values.values()) or any(v == 0 for k,v in values.items() if k != 'retries'):
            raise ValueError('Los límites de seguridad deben ser positivos (retries admite cero).')
        return cls(**values)

    def public(self):
        return asdict(self)


def local_only():
    # También después de cargar .env: la campaña no sube resultados ni trazas.
    os.environ.update(LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false',
                      DEEPTEAM_TELEMETRY_OPT_OUT='YES', DEEPEVAL_TELEMETRY_OPT_OUT='YES',
                      TELEMETRY_OPT_OUT='YES', ERROR_REPORTING='NO')
    os.environ.pop('CONFIDENT_API_KEY', None)
