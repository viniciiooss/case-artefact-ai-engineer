"""Regressão opcional no navegador; requer Playwright e Chromium instalados.

Executa os assets reais com respostas HTTP controladas, sem chamar modelos pagos.
"""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit


def main():
    from playwright.sync_api import expect, sync_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser-path", help="Executável Chromium/Chrome alternativo")
    args = parser.parse_args()
    assets = Path(__file__).resolve().parents[1] / "src" / "emporio" / "web"
    messages = []
    source = {
        "id": "policy-p2-2-0",
        "kind": "policy",
        "title": "Horário de funcionamento",
        "page": 2,
        "section": "2",
        "excerpt": '<img src=x onerror="window.sourceInjected=true"> Segunda a sexta: 09h–18h.',
        "reference": "politicas_da_loja.pdf",
    }
    reply = (
        "Nosso **horário** é de **09h às 18h**.\n"
        "*Sábados*: 09h às 13h.\n\n"
        '<img src=x onerror="window.replyInjected=true">'
        "<script>window.replyInjected=true</script>\n"
        "**<svg onload=window.replyInjected=true>**"
    )

    def route_request(route):
        path = urlsplit(route.request.url).path
        if path in {"/", "/static/app.js", "/static/style.css"}:
            filename = "index.html" if path == "/" else path.rsplit("/", 1)[-1]
            route.fulfill(path=assets / filename)
        elif path == "/api/health":
            route.fulfill(json={"provider": "demo", "status": "ok"})
        elif path == "/api/sessions":
            route.fulfill(status=201, json={"session_id": "format-test", "token": "test-token"})
        elif path == "/api/sessions/format-test":
            route.fulfill(json={"messages": messages, "verified_orders": []})
        elif path == "/api/sessions/format-test/messages":
            question = route.request.post_data_json["message"]
            messages.extend(
                [
                    {"role": "user", "content": question, "sources": []},
                    {"role": "assistant", "content": reply, "sources": [source]},
                ]
            )
            route.fulfill(json={"message": reply, "sources": [source], "provider": "demo"})
        else:
            route.abort()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.browser_path, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/*", route_request)
        page.goto("http://emporio.test/")
        expect(page.locator("#new-conversation")).to_be_enabled()
        question = '**Texto do cliente** <img src=x onerror="window.userInjected=true">'
        page.locator("#message").fill(question)
        page.locator("#message").press("Enter")
        answer = page.locator(".message-assistant").first
        expect(answer.locator("strong")).to_have_count(3)
        expect(answer.locator("strong").first).to_have_text("horário")
        expect(answer.locator("em")).to_have_text("Sábados")
        assert "**horário**" not in answer.inner_text()
        expect(page.locator(".message-user .message-content").first).to_have_text(question)
        expect(page.locator(".message-user strong")).to_have_count(0)
        expect(page.locator(".message img, .message script, .message svg")).to_have_count(0)
        assert not page.evaluate(
            "window.replyInjected || window.sourceInjected || window.userInjected"
        )
        assert "<svg onload=window.replyInjected=true>" in answer.inner_text()
        source_details = answer.locator(".source").first
        source_details.locator("summary").click()
        expect(source_details.locator("a")).to_have_attribute(
            "href", "/api/policies/document#page=2"
        )
        answer.evaluate("el => { el.dataset.preserved = 'yes'; }")
        page.locator("#message").fill("E no sábado?")
        page.locator("#message").press("Enter")
        expect(page.locator(".message-assistant")).to_have_count(2)
        expect(answer).to_have_attribute("data-preserved", "yes")
        expect(source_details).to_have_attribute("open", "")
        page.reload()
        expect(page.locator(".message-assistant")).to_have_count(2)
        expect(page.locator(".message-assistant strong")).to_have_count(6)
        page.set_viewport_size({"width": 375, "height": 812})
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
        expect(page.locator("#message")).to_be_visible()
        assert errors == [], errors
        browser.close()
    print(
        json.dumps({"passed": True, "checks": ["emphasis", "XSS", "sources", "history", "mobile"]})
    )


if __name__ == "__main__":
    main()
