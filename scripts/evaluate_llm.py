"""Avaliação DeepEval com geração e juiz reais no OpenRouter; consome créditos."""

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from emporio.config import Settings
from emporio.eval_dataset import load_cases, select_cases

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "evals/llm_cases.json")
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--category", help="Filtrar pelo campo type do dataset.")
    parser.add_argument(
        "--case-id", action="append", help="Executar só este ID; pode repetir a opção."
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validar e listar a seleção sem chamar modelos.",
    )
    parser.add_argument("--judge-model", help="Slug do juiz no OpenRouter.")
    parser.add_argument("--report", type=Path, default=ROOT / "var/deepeval.json")
    args = parser.parse_args()
    try:
        cases = load_cases(args.cases)
        cases_file_digest = sha256(args.cases.read_bytes()).hexdigest()
        selected = select_cases(
            cases, category=args.category, case_ids=args.case_id, limit=args.limit
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.validate_only:
        print(
            json.dumps(
                {
                    "dataset": str(args.cases),
                    "total": len(cases),
                    "by_type": dict(Counter(case.type for case in cases)),
                    "selected": len(selected),
                    "selected_ids": [case.id for case in selected],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    try:
        from emporio.evaluation import run_evaluation

        overrides = {"provider": "openrouter"}
        if args.judge_model:
            overrides["eval_model"] = args.judge_model
        with TemporaryDirectory(prefix="emporio-llm-eval-") as state_dir:
            settings = Settings(**overrides, state_dir=Path(state_dir))
            print(
                f"Agente: {settings.model}; juiz: {settings.eval_model} "
                f"(raciocínio {settings.eval_reasoning_effort}); casos: {len(selected)}"
            )
            report = run_evaluation(settings, selected)
    except ImportError:
        print(
            "Instale o extra eval: "
            "uv sync --locked --no-editable --extra observability --extra eval"
        )
        return 2
    except Exception:
        print("Não foi possível iniciar a avaliação. Confira configuração, dependências e casos.")
        return 2
    report["metadata"].update(cases_file=str(args.cases), cases_file_sha256=cases_file_digest)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for case in report["cases"]:
        print(f"{case['id']}: {'OK' if case['passed'] else 'FALHOU'}")
        for metric in case["metrics"]:
            print(f"  {metric['name']}: {metric['score']:.2f} (mínimo {metric['threshold']})")
        for failure in case.get("checks", {}).get("failures", []):
            print(f"  Verificação exata: {failure}")
        if case.get("error"):
            print(f"  Falha operacional: {case['error']}")
    print(f"{report['passed']}/{report['total']} aprovados; {report['evaluated']} executados.")
    for category, counts in report["by_type"].items():
        print(
            f"  {category}: {counts['passed']}/{counts['evaluated']} aprovados; "
            f"{counts['total']} selecionados"
        )
    print(f"Relatório: {args.report}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
