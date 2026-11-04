.PHONY: sync serve chat ingest lint test eval examples check

sync:
	uv sync --locked --no-editable

serve: sync
	uv run --no-sync emporio serve

chat: sync
	uv run --no-sync emporio chat

ingest: sync
	uv run --no-sync emporio ingest

lint: sync
	uv run --no-sync ruff check .
	uv run --no-sync ruff format --check .

test: sync
	uv run --no-sync pytest

eval: sync
	uv run --no-sync python scripts/evaluate.py

examples: sync
	uv run --no-sync python scripts/evaluate.py --write-examples --report var/evaluation.json

check: lint test eval
