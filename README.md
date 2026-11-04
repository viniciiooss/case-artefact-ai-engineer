# Empório da Música · Mel

Agente de atendimento em português brasileiro para o [desafio Artefact](docs/enunciado.pdf).
Mel tem uma voz acolhedora, informal e profissional. Consulta instrumentos, estoque,
preços, promoções, pedidos identificados e o manual da loja. Inclui chat web, CLI, API
HTTP, persistência local, testes e conversas reproduzíveis.

![Chat web da Empório da Música](docs/assets/welcome.png)

**O modo padrão `demo` é um simulador determinístico, não uma LLM.** Ele percorre o mesmo
grafo e as mesmas ferramentas sem chave e sem rede. OpenAI, OpenRouter e Ollama são escolhas explícitas;
falhas desses provedores não acionam fallback silencioso para demo.

## Executar em poucos minutos

O enunciado exige somente Python; frameworks, Docker e provedores são escolhas desta
implementação. Para executar localmente: Python **3.11 ou superior** e
[`uv`](https://docs.astral.sh/uv/getting-started/installation/). Não há build Node.
Execute os comandos a partir da raiz do repositório:

```bash
uv sync --locked --no-editable
uv run --no-sync emporio serve
```

Abra **http://127.0.0.1:8000**. O snapshot é validado e carregado na primeira execução;
`var/` guarda os bancos SQLite. `.env` é opcional no demo. A instalação por wheel
(`--no-editable`) também evita depender de arquivos `.pth` editáveis no macOS.
O `uv.lock` fixa as dependências; não é necessário regenerá-lo para executar.

```bash
uv run --no-sync emporio ask "Quero um violão até R$ 1.000"
uv run --no-sync emporio chat
uv run --no-sync emporio ingest
```

Na CLI interativa, `/verificar NÚMERO EMAIL` identifica um pedido, `/novo` apaga a conversa
atual e inicia outra, e `/sair` encerra. `ask` cria uma sessão temporária e a apaga ao final;
aceita `--order-id 1 --email pedro.oliveira@jmail.com`, dados fictícios do snapshot.
Conversas interativas ficam no SQLite local; a API permite apagá-las.

## Configurar uma LLM

Copie `.env.example` para `.env` se quiser personalizar. Escolha **um** dos modos:

```dotenv
# Sem chamadas externas; nenhuma chave necessária
EMPORIO_PROVIDER=demo
```

```dotenv
# Requer chave e acesso à API; sujeito ao custo do provedor
EMPORIO_PROVIDER=openai
EMPORIO_MODEL=gpt-4.1-mini
OPENAI_API_KEY=sua-chave
```

```dotenv
# OpenRouter: integração adaptada do case anterior da Yaitec
EMPORIO_PROVIDER=openrouter
EMPORIO_MODEL=xiaomi/mimo-v2.5
OPENROUTER_API_KEY=sua-chave
```

```dotenv
# Requer Ollama instalado e em execução, com modelo compatível com ferramentas
EMPORIO_PROVIDER=ollama
EMPORIO_MODEL=qwen3:8b
EMPORIO_OLLAMA_URL=http://localhost:11434
```

Para Ollama, faça `ollama pull qwen3:8b` antes de iniciar o atendimento. Os modelos são
configuráveis; o comportamento de tool calling depende do modelo e deve ser avaliado.
O [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini) é o baseline
compacto com suporte a ferramentas para a opção via API. Qwen3 8B permite explorar uma
opção local, com exigências de hardware e aderência às ferramentas que precisam ser medidas.
São padrões reproduzíveis e configuráveis, sem pressupor que sejam a melhor escolha para
todo ambiente. O modo demo torna a avaliação operacional possível sem contratar um provedor.
As integrações estão implementadas, mas os cenários em `examples/` e a avaliação
automática desta entrega usam somente demo. Não são evidência de qualidade de LLM real.
Testes de transporte controlado exercitam os SDKs OpenAI e OpenRouter, a serialização de
function calling e a execução real das ferramentas; eles não fazem chamadas aos provedores.

OpenRouter usa a integração nativa `langchain-openrouter`, com modelo no formato
`provedor/modelo`. O padrão `xiaomi/mimo-v2.5` reaproveita a seleção do case Yaitec;
a disponibilidade e o suporte a ferramentas dependem do catálogo do provedor.
São exigidos parâmetros compatíveis com as ferramentas, sem fallback automático para
outro endpoint ou provedor da aplicação. O backend identifica autenticação, créditos,
requisição inválida, limite de uso e timeout sem propagar mensagens brutas de erro.
Veja a [análise do reaproveitamento](docs/reuse-yaitec.md) e a
[integração oficial](https://openrouter.ai/blog/tutorials/langchain-chatopenrouter-setup/).

| Variável | Padrão | Finalidade |
| --- | --- | --- |
| `EMPORIO_PROVIDER` | `demo` | `demo`, `openai`, `openrouter` ou `ollama` |
| `EMPORIO_MODEL` | por provedor | `deterministic-v1`, `gpt-4.1-mini`, `xiaomi/mimo-v2.5` ou `qwen3:8b` |
| `EMPORIO_DATA_DIR` | `data` | Seis CSVs e PDF de políticas |
| `EMPORIO_STATE_DIR` | `var` | Catálogo, sessões e protocolos locais |
| `EMPORIO_MAX_TOOL_ROUNDS` | `4` | Limite de rodadas de ferramentas; de 1 a 8 |
| `EMPORIO_LLM_TIMEOUT` | `45` | Tempo limite de uma chamada ao provedor, em segundos |
| `EMPORIO_HISTORY_TURNS` | `10` | Janela de turnos enviada ao modelo; de 1 a 30 |
| `EMPORIO_TIMEZONE` | `America/Campo_Grande` | Data local para regras de prazo |
| `EMPORIO_OLLAMA_URL` | `http://localhost:11434` | Endereço do servidor Ollama |
| `EMPORIO_OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Endpoint do OpenRouter |
| `EMPORIO_OPENROUTER_SITE_URL` | `http://127.0.0.1:8000` | Identificação da aplicação no OpenRouter |

`OPENAI_API_KEY` é exigida em `openai`; `OPENROUTER_API_KEY`, em `openrouter`.
As chaves são independentes. Não versione `.env` nem bancos de sessão.
Nos modos OpenAI e OpenRouter, mensagens, contexto e resultados de ferramentas são enviados à API;
em Ollama, ao servidor configurado. E-mail e token de sessão não integram o schema da LLM.

## Docker

Com Docker e Compose **2.24.0 ou superior**, o demo funciona sem `.env` (suporte a
[`env_file` opcional](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/)):

```bash
docker compose up --build
```

Abra http://127.0.0.1:8000. A imagem usa Python 3.12, dependências do lock, usuário sem
privilégios de root, dados em `/app/data`, porta 8000 e volume persistente para `/app/var`.
O healthcheck usa a biblioteca padrão do Python. Para parar: `docker compose down`;
`docker compose down --volumes` também elimina o histórico armazenado no volume.
Para Ollama em outra máquina ou no host, configure `EMPORIO_OLLAMA_URL` com um endereço
alcançável pelo contêiner; `localhost` dentro dele aponta para o próprio contêiner.

## API HTTP

```bash
curl http://127.0.0.1:8000/api/health
curl -X POST http://127.0.0.1:8000/api/sessions
```

A criação retorna `session_id` e `token` apenas uma vez. Substitua os valores abaixo:

```bash
curl -X POST http://127.0.0.1:8000/api/sessions/SESSION_ID/messages \
  -H 'Authorization: Bearer TOKEN' -H 'Content-Type: application/json' \
  -d '{"message":"Quanto custa Takamine GD20?"}'

curl -X POST http://127.0.0.1:8000/api/sessions/SESSION_ID/order-access \
  -H 'Authorization: Bearer TOKEN' -H 'Content-Type: application/json' \
  -d '{"order_id":1,"email":"pedro.oliveira@jmail.com"}'
```

O segundo comando exemplifica identificação explícita com e-mail fictício. Só depois
dela o mesmo token pode consultar aquele pedido. A resposta do chat traz `message`,
`sources`, `tools`, `provider`, `model`, `latency_ms` e `context`; a UI apresenta as fontes.

| Método e rota | Uso |
| --- | --- |
| `GET /api/health` | Provedor, modelo e contagens; não testa conectividade da LLM |
| `POST /api/sessions` | Criar sessão e receber credencial |
| `POST /api/sessions/{id}/messages` | Enviar `{message}`; entre 1 e 4.000 caracteres |
| `GET /api/sessions/{id}` | Histórico e números de pedidos autorizados |
| `GET /api/sessions/{id}/history` | Somente mensagens públicas |
| `POST /api/sessions/{id}/order-access` | Validar `{order_id,email}` no backend |
| `DELETE /api/sessions/{id}` | Excluir histórico, grants e protocolos da sessão |
| `GET /api/products` | Catálogo público disponível; filtros `query`, `category`, `max_price_brl`, `limit` |
| `GET /api/policies/document` | PDF original para conferir páginas citadas |

Todas as rotas que contêm `{id}` exigem Bearer token. Entradas inválidas retornam 422;
credenciais ausentes, 401; sessão inacessível, 404; identificação incorreta, 403;
tentativas excessivas de identificação, 429; turno concorrente, 409; provedor indisponível,
503. Erros não retornam chaves, e-mails ou exceções internas.

## Por que esta arquitetura

O ciclo explícito **modelo → ferramentas → modelo** em LangGraph permite delimitar rodadas,
validar argumentos, rastrear ferramentas e interromper loops. Function calling fornece
contratos tipados; o servidor executa a operação e verifica autorização. É um padrão de
ação e observação, sem persistir nem expor cadeia de pensamento. Veja o
[quickstart do LangGraph](https://docs.langchain.com/oss/python/langgraph/quickstart), o
[guia de function calling da OpenAI](https://developers.openai.com/api/docs/guides/function-calling)
e a [integração ChatOllama](https://docs.langchain.com/oss/python/integrations/chat/ollama).

| Necessidade | Escolha e justificativa |
| --- | --- |
| Preço, estoque, promoções e pedidos | SQL parametrizado e funções específicas sobre SQLite. Cálculos em centavos fora da LLM. Um agente com SQL arbitrário aumentaria o acesso e dificultaria controlar dados pessoais. |
| Manual de oito páginas | RAG BM25 local, normalizado em português, com trechos por seção/página. Evita dependência remota de embeddings e infraestrutura vetorial sem necessidade demonstrada para este corpus curto. Busca lexical tem limites com paráfrases. |
| Conversa e autorização | Outro SQLite para mensagens públicas, contexto mínimo, hashes dos tokens e grants por sessão/pedido. Histórico ajuda a resolver referências; preço e estoque são consultados novamente. |
| Interfaces | FastAPI, Typer e HTML/CSS/JS local compartilham o mesmo serviço; nenhuma regra comercial depende do navegador. |

Detalhes, fluxo e limites estão em [architecture.md](docs/architecture.md).

## Regras, dados e limites

Os CSVs e o PDF são **dados fictícios de um snapshot fornecido**, preservados sem correções
silenciosas; não há ERP nem rastreamento de transportadora ao vivo. Existem 65 produtos
(61 disponíveis), 20 pedidos, 50 clientes fictícios, 25 promoções e 28 trechos de políticas.
Somente produto `active` com estoque positivo está disponível; promoção exige `is_active=1`.
A maior promoção ativa não acumula com PIX; sem promoção, PIX aplica 5%. Centavos usam
arredondamento HALF_UP e parcelas preservam o total.

As ambiguidades são tratadas explicitamente:

- **Contatos:** telefone geral `(67) 3341-4444` e WhatsApp dedicado `(67) 3321-4500` têm
  funções distintas. O manual traz e-mails divergentes; a orientação evita escolher um
  silenciosamente e prefere os telefones documentados.
- **Parcelas mínimas:** tabela geral cita R$ 100; seção 3.1 detalha R$ 80 em 4–6x e R$ 100
  em 7–12x. A exceção abaixo de R$ 50 em até 3x exige confirmação humana.
- **Frete de Campo Grande:** acima de R$ 500 é gratuito; abaixo, R$ 35. Exatamente
  R$ 500 exige confirmação. Outras cidades precisam de cotação, sem inventar abrangência.
- **Recebimento:** previsão do CSV não comprova entrega real. Arrependimento online pede
  canal e data real do recebimento para conferir sete dias corridos e demais condições.

Status inconsistentes com estoque e os dois totais históricos divergentes da soma do
catálogo atual são registrados em [data-quality.md](docs/data-quality.md). O valor do pedido
é o histórico registrado; não é recalculado pelos preços de hoje. O manual é referência
interna, sem substituir análise de direitos legais. Exceções precisam da equipe.

Mel não compra, reserva, altera estoque, cancela nem emite reembolso. O encaminhamento
gera protocolo **local**; não envia aviso à equipe. Temas alheios e acessórios recebem
redirecionamento. O demo reconhece cenários limitados; linguagem aberta exige avaliar uma LLM.

As ferramentas não recebem SQL arbitrário, tabela de clientes ou credencial de sessão.
Pedidos verificam grants no backend mesmo diante de instruções maliciosas. Token é aleatório
e só seu hash é guardado no servidor; há limites de mensagem, histórico, resultados,
rodadas e tentativas de identificação. A UI renderiza mensagens como texto e permite
apagar conversas. Há uma defesa heurística para conferir valores monetários e domínios
de preço/estoque/pedido contra fontes do turno; ela não garante correção semântica de toda
resposta. Esses controles demonstram isolamento; produção ainda precisa de login/OTP,
política de retenção, rate limit geral, HTTPS, gestão de segredos, observabilidade operacional,
integração com ERP/transportadoras e avaliação real dos provedores e da privacidade.
As chamadas reais têm teto de 1.600 tokens de saída, timeout configurável e, na OpenAI,
uma tentativa adicional para falhas transitórias. No OpenRouter, tentativas automáticas
do SDK estão desativadas para respeitar o tempo limite do turno. Esses limites controlam consumo;
o healthcheck verifica o serviço e os dados, sem testar conectividade do provedor.

## Verificar e reproduzir exemplos

```bash
uv sync --locked --no-editable
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest
uv run --no-sync python scripts/evaluate.py
uv run --no-sync python scripts/evaluate.py --write-examples --report var/evaluation.json
```

`make check` executa lint, testes e avaliação. O workflow de CI repete esses comandos
com Python 3.11 e 3.12 e constrói a imagem Docker, sem publicar. A existência do workflow
não comprova execução no GitHub; resultados locais são descritos em
[validation.md](docs/validation.md).

A avaliação executa o serviço via HTTP em processo, com bancos temporários, sem mocks
de respostas. Os 12 cenários verificam conteúdo esperado/proibido, ferramentas, páginas,
fontes reais, orçamento, regras comerciais e isolamento entre conversas. Falhas produzem
código de saída 1. É uma avaliação de regressão determinística e grounding estrutural;
não mede compreensão livre, precisão estatística nem qualidade de LLM por juiz automático.

As **cinco conversas** de [examples/](examples/) são geradas por execução real do demo e
incluem provedor, modelo e hashes dos dados: catálogo/PIX, políticas, devolução em dois
turnos, pedido antes/depois da identificação e limites/promoção sem acumular.

## Entrega e assistência de código

Este diretório é a entrega em repositório Git local com histórico. Publicação no GitHub
e envio por e-mail dependem de uma ação externa autorizada e não são feitos pelo aplicativo.
Codex/ChatGPT foi utilizado na análise, implementação, elaboração de testes, revisão
automatizada e assistência de código. Isso não implica validação humana nem validação
com LLM real; consulte os comandos e limites da evidência de execução documentada.
