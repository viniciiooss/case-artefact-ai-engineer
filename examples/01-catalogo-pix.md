# Catálogo com orçamento e continuação no PIX

Gerado por `uv run --no-sync python scripts/evaluate.py --write-examples`; execução real do serviço HTTP local, sem LLM.

- provider: `demo`
- model: `deterministic-v1`
- dataset_sha256: `4f4078fee1ec8fa8b660cfbc1b3de67d3b97da4ba5505800fc0dbacb8eb84c7c`
- policy_sha256: `b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7`

Os e-mails deste snapshot são fictícios; a identificação abaixo é exclusiva deste exemplo.

**Cliente:** Quero um violão até R$ 1.000

**Mel:** Consultei o catálogo. Olha o que encontrei:

• Tagima Memphis AC-39 Nylon Natural — R$ 429,90 (preço de tabela; sem promoção ativa). 15 em estoque.

• Rozini RC-104 Nylon Estudante — R$ 459,90 (preço de tabela; sem promoção ativa). 10 em estoque.

• Shelby SN-100 Folk Aço Preto — R$ 549,00 (preço de tabela; sem promoção ativa). 5 em estoque.

• Giannini GF-1R Aço Folk Sunburst — R$ 579,90 (preço de tabela; sem promoção ativa). 7 em estoque.

• Yamaha C40 Nylon Natural — R$ 599,90 (preço de tabela; sem promoção ativa). 12 em estoque.

• Giannini GN-15 Nylon Cedr Natural — R$ 689,00 (preço de tabela; sem promoção ativa). 6 em estoque.

Quer detalhes de algum modelo ou uma simulação no PIX/parcelada?

Ferramentas: `search_products`.

- Fonte `product-83`: Tagima Memphis AC-39 Nylon Natural.
- Fonte `product-85`: Rozini RC-104 Nylon Estudante.
- Fonte `product-89`: Shelby SN-100 Folk Aço Preto.
- Fonte `product-88`: Giannini GF-1R Aço Folk Sunburst.
- Fonte `product-81`: Yamaha C40 Nylon Natural.
- Fonte `product-84`: Giannini GN-15 Nylon Cedr Natural.

**Cliente:** O primeiro no PIX

**Mel:** Para Tagima Memphis AC-39 Nylon Natural (1 unidade(s)):
• Preço de tabela por unidade: R$ 429,90.
• Total dos produtos: R$ 408,41 com 5% de desconto.
É uma simulação, sem reserva de estoque ou realização de compra.

Ferramentas: `quote_product`.

- Fonte `product-83`: Tagima Memphis AC-39 Nylon Natural.
- Fonte `policy-p3-3-0`: Formas de pagamento; página 3.
- Fonte `policy-p3-3.1-0`: Regras de parcelamento; página 3.
- Fonte `policy-p6-6.2-0`: Regras de promoções; página 6.
