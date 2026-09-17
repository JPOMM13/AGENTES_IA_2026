"""Controles reutilizados por la CLI y el grafo, independientes de DeepTeam."""
import html
import re
import signal
import threading
import unicodedata
from contextlib import contextmanager

CANARIES = ('CANARY_PRIVATE_CUSTOMER_A', 'CANARY_PRIVATE_SYSTEM', 'CANARY_PRIVATE_ERROR')


def sanitize(text):
    text = str(text)
    text = re.sub(r'\x1b\][^\x07]*(?:\x07|\x1b\\)', '', text)
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
    text = ''.join(c for c in text if c in '\n\t' or unicodedata.category(c) not in ('Cc', 'Cf'))
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[EMAIL]', text)
    text = re.sub(r'(?<!\w)(?:\+?\d[ -]?){9,15}(?!\w)', '[PHONE]', text)
    text = re.sub(r'\b(?:sk-|lsv2_)[A-Za-z0-9_-]+', '[SECRET]', text)
    for token in CANARIES:
        text = text.replace(token, '[CANARY]')
    return text


def public_text(text):
    # Plain text even in terminals, Markdown exports and later HTML previews.
    text = html.escape(sanitize(text), quote=True)
    text = re.sub(r'https?://', 'hxxps[:]//', text, flags=re.I)
    return text


def clean_tree(value):
    if isinstance(value, str): return sanitize(value)
    if isinstance(value, dict): return {sanitize(k):clean_tree(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)): return [clean_tree(v) for v in value]
    return value


def request_signal(message):
    text = ''.join(c for c in unicodedata.normalize('NFD', message.casefold()) if unicodedata.category(c) != 'Mn')
    # Remove only a narrow, explicit benign clause, not all text after a negation.
    text = re.sub(r'\bno (?:quiero|necesito|solicito) (?:un )?(?:descuento|rebaja)\b', '', text)
    patterns = [
        ('human_support', r'\b(asesor|humano|persona real)\b'),
        ('discount', r'\b(descuento|rebaja)\b'),
        ('payment', r'\b(pagar|pago|tarjeta|transferencia)\b'),
        ('purchase', r'\b(comprar|compra|reservar|reserva)\b'),
        ('complaint', r'\b(reclamo|queja)\b'),
        ('privacy', r'\b(ignora|inventa|inventado|contrasena|datos de otro|sin consentimiento|trusted_customer_id)\b'),
        ('exception', r'\b(excepcion|saltate)\b'),
    ]
    return next((reason for reason, p in patterns if re.search(p,text)), None)


class TurnDeadline(BaseException):
    """No lo absorben los handlers genéricos del grafo; corta el turno."""


@contextmanager
def deadline(seconds):
    # CLI local macOS/Linux. El harness además termina el subprocess completo.
    if not hasattr(signal, 'setitimer') or threading.current_thread() is not threading.main_thread():
        raise RuntimeError('Ejecutar el agente en proceso principal; el harness proporciona aislamiento.')
    def expire(*_): raise TurnDeadline()
    handler = signal.signal(signal.SIGALRM, expire)
    old_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *old_timer)
        signal.signal(signal.SIGALRM, handler)
