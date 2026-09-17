"""Prueba manual de un ataque contra el agente original con Ollama local."""
import argparse
from security.run_redteam import prepare_online
from security.adapter import run_case


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--message',help='Ataque a probar; si se omite se solicita por terminal')
    args=parser.parse_args(argv)
    prepare_online()
    message=args.message if args.message is not None else input('Ataque: ')
    if not message.strip():
        parser.error('Escribe un mensaje')
    case=dict(id='manual-baseline',risk='Manual',kind='adversarial',source='manual',
              turns=[dict(message=message,session='A',expected={})])
    result=run_case(case,mode='baseline',offline=False)
    for turn in result.get('turns',[]):
        print('\nAgente original:\n'+turn['response'])
        print('\nHerramientas: '+', '.join(turn.get('tools',[])))
    print('\nVerificaciones determinísticas: '+result['status'])
    for failure in result.get('failures',[]):print(failure)
    for error in result.get('errors',[]):print('Error: '+error)
    print('Prueba manual sin juez DeepTeam. Un pass no demuestra ausencia de vulnerabilidades. Cada ejecución inicia una sesión nueva.')
    return 2 if result['status']=='error' else 0


if __name__=='__main__':raise SystemExit(main())
