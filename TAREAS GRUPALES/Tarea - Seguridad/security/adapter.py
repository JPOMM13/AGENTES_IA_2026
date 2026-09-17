"""Llama al grafo real en un proceso independiente y acota su duración."""
import hashlib
import json
import os
import subprocess
import sys
from security.config import ROOT,Limits,local_only


def verify_baseline():
    manifest=json.loads((ROOT/'baseline/manifest.json').read_text())
    for path,expected in manifest['files'].items():
        if hashlib.sha256((ROOT/'baseline'/path).read_bytes()).hexdigest()!=expected:
            raise ValueError('La instantánea base fue modificada: '+path)
    return manifest


def run_case(case,mode='hardened',offline=True):
    if mode not in ('baseline','hardened'): raise ValueError('Modo inválido')
    if mode=='baseline': verify_baseline()
    local_only()
    limits=Limits.load()
    try:
        proc=subprocess.run([sys.executable,str(ROOT/'security/worker.py'),mode],
                            input=json.dumps(dict(case=case,offline=offline)),text=True,
                            capture_output=True,cwd=ROOT,env=os.environ.copy(),
                            timeout=limits.turn_seconds*len(case['turns'])+10)
        if proc.returncode: raise RuntimeError('worker_exit')
        result=json.loads(proc.stdout)
    except (subprocess.TimeoutExpired,ValueError,RuntimeError) as exc:
        result=dict(status='error',errors=[type(exc).__name__],failures=[],turns=[],api_calls=0,tokens=0)
    result.update(id=case['id'],risk=case['risk'],kind=case['kind'],source=case.get('source','fixed'))
    return result
