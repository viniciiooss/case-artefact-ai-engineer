"""Datasets de avaliação e verificações exatas, sem dependência de juiz ou rede."""

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StringConstraints, field_validator

from emporio.grounding import money_mentions

CaseType = Literal[
    "smoke",
    "fact",
    "out_of_scope",
    "qualidade_resposta",
    "aderencia_contexto",
    "citacao_fonte",
    "alucinacao",
    "fora_da_base",
    "prompt_injection",
]
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class OrderAccess(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: int = Field(gt=0)
    email: str = Field(min_length=3, max_length=254)


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    type: CaseType = "smoke"
    messages: list[Question] = Field(
        min_length=1, max_length=6, validation_alias=AliasChoices("messages", "input")
    )
    expected_output: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    order_access: OrderAccess | None = None
    expected_money_cents: list[Annotated[int, Field(ge=0)]] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    source_pages: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list)
    not_contains: list[str] = Field(default_factory=list)

    @field_validator("messages", mode="before")
    @classmethod
    def single_input_as_conversation(cls, value):
        return [value] if isinstance(value, str) else value


def load_cases(path: Path) -> list[EvaluationCase]:
    content = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        rows = []
        for number, line in enumerate(content.splitlines(), 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"JSON inválido na linha {number}.") from exc
    else:
        rows = json.loads(content)
    if not isinstance(rows, list) or not rows:
        raise ValueError("Dataset vazio ou não é uma lista de casos.")
    cases, ids = [], set()
    for number, row in enumerate(rows, 1):
        try:
            case = EvaluationCase.model_validate(row)
        except ValueError as exc:
            raise ValueError(f"Contrato inválido no caso {number}.") from exc
        if case.id in ids:
            raise ValueError(f"ID duplicado: {case.id}.")
        ids.add(case.id)
        cases.append(case)
    return cases


def select_cases(
    cases: list[EvaluationCase],
    *,
    category: str | None = None,
    case_ids: list[str] | None = None,
    limit: int = 4,
) -> list[EvaluationCase]:
    if limit < 1:
        raise ValueError("--limit deve ser positivo.")
    requested = set(case_ids or [])
    if requested - {case.id for case in cases}:
        raise ValueError("ID de caso inexistente no dataset.")
    selected = [
        case
        for case in cases
        if (category is None or case.type == category) and (not requested or case.id in requested)
    ]
    if not selected:
        raise ValueError("Nenhum caso corresponde aos filtros.")
    return selected[:limit]


def check_expectations(case: EvaluationCase, response: dict) -> list[str]:
    failures = []
    missing_money = set(case.expected_money_cents) - money_mentions(response["message"])
    failures.extend(f"missing_money:{amount}" for amount in sorted(missing_money))
    tools = {tool["name"] for tool in response["tools"] if tool["ok"]}
    failures.extend(f"missing_tool:{name}" for name in case.required_tools if name not in tools)
    ids = {source["id"] for source in response["sources"]}
    failures.extend(f"missing_source:{name}" for name in case.source_ids if name not in ids)
    pages = {source.get("page") for source in response["sources"]}
    failures.extend(f"missing_page:{page}" for page in case.source_pages if page not in pages)
    if any(fragment.casefold() in response["message"].casefold() for fragment in case.not_contains):
        failures.append("forbidden_text_detected")
    return failures
