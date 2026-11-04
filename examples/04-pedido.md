# Pedido protegido antes e depois da identificação

Gerado por `uv run --no-sync python scripts/evaluate.py --write-examples`; execução real do serviço HTTP local, sem LLM.

- provider: `demo`
- model: `deterministic-v1`
- dataset_sha256: `4f4078fee1ec8fa8b660cfbc1b3de67d3b97da4ba5505800fc0dbacb8eb84c7c`
- policy_sha256: `b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7`

Os e-mails deste snapshot são fictícios; a identificação abaixo é exclusiva deste exemplo.

**Cliente:** Qual o status do pedido 1?

**Mel:** Para proteger seus dados, preciso que você identifique o pedido. Use Identificar pedido na web ou /verificar NUMERO EMAIL na CLI. Depois me peça o status novamente.

Ferramentas: `get_order`.


**Identificação explícita:** pedido 1, e-mail fictício `pedro.oliveira@jmail.com`.

Resultado do backend: `{"verified": true, "order_id": 1}`.

**Cliente:** Qual o status do pedido 1?

**Mel:** Pedido #1: entregue.
Total registrado: R$ 11.499,00.
Código de rastreamento: BRAB1234567BR.
Previsão registrada: 2025-10-25. Essa data não confirma recebimento nem foi atualizada pela transportadora.

Ferramentas: `get_order`.

- Fonte `order-1`: Pedido #1.
