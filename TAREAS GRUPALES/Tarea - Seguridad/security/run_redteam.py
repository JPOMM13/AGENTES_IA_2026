"""CLI: fixtures offline o DeepTeam real; nunca presenta offline como red teaming LLM."""
import argparse
import json
import os
from security.config import ROOT,local_only,Limits
from security.adapter import run_case,verify_baseline
from security.storage import new_run,save,digest,finish


def prepare_online():
    from config import Settings
    from local_llm import check_models,local_url
    settings=Settings.load();local_only()
    os.environ.setdefault('OLLAMA_MODEL',settings.model)
    os.environ.setdefault('SECURITY_SIMULATOR_MODEL',settings.model)
    os.environ.setdefault('SECURITY_JUDGE_MODEL',settings.model)
    check_models([os.environ[k] for k in ('OLLAMA_MODEL','SECURITY_SIMULATOR_MODEL','SECURITY_JUDGE_MODEL')])
    return settings


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--offline',action='store_true');p.add_argument('--mode',choices=['baseline','hardened'],default='baseline')
    p.add_argument('--smoke',action='store_true')
    p.add_argument('--attacks-per-type',type=int,default=1,help='Ataques solicitados por tipo de vulnerabilidad (no es un requisito académico)')
    args=p.parse_args(argv)
    if args.attacks_per_type<1: p.error('--attacks-per-type debe ser positivo')
    local_only();verify_baseline()
    directory,manifest=new_run(args.mode,args.offline)
    rows=json.loads((ROOT/'security/cases.json').read_text())
    manifest['fixed_corpus_sha256']=digest(rows)
    results=[];corpus=[]
    selected=([r for r in rows if r['kind']=='adversarial'][:1] if args.smoke else [r for r in rows if r['kind']=='adversarial']) if args.offline else []
    manifest['planned_fixed_cases']=len(selected)
    manifest['smoke']=args.smoke
    manifest['scope']='security_only'
    manifest['phase']='initial_discovery' if args.mode=='baseline' else 'optional_hardened' 
    manifest['attacks_per_type']=args.attacks_per_type
    try:
        from config import Settings
        settings=Settings.load();local_only()
        manifest['reference_datetime']=settings.reference_datetime.isoformat()
        if not args.offline:
            settings=prepare_online()
            from security.models import Budget
            budget=Budget()
            manifest['provider']='ollama'
            from local_llm import local_url
            manifest['ollama_base_url']=local_url()
            manifest['models']={k:os.getenv(k) for k in ('OLLAMA_MODEL','SECURITY_SIMULATOR_MODEL','SECURITY_JUDGE_MODEL')}
            manifest['budget']=budget.public()
        else:
            manifest['provider']='fixtures'
            from local_llm import local_url
            manifest['ollama_base_url']=local_url()
            manifest['models']={'target':'Scripted fixtures; no LLM'}
        save(directory/'manifest.json',manifest)
        print(json.dumps({'run':directory.name,'mode':args.mode,'offline':args.offline,'limits':manifest['limits'],'models':manifest['models'],'budget':manifest.get('budget')},ensure_ascii=False),flush=True)
        selected=([r for r in rows if r['kind']=='adversarial'][:1] if args.smoke else [r for r in rows if r['kind']=='adversarial']) if args.offline else []
        for case in selected:
            if not args.offline: budget.reserve(Limits.load().turn_calls*len(case['turns']))
            result=run_case(case,args.mode,args.offline);results.append(result)
            if not args.offline: budget.settle_target(Limits.load().turn_calls*len(case["turns"]),result)
            save(directory/'results.json',results)
            print(case['id']+': '+result['status'],flush=True)
        if not args.offline:
            from security.online import campaign
            manifest['deepteam_started']=True
            save(directory/'manifest.json',manifest)
            manifest['deepteam_cases']=campaign(args.mode,budget,results,corpus,directory,args.smoke,args.attacks_per_type)
            manifest['deepteam_executed']=True;manifest['budget']=budget.public()
            manifest['generated_evaluable']=sum(r['source']=='generated' and r['status'] in ('pass','fail') for r in results)
            if manifest['generated_evaluable']==0: raise RuntimeError('NoEvaluableDeepTeamCases')
        manifest['corpus_sha256']=digest(corpus)
        save(directory/'corpus.json',corpus)
        code=finish(directory,manifest,results)
    except (Exception,KeyboardInterrupt) as exc:
        # No imprimir excepciones del proveedor: pueden contener secretos o payloads.
        config_error=isinstance(exc,ValueError) and not results
        manifest['configuration_issue']=str(exc) if config_error and str(exc).startswith(('Falta ','Configura ')) else type(exc).__name__
        seen={r['id'] for r in results}
        for case in selected+corpus:
            if case['id'] not in seen:
                results.append(dict(id=case['id'],risk=case['risk'],kind=case['kind'],source=case.get('source','fixed'),status='not_run',turns=[],failures=[],errors=[]))
        for result in results:
            if result.get('source')=='generated' and not result.get('judge') and result['status']!='not_run':
                result['status']='error'
                result.setdefault('errors',[]).append('MissingDeepTeamGrade')
        if 'budget' in locals(): manifest['budget']=budget.public()
        code=finish(directory,manifest,results,type(exc).__name__)
        if config_error: code=2
        print('Ejecución pendiente/incompleta: '+manifest['configuration_issue'],flush=True)
    from security.report import write_report
    report=write_report(directory)
    print('Reporte: '+str(report),flush=True)
    print('Resultados: '+str(directory),flush=True)
    return code

if __name__=='__main__': raise SystemExit(main())
