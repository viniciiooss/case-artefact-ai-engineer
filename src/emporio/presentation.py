"""Retira atribuições internas sem substituir o manual físico de um instrumento."""

import re

from emporio.text import normalize

INTERNAL = r"\*{0,2}manual\b\s+(?:da loja|interno|de pol[ií]ticas(?: e procedimentos)?)\*{0,2}"
MANUAL = (
    r"\*{0,2}manual\b(?:\s+(?:da loja|interno|de pol[ií]ticas(?: e procedimentos)?))?\*{0,2}"
    r"(?!\s+(?:do|da|de)\s+(?:produto|instrumento|fabricante|instru[cç][oõ]es|usu[aá]rio|"
    r"viol[aã]o|guitarra|piano|baixo|bateria|teclado|ukulele|modelo))"
)
PAGE = r"p[aá]g(?:ina|\.)?\s*\d+"
SECTION = rf"se[cç][aã]o\s+\d+(?:\.\d+)*(?:\s*,?\s*{PAGE})?"
CITATION = rf"\*{{0,2}}(?:{SECTION}|{PAGE})\*{{0,2}}"


def _contact_attribution(match: re.Match) -> str:
    text = match[0]
    if set(normalize(text).split()) & {
        "serie",
        "serial",
        "original",
        "produto",
        "instrumento",
        "modelo",
        "fabricante",
    }:
        return text
    if re.search(
        r"\b(?:whatsapp|telefones?|contatos?|canais?)\b|\(\d{2}\)\s*\d{4,5}-\d{4}", text, re.I
    ):
        return match["before"] + match["after"]
    return text


def customer_answer(text: str) -> str:
    # Uma linha composta só de proveniência não contém condições comerciais.
    text = re.sub(
        rf"^[ \t]*\*{{0,2}}(?:fontes?|refer[eê]ncias?)\s*:\*{{0,2}}\s*(?:o\s+)?"
        rf"{INTERNAL}(?:\s*,\s*(?:{SECTION}|{PAGE}))*\.?[ \t]*$",
        "",
        text,
        flags=re.I | re.M,
    )
    text = re.sub(
        rf"[ \t]*(?:\(\s*{CITATION}\s*\)|\[\s*{CITATION}\s*\])",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(
        rf"[ \t]+[—–-][ \t]*{CITATION}\.?(?=[ \t]*(?:$|\n))",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(
        rf"\b(?:segundo|conforme|de acordo com)\s+(?:o\s+)?{MANUAL}\s*[,;:]?\s*",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(rf"\b(?:no|neste|nesse)\s+{INTERNAL}[ \t]*", "", text, flags=re.I)
    # Sem inferir o sentido de 'número': pode ser número de série de um produto.
    text = re.sub(
        rf"^(?P<before>[^\n]*?)\s+no\s+{MANUAL}(?P<after>[^\n]*)$",
        _contact_attribution,
        text,
        flags=re.I | re.M,
    )
    text = re.sub(
        rf"\b([Oo])\s+(?:{INTERNAL}|{MANUAL}(?=\s+(?:prev[eê]|estabelece|determina)\b))",
        lambda match: "A loja" if match[1].isupper() else "a loja",
        text,
        flags=re.I,
    )
    # 'Foto do manual' e 'devolva o manual original' continuam como condições do produto.
    text = re.sub(rf"\bdo\s+{INTERNAL}", "da loja", text, flags=re.I)
    text = re.sub(rf"\bpelo\s+{INTERNAL}", "pelas condições da loja", text, flags=re.I)
    text = re.sub(r"(?<=\S) {2,}(?=\S)", " ", text).strip()
    text = re.sub(r" +([,.;:])", r"\1", text)
    return text[:1].upper() + text[1:]
