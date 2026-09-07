"""Interfaz de consola del equipo Cafe.AI."""

import argparse
import sys
from pathlib import Path

from cafe_ai_agents.config import create_llm
from cafe_ai_agents.formatter import campaign_to_markdown
from cafe_ai_agents.graph import run_campaign


def build_parser() -> argparse.ArgumentParser:
    """Define los argumentos disponibles en la consola."""
    parser = argparse.ArgumentParser(description="Genera una campaña multiagente para Cafe.AI")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--brief", help="Solicitud publicitaria escrita directamente")
    source.add_argument("--brief-file", type=Path, help="Archivo de texto con la solicitud")
    parser.add_argument("--output", type=Path, help="Ruta donde guardar el Markdown")
    parser.add_argument("--model", help="Nombre de un modelo local de Ollama")
    parser.add_argument("--quiet", action="store_true", help="Oculta el avance de los agentes")
    return parser


def _read_brief(args: argparse.Namespace) -> str:
    """Obtiene el brief desde argumento, archivo o entrada interactiva."""
    if args.brief:
        return args.brief.strip()
    if args.brief_file:
        return args.brief_file.read_text(encoding="utf-8").strip()
    return input("Describe la campaña para Cafe.AI: ").strip()


def main(argv: list[str] | None = None) -> int:
    """Configura el modelo, ejecuta el grafo y presenta el resultado."""
    args = build_parser().parse_args(argv)
    try:
        brief = _read_brief(args)
        if not brief:
            raise ValueError("El brief no puede estar vacío.")

        llm, model_name = create_llm(args.model)
        if not args.quiet:
            print(f"[SISTEMA] Modelo seleccionado: {model_name}")

        campaign = run_campaign(llm, brief, verbose=not args.quiet)
        markdown = campaign_to_markdown(campaign)
        print("\n" + markdown)

        if args.output:
            # Solo se escribe el archivo cuando el usuario lo solicita explícitamente.
            args.output.write_text(markdown, encoding="utf-8")
            print(f"Campaña guardada en: {args.output}")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
