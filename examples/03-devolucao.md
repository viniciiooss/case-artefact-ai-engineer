# Devolução pede canal e recebimento real

Gerado por `uv run --no-sync python scripts/evaluate.py --write-examples`; execução real do serviço HTTP local, sem LLM.

- provider: `demo`
- model: `deterministic-v1`
- dataset_sha256: `4f4078fee1ec8fa8b660cfbc1b3de67d3b97da4ba5505800fc0dbacb8eb84c7c`
- policy_sha256: `b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7`

Os e-mails deste snapshot são fictícios; a identificação abaixo é exclusiva deste exemplo.

**Cliente:** Quero devolver meu instrumento por arrependimento

**Mel:** Vamos conferir as condições: a compra foi online ou presencial? E qual foi a data real de recebimento? Para arrependimento online, o manual prevê até 7 dias corridos do recebimento; a previsão do pedido não comprova essa data.

Ferramentas: `assess_return`.

- Fonte `policy-p4-4.1-0`: Arrependimento em compras online; página 4.
- Fonte `policy-p4-4.4-0`: Itens não elegíveis para troca; página 4.

**Cliente:** A compra foi online e recebi há 3 dias

**Mel:** Está dentro do prazo descrito no manual, sujeito às condições. São 3 dias; o prazo desta regra é 7 dias corridos.

Confirmar embalagem original, ausência de sinais de uso, acessórios e manuais. Personalização, venda final ou dúvidas de elegibilidade precisam de análise da equipe.

Posso orientar pelo manual; a equipe confirma a solicitação e as condições.

Ferramentas: `assess_return`.

- Fonte `policy-p4-4.1-0`: Arrependimento em compras online; página 4.
- Fonte `policy-p4-4.4-0`: Itens não elegíveis para troca; página 4.
