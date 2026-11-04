from datetime import date
from typing import Annotated, Literal

from langchain_core.tools import tool
from pydantic import Field

from emporio.pricing import assess_return as evaluate_return
from emporio.pricing import quote
from emporio.text import normalize


def product_source(product: dict) -> dict:
    return {
        "id": f"product-{product['product_id']}",
        "kind": "catalog",
        "title": product["name"],
        "reference": "products.csv + promotions.csv",
        "excerpt": f"Produto #{product['product_id']}; status {product['status']}; "
        f"estoque {product['stock_quantity']}. Consulta ao snapshot atual.",
    }


def make_tools(catalog, policies, sessions, session_id: str, question: str, today: date):
    """Dependências e identidade capturadas no servidor, fora do schema da LLM."""

    @tool
    def search_products(
        query: Annotated[str, Field(max_length=200)] = "",
        category: Annotated[str | None, Field(max_length=80)] = None,
        max_price_brl: Annotated[float | None, Field(ge=0, le=1000000)] = None,
        available_only: bool = True,
        limit: Annotated[int, Field(ge=1, le=10)] = 6,
    ) -> dict:
        """Consulta preço, estoque, promoção e descrição de instrumentos no catálogo atual.

        Use termos de modelo/marca em query, a família em category e orçamento em max_price_brl.
        Para consultar um modelo esgotado/descontinuado use available_only=False.
        """
        products = catalog.search_products(
            query,
            category=category,
            max_price_brl=max_price_brl,
            available_only=available_only,
            limit=limit,
        )
        return {"products": products, "sources": [product_source(p) for p in products]}

    @tool
    def get_product(product_id: Annotated[int, Field(ge=1)]) -> dict:
        """Consulta um produto pelo ID, inclusive itens esgotados ou descontinuados."""
        product = catalog.get_product(product_id)
        if not product:
            return {"error": "product_not_found", "sources": []}
        return {"product": product, "sources": [product_source(product)]}

    @tool
    def quote_product(
        product_id: Annotated[int, Field(ge=1)],
        payment: Literal["pix", "credit", "debit", "boleto"] = "debit",
        quantity: Annotated[int, Field(ge=1, le=100)] = 1,
        installments: Annotated[int, Field(ge=1, le=12)] = 1,
        city: Annotated[str | None, Field(max_length=100)] = None,
    ) -> dict:
        """Calcula cotação em centavos com promoção/PIX sem acumular, parcelas e frete.

        Não realiza compra. needs_review exige confirmação humana; invalid não pode ser prometido.
        """
        product = catalog.get_product(product_id)
        if not product:
            return {"error": "product_not_found", "sources": []}
        result = quote(
            product, payment=payment, quantity=quantity, installments=installments, city=city
        )
        sections = ["3", "3.1", "6.2"] + (["5.1", "5.2"] if city else [])
        return {
            "quote": result,
            "sources": [product_source(product)] + policies.section_sources(*sections),
        }

    @tool
    def get_order(order_id: Annotated[int, Field(ge=1)]) -> dict:
        """Consulta status e rastreamento de pedido já validado nesta sessão.

        Se não autorizado, solicite identificação pelo formulário web ou comando /verificar.
        """
        if not sessions.can_access_order(session_id, order_id):
            return {
                "error": "order_verification_required",
                "sources": [],
                "message": "Use Identificar pedido na web ou /verificar NUMERO EMAIL na CLI.",
            }
        order = catalog.get_order(order_id)
        if not order:
            return {"error": "order_not_found", "sources": []}
        source = {
            "id": f"order-{order_id}",
            "kind": "order",
            "title": f"Pedido #{order_id}",
            "reference": "orders.csv + order_items.csv",
            "excerpt": "Consulta autorizada.",
        }
        return {
            "order": order,
            "sources": [source],
            "notice": "Previsão registrada não é confirmação de recebimento nem rastreio ao vivo.",
        }

    @tool
    def search_policies(query: Annotated[str, Field(min_length=1, max_length=300)]) -> dict:
        """Recupera trechos reais do PDF da loja com seção e página: horários, endereço,
        pagamentos, frete, devoluções, garantia, privacidade e contatos.
        """
        return {"sources": policies.search(query)}

    @tool
    def assess_return(
        channel: Literal["online", "store", "unknown"] = "unknown",
        reason: Literal["regret", "defect", "preference"] = "regret",
        received_at: date | None = None,
        purchased_at: date | None = None,
    ) -> dict:
        """Aplica prazos do manual usando datas reais informadas pelo cliente. Não autoriza
        reembolso. Se canal/data faltarem, pede informações; datas futuras são rejeitadas.
        """
        result = evaluate_return(
            channel=channel,
            reason=reason,
            received_at=received_at,
            purchased_at=purchased_at,
            today=today,
        )
        sections = {
            "regret": ("4.1", "4.4"),
            "defect": ("4.2", "8.1"),
            "preference": ("4.3", "4.4"),
        }[reason]
        return {"assessment": result, "sources": policies.section_sources(*sections)}

    @tool
    def create_support_ticket(reason: Annotated[str, Field(min_length=5, max_length=2000)]) -> dict:
        """Registra protocolo local quando o usuário solicita equipe ou registra reclamação.
        Não envia mensagens, e-mails ou notificações externas.
        """
        if not any(w in normalize(question) for w in ("humano", "atendente", "equipe", "reclam")):
            return {
                "error": "confirmation_required",
                "sources": [],
                "message": "Confirme se deseja registrar uma solicitação de atendimento.",
            }
        return {
            "ticket": sessions.create_ticket(session_id, reason),
            "sources": policies.section_sources("7", "7.3"),
        }

    return [
        search_products,
        get_product,
        quote_product,
        get_order,
        search_policies,
        assess_return,
        create_support_ticket,
    ]
