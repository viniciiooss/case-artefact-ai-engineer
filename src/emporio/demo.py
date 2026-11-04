"""Simulador determinístico para demonstração sem chave; não é um modelo de linguagem.

Produz chamadas das mesmas ferramentas utilizadas pela LLM. A linguagem é limitada
aos cenários documentados; perguntas abertas devem usar OpenAI/Ollama.
"""

import json
import re
from datetime import date, timedelta
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from emporio.pricing import brl
from emporio.text import normalize

CATEGORIES = {
    "violao": "Violões",
    "ukulele": "Ukuleles",
    "guitarra": "Guitarras",
    "baixo": "Baixos",
    "bateria": "Baterias",
    "teclado": "Teclados",
    "piano": "Pianos",
}
BRANDS = {
    "yamaha",
    "tagima",
    "giannini",
    "rozini",
    "shelby",
    "crafter",
    "martin",
    "taylor",
    "takamine",
    "kala",
    "ohana",
    "kalani",
    "fender",
    "gibson",
    "ibanez",
    "prs",
    "music",
    "korg",
    "nord",
    "roland",
    "pearl",
}
FILLER = set(
    "quanto custa custo preco valor do da de o a um uma qual no na em por para e "
    "pix cartao credito debito boleto reais quero comprar tem estoque promocao "
    "promocional disponivel desconto fica ficaria esse essa modelo favor voces "
    "vi anuncio black friday hoje agora saber".split()
)
ORDER_STATUS = {
    "pending": "pendente",
    "confirmed": "confirmado",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}


def call(name: str, args: dict) -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": "demo-" + uuid4().hex[:12]}]
    )


def parse_budget(question: str) -> float | None:
    match = re.search(
        r"(?:até|ate|menos de|no máximo|no maximo|orçamento de)\s*"
        r"(?:r\$\s*)?([\d.,]+)",
        question,
        re.I,
    )
    if not match:
        return None
    value = match[1].rstrip(".,")
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    elif "." in value and len(value.rsplit(".", 1)[1]) == 3:
        value = value.replace(".", "")
    return float(value)


class DemoModel:
    def __init__(self, context: dict, today: date):
        self.context, self.today = context, today

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        latest = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        question = messages[latest].text
        normalized = normalize(question)
        outputs = [
            {"name": m.name, "result": json.loads(m.content)}
            for m in messages[latest + 1 :]
            if isinstance(m, ToolMessage)
        ]
        if outputs:
            # Primeiro localiza o modelo, depois aplica regras de preço com outra ferramenta.
            last = outputs[-1]
            if last["name"] in {"search_products", "get_product"} and self._wants_quote(normalized):
                products = last["result"].get("products", [])
                if "product" in last["result"]:
                    products = [last["result"]["product"]]
                if len(products) == 1:
                    return call(
                        "quote_product", self._quote_args(normalized, products[0]["product_id"])
                    )
            return AIMessage(content=self._render(question, outputs))

        if any(
            w in normalized
            for w in (
                "liste todos os clientes",
                "emails e telefones",
                "dados pessoais",
                "senha",
                "chave da api",
            )
        ):
            return AIMessage(
                content="Não compartilho dados pessoais de clientes ou credenciais. "
                "Posso ajudar com instrumentos, políticas e seu pedido identificado."
            )
        if any(w in normalized for w in ("atendente", "humano", "reclamacao", "reclamar")):
            return call("create_support_ticket", {"reason": question})
        if any(w in normalized for w in ("pedido", "rastreio", "rastrear", "rastreamento")):
            match = re.search(
                r"(?:pedido|rastreio|rastrear|rastreamento)\s*(?:numero\s*)?#?\s*(\d+)", normalized
            )
            if not match:
                return AIMessage(
                    content="Qual é o número do pedido? Para consultar, use também "
                    "Identificar pedido na web ou /verificar NUMERO EMAIL na CLI."
                )
            return call("get_order", {"order_id": int(match[1])})

        return_terms = ("devolver", "devolucao", "arrepend", "trocar", "defeito")
        if any(w in normalized for w in return_terms) or (
            self.context.get("pending_return")
            and any(w in normalized for w in ("online", "presencial", "recebi", "internet"))
        ):
            return call("assess_return", self._return_args(normalized))

        family = next(
            (name for word, name in CATEGORIES.items() if word in normalized.split()), None
        )
        accessory = any(
            w in normalized.split()
            for w in (
                "cabo",
                "cabos",
                "pedal",
                "pedais",
                "amplificador",
                "amplificadores",
                "case",
                "cases",
                "palheta",
                "palhetas",
                "cordas",
            )
        )
        if accessory and not family:
            return AIMessage(
                content="A Empório trabalha exclusivamente com instrumentos musicais; "
                "não vendemos acessórios como cabos, pedais, amplificadores ou jogos "
                "de cordas. Posso ajudar a encontrar um instrumento para você."
            )

        # Uma referência explícita sempre prevalece sobre a memória do último modelo.
        product_id = re.search(r"(?:produto|id)\s*#?\s*(\d+)", normalized)
        if product_id:
            return call("get_product", {"product_id": int(product_id[1])})
        quote_followup = self._wants_quote(normalized) and self.context.get("products")
        brand_present = any(w in normalized.split() for w in BRANDS)
        if quote_followup and not brand_present and not family:
            products = self.context["products"]
            selection = {"primeiro": 0, "segundo": 1, "terceiro": 2}
            chosen = next((idx for word, idx in selection.items() if word in normalized), None)
            if chosen is not None and chosen < len(products):
                return call("quote_product", self._quote_args(normalized, products[chosen]))
            if len(products) == 1:
                return call("quote_product", self._quote_args(normalized, products[0]))
            return AIMessage(
                content="Qual dos modelos você quer simular? Pode informar o nome "
                "ou dizer, por exemplo, 'o primeiro no PIX'."
            )

        model_code = re.search(r"\b[a-z]{1,5}\d{2,4}[a-z]?\b", normalized)
        if family or brand_present or model_code:
            words = normalized.split()
            if brand_present:
                start = next(i for i, w in enumerate(words) if w in BRANDS)
                relevant = words[start:]
                stop = next(
                    (i for i, w in enumerate(relevant) if w in {"no", "em", "por", "para"}),
                    len(relevant),
                )
                query = " ".join(w for w in relevant[:stop] if w not in FILLER)
            elif model_code:
                query = model_code[0]
            else:
                query = " ".join(
                    w
                    for w in words
                    if w
                    in {
                        "nylon",
                        "aco",
                        "eletrico",
                        "natural",
                        "sunburst",
                        "preto",
                        "soprano",
                        "tenor",
                    }
                )
            return call(
                "search_products",
                {
                    "query": query,
                    "category": family,
                    "max_price_brl": parse_budget(question),
                    "available_only": not (brand_present or model_code),
                    "limit": 6,
                },
            )

        if any(
            w in normalized
            for w in (
                "horario",
                "endereco",
                "onde fica",
                "abrem",
                "abre ",
                "sabado",
                "domingo",
                "pagamento",
                "parcelamento",
                "pix",
                "promocao",
                "frete",
                "entrega",
                "garantia",
                "whatsapp",
                "telefone",
                "contato",
                "privacidade",
                "funciona",
            )
        ):
            return call("search_policies", {"query": question})
        if normalized in {"oi", "ola", "bom dia", "boa tarde", "boa noite", "obrigado", "obrigada"}:
            return AIMessage(
                content="Oi! Sou a Mel, assistente da Empório da Música. "
                "Posso ajudar a escolher um instrumento, consultar seu pedido "
                "ou explicar as políticas da loja. Como posso ajudar?"
            )
        return AIMessage(
            content="Por aqui posso ajudar com instrumentos musicais, pedidos e "
            "políticas da Empório da Música. Sobre outros assuntos, não tenho "
            "informações confiáveis para te orientar. O que você procura na loja?"
        )

    @staticmethod
    def _wants_quote(text: str) -> bool:
        return (
            any(w in text for w in ("pix", "parcel", "credito", "debito", "boleto", "frete"))
            or bool(re.search(r"\bem \d{1,2}x\b", text))
            or bool(re.fullmatch(r"(?:e )?\d{1,2}x", text))
        )

    @staticmethod
    def _quote_args(text: str, product_id: int) -> dict:
        match = re.search(r"\bem\s+(\d{1,2})x\b|(?:em\s+)?(\d{1,2})\s+(?:vezes|parcela)", text)
        if not match:
            match = re.fullmatch(r"(?:e )?(\d{1,2})x", text)
        n = int(next(g for g in match.groups() if g)) if match else 1
        payment = next(
            (
                p
                for w, p in (("pix", "pix"), ("boleto", "boleto"), ("debito", "debit"))
                if w in text
            ),
            "credit" if match or "credito" in text else "debit",
        )
        city = next(
            (
                c
                for c in ("campo grande", "dourados", "tres lagoas", "corumba", "ponta pora")
                if c in text
            ),
            None,
        )
        quantity = re.search(r"\b(\d+)\s+unidades?\b", text)
        return {
            "product_id": product_id,
            "payment": payment,
            "installments": n,
            "city": city,
            "quantity": int(quantity[1]) if quantity else 1,
        }

    def _return_args(self, text: str) -> dict:
        reuse = self.context.get("pending_return") and not any(
            word in text for word in ("outra compra", "outro pedido", "nova compra")
        )
        args = dict(self.context.get("return_request", {})) if reuse else {}
        args.setdefault("channel", "unknown")
        args.setdefault("reason", "regret")
        if any(w in text for w in ("online", "internet", "site")):
            args["channel"] = "online"
        elif any(w in text for w in ("presencial", "fisica", "na loja")):
            args["channel"] = "store"
        if "defeito" in text:
            args["reason"] = "defect"
        elif any(w in text for w in ("cor", "preferencia", "tamanho")):
            args["reason"] = "preference"
        for verb, key in (("recebi", "received_at"), ("comprei", "purchased_at")):
            match = re.search(verb + r"(?:\s+\w+){0,3}?\s+(\d+)\s+dias?", text)
            iso = re.search(verb + r"\s+(?:em\s+)?(\d{4})\s+(\d{2})\s+(\d{2})", text)
            if match:
                args[key] = (self.today - timedelta(days=int(match[1]))).isoformat()
            elif iso:
                args[key] = date(int(iso[1]), int(iso[2]), int(iso[3])).isoformat()
            elif verb + " hoje" in text:
                args[key] = self.today.isoformat()
        return args

    def _render(self, question: str, outputs: list[dict]) -> str:
        payload = outputs[-1]["result"]
        if "error" in payload:
            if payload["error"] == "order_verification_required":
                return (
                    "Para proteger seus dados, preciso que você identifique o pedido. "
                    "Use Identificar pedido na web ou /verificar NUMERO EMAIL na CLI. "
                    "Depois me peça o status novamente."
                )
            return (
                "Não consegui concluir essa consulta. "
                "Confira o modelo ou os dados e tente novamente."
            )
        if "products" in payload or "product" in payload:
            products = payload.get("products", [payload.get("product")])
            if not products:
                return (
                    "Não encontrei instrumentos com esses critérios no catálogo fornecido. "
                    "Podemos tentar outra marca, faixa de preço ou tipo de instrumento."
                )
            lines = ["Consultei o catálogo. Olha o que encontrei:"]
            for p in products:
                price = brl(p["sale_price_cents"])
                promo = (
                    f" (de {brl(p['price_cents'])}, {p['discount_percent']}% de desconto ativo)"
                    if p["discount_percent"]
                    else " (preço de tabela; sem promoção ativa)"
                )
                state = (
                    f"{p['stock_quantity']} em estoque"
                    if p["available"]
                    else {
                        "coming_soon": "em breve; indisponível para compra",
                        "discontinued": "descontinuado; indisponível para compra",
                    }.get(p["status"], "temporariamente sem estoque")
                )
                lines.append(f"• {p['name']} — {price}{promo}. {state}.")
            if any(not p["available"] for p in products):
                lines.append("Posso buscar alternativas disponíveis da mesma categoria.")
            else:
                lines.append("Quer detalhes de algum modelo ou uma simulação no PIX/parcelada?")
            return "\n\n".join(lines)
        if "quote" in payload:
            q = payload["quote"]
            if q["status"] == "unavailable":
                return q["notes"][0] + " Posso buscar uma alternativa disponível."
            lines = [
                f"Para {q['name']} ({q['quantity']} unidade(s)):",
                f"• Preço de tabela por unidade: {brl(q['original_unit_cents'])}.",
                f"• Total dos produtos: {brl(q['total_cents'])}"
                + (f" com {q['discount_percent']}% de desconto." if q["discount_percent"] else "."),
            ]
            if len(q["installment_cents"]) > 1:
                parts = q["installment_cents"]
                lines.append(f"• Em {len(parts)}x: " + ", ".join(brl(v) for v in parts) + ".")
            if q["shipping_cents"] is not None:
                lines.append(
                    f"• Frete: {brl(q['shipping_cents'])}; "
                    f"total com frete: {brl(q['grand_total_cents'])}."
                )
            lines.extend("• " + note for note in q["notes"])
            if q["status"] == "invalid":
                lines.append(
                    "Essa quantidade de parcelas não atende à regra; escolha menos parcelas."
                )
            lines.append("É uma simulação, sem reserva de estoque ou realização de compra.")
            return "\n".join(lines)
        if "order" in payload:
            order = payload["order"]
            lines = [
                f"Pedido #{order['order_id']}: "
                f"{ORDER_STATUS.get(order['status'], order['status'])}.",
                f"Total registrado: {brl(order['total_cents'])}.",
            ]
            if order["tracking_code"]:
                lines.append(f"Código de rastreamento: {order['tracking_code']}.")
            if order["estimated_delivery"]:
                lines.append(
                    f"Previsão registrada: {order['estimated_delivery']}. "
                    "Essa data não confirma recebimento nem foi atualizada pela transportadora."
                )
            else:
                lines.append("Ainda não há previsão de entrega registrada.")
            if order["notes"]:
                lines.append(order["notes"])
            return "\n".join(lines)
        if "assessment" in payload:
            a = payload["assessment"]
            if a["status"] == "needs_information":
                missing = []
                if "channel" in a["missing"]:
                    missing.append("a compra foi online ou presencial?")
                if "received_at" in a["missing"]:
                    missing.append("qual foi a data real de recebimento?")
                if "purchased_at" in a["missing"]:
                    missing.append("qual foi a data da compra?")
                return (
                    "Vamos conferir as condições: "
                    + " E ".join(missing)
                    + (
                        " Para arrependimento online, o manual prevê até 7 dias corridos "
                        "do recebimento; "
                        "a previsão do pedido não comprova essa data."
                    )
                )
            return (
                a["message"]
                + (
                    f" São {a['elapsed_days']} dias; o prazo desta regra é "
                    f"{a['policy_limit_days']} dias corridos.\n\n"
                    if "elapsed_days" in a
                    else "\n\n"
                )
                + a.get("conditions", "")
                + "\n\nPosso orientar pelo manual; a equipe confirma a solicitação e as condições."
            )
        if "ticket" in payload:
            ticket = payload["ticket"]
            return f"Seu protocolo é {ticket['ticket_id']}. " + ticket["message"]
        sources = payload.get("sources", [])
        if not sources:
            return (
                "Não encontrei essa informação no manual. A equipe pode confirmar pelo atendimento."
            )
        passages = []
        for source in sources[:2]:
            excerpt = source["excerpt"]
            if len(excerpt) > 1100:
                excerpt = excerpt[:1100].rsplit(" ", 1)[0] + " […]"
            passages.append(
                f"{source['title']} (página {source['page']}):\n" + excerpt.replace(" • ", "\n• ")
            )
        return "Encontrei estas orientações no manual da loja:\n\n" + "\n\n".join(passages)
