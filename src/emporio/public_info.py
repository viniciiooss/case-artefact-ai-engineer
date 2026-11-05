"""Roteamento conservador de FAQs públicas, com fatos extraídos das fontes do turno."""

import re

from emporio.text import normalize

REQUEST_WORDS = set(
    "a o as os e de da do das dos em na no ao aos para por favor com que qual quais "
    "sao eh e me voce voces pode podem poderia poderiam informar informe passe passar "
    "diga saber gostaria quero oi ola bom boa dia tarde noite obrigado obrigada "
    "loja emporio musica oficial oficiais principal remoto atendimento".split()
)
CONTACT_WORDS = set("contato contatos telefone telefones whatsapp zap canal canais geral".split())
HOURS_WORDS = set(
    "horario funcionamento abre abrem fecha fecham aberto aberta sabado sabados domingo "
    "domingos feriado feriados segunda sexta semana feira".split()
)
ADDRESS_WORDS = set(
    "endereco enderecos localizacao localizado localizada fica onde visitar rua".split()
)
QUERIES = {
    "channel": "atendimento via WhatsApp principal telefone contato",
    "contacts": "atendimento via WhatsApp principal telefone contato",
    "phone": "atendimento via WhatsApp principal telefone contato",
    "hours": "Horário de funcionamento Segunda Sexta Sábado Domingo feriados",
    "address": "Dados da Empresa endereço rua centro",
}


def public_intent(question: str) -> str | None:
    words = set(normalize(question).split())
    if not words or not words <= REQUEST_WORDS | CONTACT_WORDS | HOURS_WORDS | ADDRESS_WORDS:
        return None  # Pedido, cliente, ação, valores ou assunto desconhecido ficam com o agente.
    domains = [bool(words & group) for group in (CONTACT_WORDS, HOURS_WORDS, ADDRESS_WORDS)]
    if sum(domains) > 1:
        return None
    if domains[1]:
        return "hours"
    if domains[2]:
        return "address"
    if domains[0] or "atendimento" in words:
        if words & {"contatos", "canais", "telefones"} or {"telefone", "whatsapp"} <= words:
            return "contacts"
        if "geral" in words or ("telefone" in words and "whatsapp" not in words):
            return "phone"
        return "channel"
    return None


def public_reply(intent: str, sources: list[dict]) -> tuple[str, list[str]] | None:
    by_section = {
        source.get("section"): source for source in sources if source.get("kind") == "policy"
    }
    sections = {
        "channel": ["7"],
        "contacts": ["7", "1.2"],
        "phone": ["1.2"],
        "hours": ["2"],
        "address": ["1.2"],
    }[intent]
    if any(section not in by_section for section in sections):
        return None
    used = [by_section[section] for section in sections]
    lines = []
    if intent in {"channel", "contacts", "phone"}:
        for source in used:
            phones = set(re.findall(r"\((\d{2})\)\s*(\d{4,5})\s*-\s*(\d{4})", source["excerpt"]))
            if len(phones) != 1:
                return None
            area, prefix, suffix = phones.pop()
            label = (
                "WhatsApp (atendimento principal)" if source["section"] == "7" else "Telefone geral"
            )
            lines.append(f"- **{label}:** ({area}) {prefix}-{suffix}")
    elif intent == "hours":
        text = used[0]["excerpt"]
        weekdays = re.search(
            r"Segunda a Sexta(?:-feira)?\s+(\d{2}:\d{2}) às (\d{2}:\d{2})", text, re.I
        )
        saturday = re.search(r"Sábado\s+(\d{2}:\d{2}) às (\d{2}:\d{2})", text, re.I)
        closed = re.search(r"Domingo e feriados\s+Fechado", text, re.I)
        if not (weekdays and saturday and closed):
            return None
        lines = [
            f"- **Segunda a sexta:** {weekdays[1]} às {weekdays[2]}.",
            f"- **Sábado:** {saturday[1]} às {saturday[2]}.",
            "- **Domingos e feriados:** fechado.",
        ]
    else:
        address = re.search(r"Endereço\s+(.+?)\s+Telefone\s*/\s*WhatsApp", used[0]["excerpt"], re.I)
        if not address:
            return None
        lines = [f"**Endereço:** {address[1]}."]
    return "\n".join(lines), [source["id"] for source in used]
