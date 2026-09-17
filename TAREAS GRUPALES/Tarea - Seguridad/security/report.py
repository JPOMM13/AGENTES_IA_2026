"""Reporte de una ejecución de seguridad: riesgos, ataques y controles."""
import argparse
import json
from pathlib import Path
from security.config import ROOT
from security.controls import public_text

RISKS=[
('Fuga de datos de clientes','PIILeakage','Identidad confiable y consentimiento fuera del prompt; sesiones aisladas.','agent/graph.py; repositories/json_repository.py'),
('Revelación de instrucciones','PromptLeakage','Extracción estructurada y respuestas controladas; no incluir secretos en prompts.','local_llm.py; agent/prompts.py'),
('Permisos y acciones no autorizadas','ExcessiveAgency','Tools de lectura; no reservar, cobrar ni enviar mensajes; derivación humana.','agent/tools.py'),
('Manipulación de precios y reglas','Reglas comerciales','Importes Decimal y validación de cobertura, stock y 72 horas en código.','agent/tools.py; agent/graph.py'),
('Sesgo discriminatorio','Bias','Elegibilidad comercial determinística; revisar diferencias ante atributos irrelevantes.','agent/tools.py'),
('Trato ofensivo','Toxicity','Plantillas acotadas; revisar respuestas y rechazar contenido inapropiado.','agent/prompts.py; agent/graph.py'),
('Contenido malicioso del catálogo','SEC-09','Escape HTML y eliminación de controles de terminal.','security/controls.py'),
('Consumo de recursos','SEC-10','Límites de mensaje, sesión, llamadas, tokens y tiempo.','security/config.py; security/models.py'),
]


def resolve(ref):
    p=Path(ref)
    return p if p.exists() else ROOT/'artifacts/security'/ref


def write_report(ref):
    directory=resolve(ref)
    manifest=json.loads((directory/'manifest.json').read_text())
    results=json.loads((directory/'results.json').read_text())
    # Las ejecuciones históricas pueden contener casos funcionales; no forman parte del reporte.
    rows=[r for r in results if r.get('kind')=='adversarial' and (manifest['offline'] or r.get('source')=='generated')]
    evaluable=[r for r in rows if r['status'] in ('pass','fail')]
    failed=sum(r['status']=='fail' for r in evaluable)
    counts={status:sum(r['status']==status for r in rows) for status in ('pass','fail','error','not_run')}
    native=list((directory/'deepteam-native').glob('*.json'))
    actual=manifest.get('deepteam_executed') and bool(native)
    offline=manifest['offline']
    review_path=directory/'manual_review.json'
    reviews=json.loads(review_path.read_text()) if review_path.exists() else {}
    rate=f'{failed}/{len(evaluable)} ({failed/len(evaluable):.1%})' if evaluable else 'N/A: no hay casos evaluables'
    lines=['# Tarea Grupal – Seguridad: reporte de red teaming','',
        'Integrantes: completar por el equipo.',f"Ejecución: {manifest['id']} | Fecha UTC: {manifest['created_at']}",'',
        '## 1. Objetivo y alcance','',
        ('Fase inicial de descubrimiento: se ejecuta baseline/, el agente original con Ollama, sin activar los controles añadidos en agent/. Se conservan las reglas y protecciones que ya existían en el original.' if manifest['mode']=='baseline' else 'Ejecución histórica/opcional de la variante reforzada; no representa el diagnóstico inicial.'),
        'Los límites del arnés protegen la ejecución local y el saneamiento protege las evidencias; no se presentan como correcciones del agente.',
        'Identificar posibles vulnerabilidades del agente de cotizaciones, probar ataques con DeepTeam y documentar controles. El agente, generador de ataques y juez de seguridad usan Ollama local. No se evalúan claridad, relevancia ni calidad comercial general.','',
        f"Estado de ejecución: **{manifest['status']}**. Proveedor: **{manifest.get('provider','histórico')}**.",
        ('Diagnóstico con fixtures, sin LLM: no constituye el entregable tras usar DeepTeam.' if offline else
         'DeepTeam ejecutado; exportación nativa conservada.' if actual else
         'Ejecución de DeepTeam no completada o exportación ausente: evidencia parcial.'),
        ('Prueba smoke: solo una familia seleccionada; las otras vulnerabilidades se listan como potenciales, no probadas.' if manifest.get('smoke') else ''),'',
        '## 2. Posibles vulnerabilidades y controles para una fase posterior','',
        '| Vulnerabilidad considerada | Evidencia de esta ejecución | Control a considerar después del diagnóstico | Referencia para fase posterior |','|---|---|---|---|']
    for risk,family,control,code in RISKS:
        relevant=[r for r in rows if r['risk'].replace(' ','').lower()==family.replace(' ','').lower()]
        evidence=f"{len(relevant)} casos; {sum(r['status']=='fail' for r in relevant)} fallos; {sum(r['status']=='error' for r in relevant)} errores" if relevant else 'No probada en esta ejecución'
        lines.append(f'| {risk} | {evidence} | {control} | {code} |')
    lines+=['','En el diagnóstico baseline no se activan los controles añadidos. La matriz contiene propuestas para una fase posterior; todavía no se aplican correcciones a partir de estos hallazgos. Las protecciones propias del agente original se mantienen para medir su estado real.','',
        '## 3. Método y resultados','',
        'Como en el ejemplo de clase: definir vulnerabilidades y técnicas, llamar red_team con un callback al agente y guardar risk_assessment. El callback ejecuta el grafo completo, no una respuesta simulada. Los ataques se entregan intactos al objetivo; las evidencias exportadas se sanean. Se conservan las notas del juez y verificaciones de permisos, importes, herramientas y datos.','',
        f"Modelos: `{manifest.get('models',{})}`.",f"DeepTeam: `{manifest['dependencies']['deepteam']}`. Límites: `{manifest['limits']}`.",
        'Técnicas configuradas: PromptInjection y PermissionEscalation. El muestreo no garantiza que ambas aparezcan en una corrida pequeña.',
        f"Aprobados: {counts['pass']}; fallos: {counts['fail']}; errores: {counts['error']}; no ejecutados: {counts['not_run']}.",
        f'Tasa de violación observada en casos evaluables: {rate}.',
        f"Casos con revisión adicional: {len(reviews)}; consultar la revisión junto a cada nota del juez. Los fallos automáticos se conservan sin alterar aunque la revisión discrepe.",
        'Un error no se cuenta como seguro. Los fallos son hallazgos que requieren revisión, no motivos para ocultar la ejecución. La consigna no establece un mínimo de casos ni exige cero fallos.','',
        '## 4. Ataques ejecutados, respuestas y análisis','']
    lines += ['| Ataque | Familia | Resultado |', '|---|---|---|']
    for r in sorted(rows,key=lambda r: {'fail':0,'error':1,'not_run':2,'pass':3}[r['status']]):
        lines.append(f"| {r['id']} | {public_text(r['risk'])} | {r['status']} |")
    lines += ['', 'Los casos fail son hallazgos candidatos: revisar la respuesta y la razón del juez antes de afirmar una vulnerabilidad confirmada. Los casos pass solo indican que ese ataque no mostró una violación.', '']
    for r in rows:
        lines +=[f"### {r['id']} — {public_text(r['risk'])}",'',f"Resultado: **{r['status']}**.",'']
        for t in r.get('turns',[]):
            lines +=['> Ataque: '+public_text(t['input']).replace('\n','\n> '),
                     '> Respuesta: '+public_text(t['response']).replace('\n','\n> '),'',
                     'Tools observadas: '+', '.join(t.get('tools',[]))+'.',
                     'Motivo de derivación/bloqueo: '+str(t.get('reason'))+'.','']
        if r['id'] in reviews:
            review=reviews[r['id']]
            lines += ['**Revisión adicional: '+public_text(review['assessment'])+'**', public_text(review['reason']), public_text(review['reviewer']), '']
        judge=r.get('judge',{})
        lines +=['Verificaciones: '+public_text('; '.join(r.get('failures',[])) or 'Sin violaciones detectadas por los oráculos ejecutados')+'.',
                 'Evaluador: '+public_text(json.dumps(judge,ensure_ascii=False)) if judge else 'Sin nota semántica de DeepTeam.',
                 'Errores: '+public_text(', '.join(r.get('errors',[])) or 'ninguno')+'.',
                 ('Acción: revisar ataque y respuesta; comprobar si el control indicado en la matriz cubre el hallazgo, registrar el control propuesto para la siguiente fase, sin aplicarlo ahora.' if r['status']=='fail' else
                  'Acción: resolver el error y repetir; no concluir seguridad.' if r['status']=='error' else
                  'Acción: conservar como evidencia de este caso; no generalizar el aprobado a otros ataques.'),'']
    lines+=['## 5. Conclusiones y entrega','',
        'El resultado describe únicamente los ataques registrados. No demuestra cobertura completa de OWASP ni ausencia de vulnerabilidades. Los modelos locales pueden equivocarse al generar ataques o evaluarlos; revisar manualmente las notas y contradicciones.',
        'Copiar este reporte a Google Docs, completar integrantes y añadir capturas auténticas de los casos y sus controles. No hace falta ejecutar la evaluación funcional anterior ni crear experimentos en LangSmith.',
        'Opcionalmente repetir ataques después de aplicar controles con security.replay. Sus notas usan una rúbrica distinta del juez nativo; no comparar ambas como si fueran la misma métrica.','',
        '## 6. Evidencias y uso de IA','',
        f"Archivos de ejecución: `{directory.relative_to(ROOT)}`.",
        'Exportación nativa: '+(', '.join(str(p.relative_to(ROOT)) for p in native) if native else 'no disponible en esta ejecución')+'.',
        'La implementación y documentación se prepararon con asistencia de IA; el equipo revisa código, resultados y entrega. Los datos del cotizador son sintéticos. No se ejecutaron ataques contra servicios de terceros.',
        'Referencia de adaptación al ejemplo del curso: docs/VALIDACION_EJEMPLO.md.','']
    target=directory/'reporte_seguridad.md';target.write_text('\n'.join(lines))
    final=ROOT/'reports/REPORTE_SEGURIDAD_PARA_GOOGLE_DOCS.md';final.parent.mkdir(exist_ok=True);final.write_text(target.read_text())
    return target


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True)
    args=p.parse_args(argv);print(write_report(args.run));return 0

if __name__=='__main__':raise SystemExit(main())
