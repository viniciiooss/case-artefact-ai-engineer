"""Normalização compartilhada por buscas em português."""

import re
import unicodedata

STOPWORDS = frozenset(
    "a o as os e de da do das dos em na no nas nos um uma para por com que qual quais "
    "eu meu minha me voce voces tem quero gostaria saber pode quanto custa ate reais r brl "
    "opcao opcoes disponivel disponiveis comprar instrumento instrumentos loja sobre".split()
)
SINGULAR = {
    "violoes": "violao",
    "guitarras": "guitarra",
    "baixos": "baixo",
    "baterias": "bateria",
    "teclados": "teclado",
    "ukuleles": "ukulele",
    "pianos": "piano",
    "eletricos": "eletrico",
    "promocoes": "promocao",
    "devolucoes": "devolucao",
    "horarios": "horario",
    "pagamentos": "pagamento",
    "parcelas": "parcela",
    "trocas": "troca",
}


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(SINGULAR.get(w, w) for w in re.findall(r"[a-z0-9]+", folded))


def tokens(text: str) -> list[str]:
    return [w for w in normalize(text).split() if w not in STOPWORDS and len(w) > 1]
