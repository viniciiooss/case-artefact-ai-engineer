"""Regressões determinísticas pelo HTTP real, sem rede, mocks ou LLM juiz."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from emporio.api import create_app
from emporio.config import Settings
from emporio.service import ChatService

ROOT = Path(__file__).resolve().parents[1]


def check_response(response: dict, expected: dict, service: ChatService) -> list[str]:
    failures = []
    answer = response["message"].casefold()
    for fragment in expected.get("contains", []):
        if fragment.casefold() not in answer:
            failures.append(f"faltou texto: {fragment}")
    for fragment in expected.get("not_contains", []):
        if fragment.casefold() in answer:
            failures.append(f"texto proibido: {fragment}")
    names = {tool["name"] for tool in response["tools"]}
    for name in expected.get("required_tools", []):
        if name not in names:
            failures.append(f"faltou ferramenta: {name}")
    pages = {source.get("page") for source in response["sources"]}
    for page in expected.get("source_pages", []):
        if page not in pages:
            failures.append(f"faltou página: {page}")
    ids = {source["id"] for source in response["sources"]}
    for source_id in expected.get("source_ids", []):
        if source_id not in ids:
            failures.append(f"faltou fonte: {source_id}")
    if expected.get("no_sources") and ids:
        failures.append("resposta deveria estar sem fontes")
    # Grounding estrutural: citações do manual precisam ser trechos reais do índice.
    actual_chunks = {chunk["id"]: chunk for chunk in service.policies.chunks}
    products = []
    for source in response["sources"]:
        if source["kind"] == "policy":
            original = actual_chunks.get(source["id"])
            if not original or any(
                source.get(key) != original[key] for key in ("page", "title", "excerpt")
            ):
                failures.append(f"fonte de política sem correspondência: {source['id']}")
        elif source["kind"] == "catalog":
            product = service.catalog.get_product(int(source["id"].removeprefix("product-")))
            if product is None:
                failures.append(f"produto inexistente: {source['id']}")
            else:
                products.append(product)
    if "max_price_brl" in expected:
        if not products:
            failures.append("busca deveria citar produtos")
        for product in products:
            if not product["available"]:
                failures.append(f"produto indisponível na recomendação: {product['product_id']}")
            if product["sale_price_cents"] > round(expected["max_price_brl"] * 100):
                failures.append(f"produto acima do orçamento: {product['product_id']}")
    if response["provider"] != "demo":
        failures.append("a avaliação deve executar o provedor demo explícito")
    return failures


def write_example(case: dict, records: list, metadata: dict) -> None:
    lines = [
        f"# {case['title']}",
        "",
        "Gerado por `uv run --no-sync python scripts/evaluate.py "
        "--write-examples`; execução real do serviço HTTP local, sem LLM.",
        "",
    ]
    lines += [f"- {key}: `{value}`" for key, value in metadata.items()]
    lines += [
        "",
        "Os e-mails deste snapshot são fictícios; a identificação abaixo é "
        "exclusiva deste exemplo.",
        "",
    ]
    for record in records:
        if record["action"] == "verify":
            lines += [
                f"**Identificação explícita:** pedido {record['order_id']}, "
                f"e-mail fictício `{record['email']}`.",
                "",
                f"Resultado do backend: `{json.dumps(record['result'])}`.",
                "",
            ]
            continue
        response = record["response"]
        lines += [f"**Cliente:** {record['message']}", "", f"**Mel:** {response['message']}", ""]
        tools = ", ".join(tool["name"] for tool in response["tools"]) or "nenhuma"
        lines += [f"Ferramentas: `{tools}`.", ""]
        for source in response["sources"]:
            page = f"; página {source['page']}" if source.get("page") else ""
            lines += [f"- Fonte `{source['id']}`: {source['title']}{page}."]
        lines += [""]
    path = ROOT / "examples" / case["example"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def evaluate(cases_path: Path, write_examples: bool = False) -> dict:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    results, examples = [], []
    with TemporaryDirectory(prefix="emporio-eval-") as state_dir:
        settings = Settings(
            _env_file=None,
            provider="demo",
            model="deterministic-v1",
            data_dir=ROOT / "data",
            state_dir=Path(state_dir),
            max_tool_rounds=4,
            llm_timeout=45,
            history_turns=10,
            timezone="America/Campo_Grande",
        )
        service = ChatService(settings)
        metadata = {
            "provider": settings.provider,
            "model": settings.model,
            "dataset_sha256": service.catalog.fingerprint,
            "policy_sha256": service.policies.fingerprint,
        }
        with TestClient(create_app(service=service)) as client:
            for case in cases:
                session = client.post("/api/sessions").json()
                base = f"/api/sessions/{session['session_id']}"
                headers = {"Authorization": f"Bearer {session['token']}"}
                sessions = [(base, headers)]
                failures, records = [], []
                for index, step in enumerate(case["steps"], 1):
                    if step.get("action") == "new_session":
                        session = client.post("/api/sessions").json()
                        base = f"/api/sessions/{session['session_id']}"
                        headers = {"Authorization": f"Bearer {session['token']}"}
                        sessions.append((base, headers))
                        records.append({"action": "new_session"})
                        continue
                    if step.get("action") == "verify":
                        body = {"order_id": step["order_id"], "email": step["email"]}
                        result = client.post(base + "/order-access", json=body, headers=headers)
                        if result.status_code != step.get("status", 200):
                            failures.append(f"etapa {index}: verificação HTTP {result.status_code}")
                        elif (
                            result.status_code == 200 and result.json().get("verified") is not True
                        ):
                            failures.append(f"etapa {index}: pedido não foi verificado")
                        records.append({"action": "verify", **body, "result": result.json()})
                        continue
                    result = client.post(
                        base + "/messages",
                        json={"message": step["message"]},
                        headers=headers,
                    )
                    if result.status_code != 200:
                        failures.append(f"etapa {index}: mensagem HTTP {result.status_code}")
                        continue
                    response = result.json()
                    failures += [
                        f"etapa {index}: {failure}"
                        for failure in check_response(response, step, service)
                    ]
                    records.append(
                        {"action": "message", "message": step["message"], "response": response}
                    )
                for session_base, session_headers in sessions:
                    client.delete(session_base, headers=session_headers)
                results.append(
                    {
                        "id": case["id"],
                        "passed": not failures,
                        "failures": failures,
                        "steps": records,
                    }
                )
                if case.get("example"):
                    examples.append((case, records))
        report = {
            "metadata": metadata,
            "cases": results,
            "passed": sum(result["passed"] for result in results),
            "total": len(results),
        }
        if write_examples and report["passed"] == report["total"]:
            for case, records in examples:
                write_example(case, records, metadata)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "evals/cases.json")
    parser.add_argument("--report", type=Path, help="Gravar relatório JSON, sem tokens de sessão.")
    parser.add_argument("--write-examples", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.cases, args.write_examples)
    print(f"{'CENÁRIO':35} RESULTADO")
    for case in report["cases"]:
        print(f"{case['id']:35} {'OK' if case['passed'] else 'FALHOU'}")
        for failure in case["failures"]:
            print(f"  {failure}")
    print(f"{report['passed']}/{report['total']} cenários aprovados (demo, sem LLM juiz).")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
