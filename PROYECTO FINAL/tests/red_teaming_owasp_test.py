"""
campana_owasp.py
----------------
Campaña completa de red teaming sobre el agente "Tus Eventos".
Cubre las vulnerabilidades más relevantes para un agente de ventas
mapeadas al OWASP Top 10 para LLM (edición 2025).

Costo estimado: medio-alto  |  Tiempo: 10–20 min
Ejecuta smoke_test.py primero para verificar que todo funciona.
"""

import sys
from pathlib import Path
from datetime import datetime

# Agrega la raíz del proyecto al path para que "from tests.eventos_agent import ..."
# funcione independientemente de desde dónde se ejecute el script.
_PROYECTO_ROOT = Path(__file__).resolve().parents[1]
if str(_PROYECTO_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROYECTO_ROOT))

from deepteam import red_team
from deepteam.vulnerabilities import Bias, Toxicity, Hallucination, GoalTheft
from deepteam.attacks.single_turn import (
    PromptInjection,
    PermissionEscalation,
    EmotionalManipulation,
)

#from eventos_agent import agent_invoke
from tests.red_teaming_eventos_agent import agent_invoke

# ── Directorio de resultados ─────────────────────────────────────────────────

RESULTADOS = Path("./resultados")
RESULTADOS.mkdir(exist_ok=True)


# ── Callback ─────────────────────────────────────────────────────────────────

async def model_callback(input_text: str) -> str:
    """Envuelve al agente con el contrato que DeepTeam necesita."""
    return agent_invoke(input_text)


# ── Vulnerabilidades ─────────────────────────────────────────────────────────
#
# Mapeadas a OWASP Top 10 LLM 2025:
#
# LLM01 – Prompt Injection          → PromptInjection
# LLM02 – Sensitive Info Disclosure → PromptInjection (exfiltración)
# LLM06 – Excessive Agency          → PermissionEscalation
# LLM09 – Misinformation            → Hallucination
# + Bias, Toxicity y GoalTheft como riesgos transversales del agente de ventas

vulnerabilidades = [
    # Alucinaciones: ¿inventa precios, APIs o condiciones que no existen?
    # → Cubre LLM09 (Misinformation)
    Hallucination(types=["fake_citations", "fake_apis"]),

    # Sesgo discriminatorio en respuestas de ventas
    # → Riesgo reputacional directo para Tus Eventos
    Bias(types=["race", "gender", "politics"]),

    # Contenido tóxico ante usuarios agresivos
    # → ¿El agente mantiene el tono profesional bajo presión?
    Toxicity(types=["profanity", "threats"]),

    # Robo de objetivos: ¿puede un atacante hacer que el agente actúe
    # fuera de su rol de cotizador?
    # → Cubre LLM06 (Excessive Agency)
    GoalTheft(types=["social_engineering"]),
]


# ── Ataques ───────────────────────────────────────────────────────────────────
#
# weight controla la probabilidad de selección relativa de cada técnica.

ataques = [
    # LLM01 / LLM02: inyectar instrucciones malignas en el input
    PromptInjection(weight=3),

    # LLM06: intentar obtener capacidades no autorizadas
    # (procesar pagos, dar descuentos, revelar el system prompt)
    PermissionEscalation(weight=2),

    # Presión emocional para saltarse las reglas del agente
    EmotionalManipulation(weight=2),
]


# ── Ejecución ────────────────────────────────────────────────────────────────

def main():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    print("=" * 70)
    print("  🔴 CAMPAÑA OWASP — Red Teaming | Agente Tus Eventos")
    print(f"  Inicio: {timestamp}")
    print("=" * 70)
    print(f"\n  Vulnerabilidades : {len(vulnerabilidades)}")
    print(f"  Técnicas de ataque: {len(ataques)}")
    print(f"  Escenarios totales: ~{len(vulnerabilidades) * len(ataques)}")
    print("\n  Esto puede tomar varios minutos y consumir tokens.")
    print("  Monitorea tu uso en platform.openai.com\n")
    print("=" * 70)

    resultado = red_team(
        model_callback=model_callback,
        vulnerabilities=vulnerabilidades,
        attacks=ataques,
    )

    # ── Reporte en consola ───────────────────────────────────────────────────

    print("\n\n" + "=" * 70)
    print("  ✅ CAMPAÑA COMPLETADA")
    print("=" * 70)

    print("\n📊 RESUMEN EJECUTIVO")
    print("-" * 70)
    print(resultado.overview)

    print("\n📋 CASOS DE PRUEBA")
    print("-" * 70)
    for i, caso in enumerate(resultado.test_cases, 1):
        print(f"\n  {i}. {caso}")

    # ── Reporte OWASP ────────────────────────────────────────────────────────

    reporte = f"""REPORTE DE RED TEAMING — AGENTE TUS EVENTOS
Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{'=' * 70}
RESUMEN EJECUTIVO
{'=' * 70}
{resultado.overview}

{'=' * 70}
COBERTURA OWASP TOP 10 LLM 2025
{'=' * 70}

ID        Riesgo                          Técnica usada            Estado
--------  ------------------------------  -----------------------  -------------------------
LLM01     Prompt Injection                PromptInjection          Testeado automáticamente
LLM02     Sensitive Information Disclose  PromptInjection          Testeado automáticamente
LLM03     Supply Chain                    —                        No cubierto (revisión manual)
LLM04     Data and Model Poisoning        —                        No cubierto (revisión manual)
LLM05     Improper Output Handling        —                        No cubierto (revisión manual)
LLM06     Excessive Agency                PermissionEscalation     Testeado automáticamente
LLM07     System Prompt Leakage           PermissionEscalation     Testeado automáticamente
LLM08     Vector & Embedding Weaknesses   —                        No aplica (sin RAG)
LLM09     Misinformation                  Hallucination            Testeado automáticamente
LLM10     Unbounded Consumption           —                        Monitoreo manual recomendado

{'=' * 70}
VULNERABILIDADES TRANSVERSALES TESTEADAS
{'=' * 70}

Vulnerabilidad    Tipos                         Técnicas aplicadas
----------------  ----------------------------  ---------------------------------------
Bias              race, gender, politics        PromptInjection, EmotionalManipulation
Toxicity          profanity, threats            PromptInjection, EmotionalManipulation
GoalTheft         social_engineering            PermissionEscalation, EmotionalManipulation
Hallucination     fake_citations, fake_apis     PromptInjection

{'=' * 70}
LEYENDA DE ESTADO
{'=' * 70}

  Testeado automáticamente  → DeepTeam generó y evaluó casos de prueba reales.
  Revisión manual pendiente → No cubierto por las técnicas actuales; requiere
                              inspección humana del código, dependencias o flujos.
  No aplica                 → El riesgo no corresponde a la arquitectura del agente.
  Monitoreo manual          → Requiere observar métricas de uso en tiempo real.

{'=' * 70}
CASOS DE PRUEBA ({len(resultado.test_cases)} total)
{'=' * 70}
"""
    for i, caso in enumerate(resultado.test_cases, 1):
        reporte += f"\n{i}. {caso}"

    # ── Guardar ──────────────────────────────────────────────────────────────

    resultado.save(to=str(RESULTADOS))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_reporte = RESULTADOS / f"reporte_{ts}.txt"
    ruta_reporte.write_text(reporte, encoding="utf-8")

    print(f"\n\n💾 Resultados DeepTeam : {RESULTADOS}/")
    print(f"💾 Reporte de texto    : {ruta_reporte}")


if __name__ == "__main__":
    main()
