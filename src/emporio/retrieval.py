"""RAG local: seções/páginas reais do PDF, BM25 e expansão lexical em português."""

import hashlib
import re
from pathlib import Path

from pypdf import PdfReader
from rank_bm25 import BM25Okapi

from emporio.text import normalize, tokens

TITLES = {
    "1": "Sobre a Empório da Música",
    "1.1": "Missão",
    "1.2": "Dados da empresa",
    "2": "Horário de funcionamento",
    "3": "Formas de pagamento",
    "3.1": "Regras de parcelamento",
    "4": "Trocas e devoluções",
    "4.1": "Arrependimento em compras online",
    "4.2": "Trocas por defeito",
    "4.3": "Trocas por preferência",
    "4.4": "Itens não elegíveis para troca",
    "5": "Frete e entregas",
    "5.1": "Entregas em Campo Grande",
    "5.2": "Entregas para outras cidades",
    "5.3": "Código de rastreamento",
    "6": "Promoções e descontos",
    "6.1": "Tipos de promoção",
    "6.2": "Regras de promoções",
    "7": "Atendimento via WhatsApp",
    "7.1": "Diretrizes de atendimento",
    "7.2": "Fluxo de atendimento",
    "7.3": "Situações especiais",
    "8": "Garantia",
    "8.1": "Garantia legal",
    "8.2": "Garantia do fabricante",
    "8.3": "O que a garantia não cobre",
    "9": "Privacidade e proteção de dados",
    "10": "Disposições finais",
}
HEADINGS = re.compile(
    r"(?<![\d.])(?P<section>\d{1,2}\.\d+)\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])"
    r"|(?<![\d.])(?P<main>10|[1-9])\.\s+"
    r"(?=Sobre|Horário|Formas|Política|Promoções|Atendimento|Garantia|Privacidade|Disposições)"
)
EXPANSIONS = {
    "abrem": "horario funcionamento",
    "abre": "horario funcionamento",
    "aberto": "horario funcionamento",
    "fecha": "horario funcionamento",
    "sabados": "sabado",
    "domingos": "domingo",
    "endereco": "endereco rua centro",
    "devolver": "devolucao arrependimento",
    "arrependi": "arrependimento devolucao",
    "devolucao": "arrependimento devolucao",
    "parcelar": "parcelamento parcela",
    "parcela": "parcelamento parcela",
    "12x": "parcelamento parcela",
    "acumula": "cumulativas cumulatividade",
    "cumulativo": "cumulativas cumulatividade",
    "rastrear": "rastreamento codigo",
    "rastreio": "rastreamento codigo",
    "contato": "telefone whatsapp",
    "garantia": "garantia legal fabricante",
}


class PolicyIndex:
    def __init__(self, pdf_path: Path):
        self.pdf_path = Path(pdf_path)
        self.fingerprint = hashlib.sha256(self.pdf_path.read_bytes()).hexdigest()
        self.chunks = self._extract()
        self._documents = [tokens(c["title"] + " " + c["excerpt"]) for c in self.chunks]
        self._index = BM25Okapi(self._documents)

    def _extract(self) -> list[dict]:
        chunks, current = [], "1"
        for page_no, page in enumerate(PdfReader(self.pdf_path).pages, 1):
            text = re.sub(r"\s+", " ", page.extract_text() or "").strip()
            text = re.sub(r"Empório da Música Manual de Políticas e Procedimentos", "", text)
            text = re.sub(r"Página \d+", "", text).strip()
            matches = list(HEADINGS.finditer(text))
            boundaries = [(0, current)]
            for m in matches:
                section = m.group("section") or m.group("main")
                if section in TITLES:
                    boundaries.append((m.start(), section))
                    current = section
            boundaries.append((len(text), current))
            for (start, section), (end, _) in zip(boundaries, boundaries[1:], strict=False):
                content = text[start:end].strip()
                if len(content) < 45:
                    continue
                # Uma seção pode ocupar mais de uma página. As fontes preservam a página real.
                offset = 0
                while offset < len(content):
                    stop = min(offset + 1600, len(content))
                    if stop < len(content):
                        boundary = content.rfind(" ", offset + 1200, stop)
                        if boundary > offset:
                            stop = boundary
                    excerpt = content[offset:stop].strip()
                    chunk_id = f"policy-p{page_no}-{section}-{offset}"
                    chunks.append(
                        {
                            "id": chunk_id,
                            "kind": "policy",
                            "page": page_no,
                            "section": section,
                            "title": TITLES[section],
                            "reference": "politicas_da_loja.pdf",
                            "excerpt": excerpt,
                        }
                    )
                    if stop == len(content):
                        break
                    offset = stop - 150
        if not chunks:
            raise ValueError("O PDF de políticas não contém texto extraível.")
        return chunks

    def search(self, query: str, limit: int = 4) -> list[dict]:
        normalized = normalize(query)
        expansion = " ".join(v for k, v in EXPANSIONS.items() if k in normalized.split())
        words = tokens(normalized + " " + expansion)
        if not words:
            return []
        scores = self._index.get_scores(words)
        ranked = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        return [
            {**self.chunks[i], "score": round(float(scores[i]), 4)} for i in ranked if scores[i] > 0
        ][: max(1, min(limit, 8))]

    def section_sources(self, *sections: str) -> list[dict]:
        """Fontes exatas para cálculos que implementam regras específicas do manual."""
        return [c.copy() for c in self.chunks if c["section"] in sections]
