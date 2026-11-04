# Limites do atendimento e promoção sem acumular PIX

Gerado por `uv run --no-sync python scripts/evaluate.py --write-examples`; execução real do serviço HTTP local, sem LLM.

- provider: `demo`
- model: `deterministic-v1`
- dataset_sha256: `4f4078fee1ec8fa8b660cfbc1b3de67d3b97da4ba5505800fc0dbacb8eb84c7c`
- policy_sha256: `b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7`

Os e-mails deste snapshot são fictícios; a identificação abaixo é exclusiva deste exemplo.

**Cliente:** Vocês vendem cabos e pedais?

**Mel:** A Empório trabalha exclusivamente com instrumentos musicais; não vendemos acessórios como cabos, pedais, amplificadores ou jogos de cordas. Posso ajudar a encontrar um instrumento para você.

Ferramentas: `nenhuma`.


**Cliente:** Qual a previsão do tempo amanhã?

**Mel:** Por aqui posso ajudar com instrumentos musicais, pedidos e políticas da Empório da Música. Sobre outros assuntos, não tenho informações confiáveis para te orientar. O que você procura na loja?

Ferramentas: `nenhuma`.


**Cliente:** Quanto custa Crafter HT-100 no PIX?

**Mel:** Para Crafter HT-100 Folk Aço Natural (1 unidade(s)):
• Preço de tabela por unidade: R$ 2.399,00.
• Total dos produtos: R$ 1.967,18 com 18% de desconto.
• Promoção ativa aplicada. O desconto PIX não acumula com a promoção.
É uma simulação, sem reserva de estoque ou realização de compra.

Ferramentas: `search_products, quote_product`.

- Fonte `product-90`: Crafter HT-100 Folk Aço Natural.
- Fonte `policy-p3-3-0`: Formas de pagamento; página 3.
- Fonte `policy-p3-3.1-0`: Regras de parcelamento; página 3.
- Fonte `policy-p6-6.2-0`: Regras de promoções; página 6.
