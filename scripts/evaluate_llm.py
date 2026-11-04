"""Avaliação DeepEval com geração e juiz reais no OpenRouter; consome créditos."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from emporio.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "evals/llm_cases.json")
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--judge-model", help="Slug do juiz no OpenRouter.")
    parser.add_argument("--report", type=Path, default=ROOT / "var/deepeval.json")
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not 1 <= args.limit <= len(cases):
        parser.error(f"--limit deve estar entre 1 e {len(cases)}.")
    try:
        from emporio.evaluation import run_evaluation

        overrides = {"provider": "openrouter"}
        if args.judge_model:
            overrides["eval_model"] = args.judge_model
        with TemporaryDirectory(prefix="emporio-llm-eval-") as state_dir:
            settings = Settings(**overrides, state_dir=Path(state_dir))
            print(f"Agente: {settings.model}; juiz: {settings.eval_model}; casos: {args.limit}")
            report = run_evaluation(settings, cases[: args.limit])
    except ImportError:
        print(
            "Instale o extra eval: "
            "uv sync --locked --no-editable --extra observability --extra eval"
        )
        return 2
    except Exception:
        print("Não foi possível iniciar a avaliação. Confira configuração, dependências e casos.")
        return 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for case in report["cases"]:
        print(f"{case['id']}: {'OK' if case['passed'] else 'FALHOU'}")
        for metric in case["metrics"]:
            print(f"  {metric['name']}: {metric['score']:.2f} (mínimo {metric['threshold']})")
        if case.get("error"):
            print(f"  Falha operacional: {case['error']}")
    print(f"{report['passed']}/{report['total']} aprovados; {report['evaluated']} executados.")
    print(f"Relatório: {args.report}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
