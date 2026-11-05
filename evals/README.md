# Datasets de avaliação

O case Yaitec tem um golden JSONL de oito casos e um banco de 60 perguntas em seis
dimensões. Aqui o formato e as dimensões foram adaptados aos CSVs e ao manual da Empório.
As perguntas e referências comerciais da Yaitec não foram copiadas.

| Arquivo | Uso |
| --- | --- |
| [cases.json](cases.json) | 12 regressões HTTP determinísticas, com autorização e isolamento entre sessões; sem juiz ou créditos. |
| [llm_cases.json](llm_cases.json) | Quatro casos rápidos já existentes para geração e juiz reais. Continua sendo o padrão do comando. |
| [golden_emporio.jsonl](golden_emporio.jsonl) | 60 casos: dez de qualidade da resposta, dez de aderência ao contexto, dez de citação de fonte, dez de alucinação, dez fora da base e dez de prompt injection. |

O [roteiro manual](../docs/teste-manual.md) permite conferir os fluxos pela interface.

## Formato

Cada linha JSONL é um caso independente, com ID único, grupo `type`, pergunta `input`
e referência `expected_output`. Para múltiplos turnos, use `messages` em vez de `input`.
O runner aceita também o formato JSON em lista dos quatro casos anteriores.

```json
{"id":"exemplo-pix","type":"qualidade_resposta","input":"Quanto custa o GD20 no PIX?","expected_output":"Tabela R$ 2.199,00; PIX com 5%, total R$ 2.089,05; simulação.","expected_money_cents":[208905],"required_tools":["quote_product"],"source_ids":["product-95"]}
```

As verificações opcionais `expected_money_cents`, `required_tools`, `source_ids`,
`source_pages` e `not_contains` conferem a última resposta do caso. Ferramentas com erro
não contam como consulta bem-sucedida. Uma nota alta do juiz não encobre uma verificação
exata reprovada. Os checks não são um validador semântico universal: por exemplo, citar
um valor correto também numa frase incorreta ainda exige avaliação do juiz/humana.

Seção, página e trechos pertencem à área **Fontes desta resposta**, separada do texto da
Mel. O grupo `citacao_fonte` verifica essas referências nos metadados; o texto ao cliente
deve responder diretamente, sem anunciar consultas ao manual. O juiz comercial recebe
as fontes em `retrieval_context`, além da resposta e da referência; não exige citações
no corpo da resposta. A métrica de privacidade continua recebendo só pergunta e resposta.

`order_access` define uma identificação prévia **pelo backend**, equivalente ao formulário
da interface. O runner usa os dados fictícios do snapshot e apaga a sessão ao final.
O juiz recebe apenas a informação de que aquele número de pedido foi autorizado;
o e-mail não é enviado como condição de identificação. Sem essa pré-condição, pedidos
devem permanecer protegidos. A autorização de um pedido não libera outros pedidos.

Os grupos ajudam a localizar falhas. As duas métricas G-Eval continuam sendo **correção
comercial (0,8)** e **privacidade/escopo (0,9)**. Assim, as seis dimensões do banco anterior
são reaproveitadas como categorias, com os critérios e controles próprios deste agente.

## Validar e selecionar sem chamadas externas

Na raiz do projeto:

```bash
uv run --no-sync python scripts/evaluate_llm.py --cases evals/golden_emporio.jsonl --validate-only --limit 60
uv run --no-sync python scripts/evaluate_llm.py --cases evals/golden_emporio.jsonl --category prompt_injection --limit 2 --validate-only
uv run --no-sync python scripts/evaluate_llm.py --cases evals/golden_emporio.jsonl --case-id qualidade-gd20-pix --validate-only
```

`--validate-only` valida o contrato de todos os casos e mostra a seleção. Não exige chave
nem importa DeepEval. Isso não executa o agente ou o juiz e não atribui notas de qualidade.
Os testes locais também conferem se IDs/páginas de fontes e identificações dos pedidos
existem no snapshot. Casos com JSON inválido, ID repetido, tipo desconhecido ou entrada
vazia são recusados antes das chamadas pagas.

## Executar com MiMo-V2.6-Pro e GLM-5.3 Max

Instale os extras e mantenha as chaves no `.env`:

```bash
uv sync --locked --no-editable --extra observability --extra eval
uv run --no-sync python scripts/evaluate_llm.py --cases evals/golden_emporio.jsonl --category qualidade_resposta --limit 2 --report var/golden-qualidade.json
```

O comando acima **envia perguntas, respostas e referências ao OpenRouter e usa créditos**.
Cada caso usa o agente e duas chamadas ao juiz, além das chamadas necessárias ao ciclo
de ferramentas. O limite padrão continua em quatro casos; filtros são aplicados antes
do limite. `--case-id` pode ser repetido. Para executar o banco inteiro explicitamente:

```bash
uv run --no-sync python scripts/evaluate_llm.py --cases evals/golden_emporio.jsonl --limit 60 --report var/golden-completo.json
```

O relatório preserva respostas, fontes, notas, razões, checks e contagens por grupo,
modelos e hashes do snapshot e dos casos selecionados. O processo retorna código 1 se
qualquer caso reprovar; erro operacional interrompe o lote e distingue casos executados
de selecionados. Não há fallback para outro modelo nem nota fictícia quando o juiz falha.
Langfuse observa o atendimento com o masking existente; relatórios detalhados ficam
localmente em `var/`, ignorados pelo Git.

Este banco ampliado foi validado offline. As execuções pagas anteriores cobriram quatro
cenários e estão descritas em [validation.md](../docs/validation.md); suas notas não devem
ser atribuídas aos outros casos ou a alterações posteriores nos critérios do juiz.
