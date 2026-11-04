# Qualidade e interpretação do snapshot

Os seis CSVs e o manual de oito páginas foram fornecidos para o desafio e preservados.
Clientes, e-mails e pedidos são fictícios; não constituem uma conexão real com ERP.
As contagens abaixo foram calculadas diretamente dos arquivos com `csv.DictReader` e
os valores monetários comparados com `Decimal`, sem alterar o material original.

| Arquivo | Registros |
| --- | ---: |
| `categories.csv` | 9 |
| `products.csv` | 65 |
| `customers.csv` | 50 |
| `orders.csv` | 20 |
| `order_items.csv` | 22 |
| `promotions.csv` | 25 |

Não foram encontrados IDs primários duplicados nas cinco entidades com ID próprio, nem
referências ausentes entre produtos/categorias, pedidos/clientes, promoções/produtos e
itens/pedidos/produtos. A ingestão valida essas relações, preços e estruturas, e realiza
a substituição transacional por hash. O manual produz 28 trechos com páginas preservadas.

## Disponibilidade e promoções

São 62 produtos `active`, dois `discontinued` e um `coming_soon`. A condição de venda é
**status active e estoque maior que zero**, resultando em 61 disponíveis.

| Produto | Status | Estoque | Interpretação |
| --- | --- | ---: | --- |
| #96 Giannini GF-3D Dreadnought Sunburst | `active` | 0 | Esgotado |
| #113 Shelby SN-7C 7 Cordas Nylon Natural | `discontinued` | 0 | Descontinuado |
| #130 Kala KA-ABP-CTG Barítono Cedar | `coming_soon` | 2 | Em breve, indisponível mesmo com estoque |
| #136 Ibanez Bass 2X Electric Bass | `discontinued` | 13 | Descontinuado, indisponível mesmo com estoque |

Há 25 registros de promoção, dos quais quatro ativos: #127 (10%), #121 (20%), #90 (18%)
e #94 (8%). Não há datas de vigência no CSV; `is_active` é a evidência disponível.
Descrições como “Black Friday” não autorizam reativar ofertas. Takamine GD20 (#95) custa
R$ 2.199,00: seu desconto de 12% está inativo. Promoções repetidas de um produto não
acumulam; a implementação seleciona a maior ativa. PIX também não acumula com promoção.

## Pedidos e valores históricos

Status dos 20 pedidos: sete `delivered`, um `shipped`, quatro `confirmed`, quatro `pending`
e quatro `cancelled`. Datas/previsões são históricas e não mudam automaticamente com o
relógio da aplicação. Uma previsão passada não prova que o pedido foi recebido.

`order_items.csv` tem quantidade e produto, sem preço unitário histórico. Comparar sua
soma com o catálogo atual revela duas diferenças; não prova erro do total original:

| Pedido | Total registrado | Soma dos itens ao preço de tabela atual | Diferença |
| --- | ---: | ---: | ---: |
| #3 | R$ 3.450,00 | R$ 3.498,00 | R$ 48,00 |
| #20 | R$ 1.400,00 | R$ 1.488,00 | R$ 88,00 |

Não é possível reconstruir preço vigente, descontos e condições comerciais da compra
com esses campos. O serviço apresenta `orders.total_brl` como **total registrado**,
sem sobrescrever nem recalcular a história. Rastreio é o código fornecido, sem consulta
ao transportador e sem prometer previsão atualizada.

## Ambiguidades do manual

| Tema | Evidência e tratamento |
| --- | --- |
| Contatos | Telefone geral `(67) 3341-4444` e WhatsApp dedicado da seção 7 `(67) 3321-4500` têm papéis distintos. Há e-mails divergentes no manual; não escolher um silenciosamente. |
| Parcela mínima | A tabela geral indica R$ 100; seção 3.1 especifica R$ 80 em 4–6x e R$ 100 em 7–12x. Aplicar a regra detalhada e pedir equipe para a exceção abaixo de R$ 50 em até 3x. |
| Frete | Campo Grande acima de R$ 500 é gratuito, abaixo é R$ 35; exatamente R$ 500 não está definido. Outras cidades e abrangência metropolitana exigem confirmação/cotação. |
| Devolução | Arrependimento online conta sete dias corridos do recebimento real. Perguntar canal/data faltantes; nunca usar `estimated_delivery` como recebimento. |
| Defeito/garantia | A seção de troca por defeito fala em 30 dias e a garantia em 90. São referências distintas; encaminhar dúvidas e evitar afirmar perda de direitos legais. |

O texto é manual interno de referência, sem substituir análise humana ou jurídica.
Condições de personalização/venda final não resolvem isoladamente direitos legais.

## Conferir as diferenças

Depois de instalar as dependências, execute na raiz:

```bash
uv run --no-sync python - <<'PY'
import csv
from collections import Counter
from decimal import Decimal
from pathlib import Path

tables = {p.stem: list(csv.DictReader(p.open())) for p in Path("data").glob("*.csv")}
print({name: len(rows) for name, rows in tables.items()})
for name in ("products", "orders"):
    print(name, Counter(row["status"] for row in tables[name]))
products = {row["product_id"]: row for row in tables["products"]}
for order in tables["orders"]:
    current = sum(
        Decimal(products[item["product_id"]]["price_brl"]) * int(item["quantity"])
        for item in tables["order_items"] if item["order_id"] == order["order_id"]
    )
    if current != Decimal(order["total_brl"]):
        print(order["order_id"], "registrado", order["total_brl"], "catálogo atual", current)
PY
```

As conversas em `examples/` incluem SHA-256 combinado dos CSVs e hash do PDF para
identificar exatamente a carga avaliada. Esses hashes identificam conteúdo; não provam
que o conteúdo seja correto, recente ou validado por uma pessoa.
