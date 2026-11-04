.PHONY: sync sync-eval serve chat ingest lint test eval eval-llm validate-evals examples check

sync:
	uv sync --locked --no-editable --extra observability

sync-eval:
	uv sync --locked --no-editable --extra observability --extra eval

serve: sync
	uv run --no-sync emporio serve

chat: sync
	uv run --no-sync emporio chat

ingest: sync
	uv run --no-sync emporio ingest

lint: sync
	uv run --no-sync ruff check .
	uv run --no-sync ruff format --check .

test: sync-eval
	uv run --no-sync pytest

eval: sync
	uv run --no-sync python scripts/evaluate.py

eval-llm: sync-eval
	uv run --no-sync python scripts/evaluate_llm.py --limit 4

validate-evals: sync
	uv run --no-sync python scripts/evaluate_llm.py --cases evals/golden_emporio.jsonl --validate-only --limit 60

examples: sync
	uv run --no-sync python scripts/evaluate.py --write-examples --report var/evaluation.json

check: lint test eval validate-evals
