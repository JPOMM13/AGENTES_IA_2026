"""Resultados verificables con saneamiento antes de persistir."""
from datetime import datetime, timezone
from importlib.metadata import version
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from security.config import ROOT,Limits
from security.controls import clean_tree


def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def save(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(clean_tree(obj),ensure_ascii=False,indent=2)+'\n');temp.replace(path)


def new_run(mode,offline,source=None):
    rid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+mode+'-'+uuid4().hex[:6]
    directory=ROOT/'artifacts/security'/rid;directory.mkdir(parents=True)
    code={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
          for folder in ('agent','repositories','security') for p in (ROOT/folder).glob('*.py')}
    code['local_llm.py']=hashlib.sha256((ROOT/'local_llm.py').read_bytes()).hexdigest()
    manifest=dict(id=rid,mode=mode,offline=offline,status='running',created_at=datetime.now(timezone.utc).isoformat(),
                  source=source,limits=Limits.load().public(),
                  dependencies={p:version(p) for p in ('deepteam','deepeval','langgraph','langchain-openai','pydantic')},
                  code_hashes=code,baseline_manifest_sha256=hashlib.sha256((ROOT/'baseline/manifest.json').read_bytes()).hexdigest(),
                  data_sha256=hashlib.sha256((ROOT/'data/mock_data_eventos.json').read_bytes()).hexdigest(),
                  remote_tracing=False,deepteam_executed=False,
                  limits_scope='Límites propuestos y harness; la base preserva cinco reintentos y no incorpora límites internos de entrada/sesión.')
    save(directory/'manifest.json',manifest)
    save(directory/'corpus.json',[])
    return directory,manifest


def metrics(results):
    def group(rows):
        evaluated=[r for r in rows if r['status'] in ('pass','fail')]
        failed=sum(r['status']=='fail' for r in evaluated)
        return dict(attempted=len(rows),evaluated=len(evaluated),failed=failed,
                    errors=sum(r['status']=='error' for r in rows),
                    not_run=sum(r['status']=='not_run' for r in rows),
                    rate=failed/len(evaluated) if evaluated else None)
    return dict(adversarial=group([r for r in results if r['kind']=='adversarial']),
                benign=group([r for r in results if r['kind']=='benign']),
                by_risk={risk:group([r for r in results if r['risk']==risk]) for risk in sorted({r['risk'] for r in results})})


def finish(directory,manifest,results,error=None):
    manifest['metrics']=metrics(results)
    manifest['status']='incomplete' if error or any(r['status'] in ('error','not_run') for r in results) else 'completed'
    if error: manifest['error']=error
    save(directory/'results.json',results);save(directory/'manifest.json',manifest)
    if manifest['status']=='incomplete': return 3
    return 1 if any(r['status']=='fail' for r in results) else 0
