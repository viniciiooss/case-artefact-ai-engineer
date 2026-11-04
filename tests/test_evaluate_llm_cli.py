import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(tmp_path, *arguments):
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("EMPORIO_", "OPENROUTER_", "OPENAI_", "LANGFUSE_"))
    }
    environment["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/evaluate_llm.py"), *arguments],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        timeout=20,
    )


def test_validation_only_filters_jsonl_without_credentials_or_creating_paid_reports(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        "\n".join(
            json.dumps({"id": id_, "type": category, "input": question, "expected_output": "ref"})
            for id_, category, question in [
                ("preco", "qualidade_resposta", "Preço?"),
                ("fonte", "citacao_fonte", "Cite a fonte"),
            ]
        )
    )
    report = tmp_path / "paid.json"
    result = run_cli(
        tmp_path,
        "--cases",
        str(path),
        "--category",
        "citacao_fonte",
        "--case-id",
        "fonte",
        "--validate-only",
        "--report",
        str(report),
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["total"] == 2 and summary["selected_ids"] == ["fonte"]
    assert not report.exists()


def test_unknown_case_id_is_reported_before_provider_setup(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps([{"id": "real", "messages": ["Pergunta"], "expected_output": "ref"}])
    )
    result = run_cli(tmp_path, "--cases", str(path), "--case-id", "inexistente", "--validate-only")
    assert result.returncode == 2
    assert "ID de caso inexistente no dataset" in result.stderr
    assert "OPENROUTER_API_KEY" not in result.stderr
