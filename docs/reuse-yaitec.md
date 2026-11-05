# Reaproveitamento do case Yaitec

O case anterior, **YAITEC RAG Assistant**, foi localizado e analisado no checkout local
do autor. Sua estrutura usa FastAPI, LangGraph, OpenAI/OpenRouter, embeddings,
PostgreSQL/pgvector, avaliação DeepEval, Langfuse e voz. A análise consultou README,
configuração, cliente LLM, grafo, retrieval, embeddings, guardrails e testes.

## Componentes e decisão

| Componente do case anterior | Aplicação no desafio Artefact |
| --- | --- |
| Seleção OpenAI/OpenRouter, chave independente e identificação da aplicação em `config.py`/`llm.py` | **Adaptado.** `EMPORIO_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, modelo configurável e atribuição própria da Empório. O modelo inicial foi atualizado para `xiaomi/mimo-v2.6-pro` a pedido do usuário. |
| Erros de autenticação, modelo inválido e rate limit | **Adaptado.** Classificação sanitizada por status, incluindo créditos insuficientes e timeout. A CLI e o log operacional distinguem as causas; a API preserva sua mensagem genérica para o cliente. |
| Geração JSON e roteamento de fallback | **Contrato diferente.** O agente da Artefact precisa executar ferramentas comerciais e verificar grants. Usa `ChatOpenRouter.bind_tools` no grafo existente, sem trocar silenciosamente de modelo nem substituir uma falha por demo. |
| LangGraph e fontes anexadas no backend | **Padrão já presente.** A versão da Artefact mantém ferramentas tipadas e referências derivadas de seus resultados reais. |
| DeepEval/GEval, juiz em português e avaliação por dimensões | **Adaptado.** Extra `eval`, juiz OpenRouter com schemas validados, duas métricas em português, quatro casos rápidos e banco golden de 60 casos próprios. Executa fora do atendimento, com relatório e falhas explícitas. |
| Langfuse e captura de latência/tokens | **Adaptado.** Extra `observability`, callback nativo no grafo, spans de ferramentas/modelo, tokens quando disponíveis e hash por conversa. Conteúdo e erros brutos são omitidos; exportação em background e flush no encerramento. |
| pgvector/HNSW, embeddings e top-k adaptativo | **Requer experimento próprio.** Os limiares de distância cosseno não se aplicam a scores BM25. Para oito páginas, manter a recuperação local atual e comparar alternativas quando houver evidência de falha ou expansão do corpus. |
| Voz STT/TTS e seleção de modelo no navegador | **Fora da mudança atual.** São extensões possíveis, mas o escopo da Artefact pede mensagens de texto; configuração do provedor continua no backend. |
| Guardrail baseado apenas em quantidade de fontes | **Validação atual preservada.** Uma fonte de política não sustenta um preço de produto ou status de pedido. A implementação atual também verifica valores e domínio das afirmações. |

## Adaptação do OpenRouter

O case anterior chama a API compatível com OpenAI por `AsyncOpenAI(base_url=...)` e pede
resposta JSON. A versão da Artefact usa o pacote nativo `langchain-openrouter`, mantendo
o fluxo modelo → ferramentas → modelo. Essa integração e o suporte a ferramentas são
descritos na [documentação do OpenRouter](https://openrouter.ai/blog/tutorials/langchain-chatopenrouter-setup/).

O catálogo público consultado listava suporte a `tools` para
[`xiaomi/mimo-v2.5`](https://openrouter.ai/api/v1/models/xiaomi/mimo-v2.5/endpoints).
Isso orientou a configuração padrão; não comprova a qualidade do modelo para o case.
Após o pedido de atualização, o atendimento passou para
[`xiaomi/mimo-v2.6-pro`](https://openrouter.ai/xiaomi/mimo-v2.6-pro) e o juiz para
[`z-ai/glm-5.3`](https://openrouter.ai/z-ai/glm-5.3) com `reasoning.effort=max`.
O juiz tem orçamento e timeout próprios da avaliação e não participa do atendimento.
Em uma atualização posterior solicitada pelo usuário, os padrões passaram para
Claude Haiku 5.5 no atendimento e GPT-6 Luna no juiz, ainda pelo OpenRouter. Os parâmetros
de temperatura são omitidos nesses dois modelos, conforme seu suporte; a preferência
local de endpoint do atendimento passou de Xiaomi para Anthropic.
`require_parameters=true` exige suporte aos parâmetros enviados; veja
[roteamento de provedores](https://openrouter.ai/docs/guides/routing/provider-selection).

O SDK nativo usado no lock aceita timeout em milissegundos. O valor configurado em
segundos é convertido explicitamente. Seu retry implícito foi desativado por requisição
para evitar backoff prolongado, mesmo quando o wrapper recebe `max_retries=0`.
Essas condições têm testes que usam o SDK real com `httpx.MockTransport`.

## Configurar

No `.env` deste projeto:

```dotenv
EMPORIO_PROVIDER=openrouter
EMPORIO_MODEL=anthropic/claude-haiku-5.5
EMPORIO_OPENROUTER_PROVIDER_ORDER=["Anthropic"]
EMPORIO_ATTENDANT_REASONING_EFFORT=none
EMPORIO_EVAL_MODEL=openai/gpt-6-luna
EMPORIO_EVAL_REASONING_EFFORT=max
OPENROUTER_API_KEY=sua-chave
```

Depois:

```bash
uv sync --locked --no-editable --extra observability
uv run --no-sync emporio serve
```

Na primeira adaptação, o projeto Yaitec foi apenas consultado. Após o pedido explícito
para configurar as integrações, somente as chaves necessárias de OpenRouter e Langfuse
foram copiadas para o `.env` local, com permissão 0600 e ignorado por Git/Docker. O projeto
de origem não foi alterado. Documentos da empresa e perguntas da base antiga não foram
copiados. Os testes automatizados continuam usando chaves fictícias e transporte controlado.

## Por que a integração permanece pequena

Langfuse usa o callback já compatível com LangGraph, sem serviço adicional no Compose.
O projeto das credenciais é reutilizado, com ambiente e tags próprios da Empório. DeepEval
fica em um extra separado e usa G-Eval com etapas fixas, sem uma plataforma própria de
avaliação, sem login na Confident AI e sem chamadas de juiz no fluxo de atendimento.

O adaptador atende ao contrato schema-aware do
[DeepEval](https://deepeval.com/guides/guides-using-custom-llms); as
[métricas G-Eval](https://deepeval.com/docs/metrics-llm-evals) usam somente parâmetros
referenciados em seus critérios. O tracing segue a
[integração LangGraph](https://langfuse.com/integrations/frameworks/langchain) e o
[masking de exportação](https://langfuse.com/docs/observability/features/masking)
do SDK Langfuse 5. Os detalhes e limites observados estão em [validation.md](validation.md).

## Dataset e teste manual

O banco de perguntas da Yaitec organiza 60 perguntas em seis grupos. A adaptação mantém
esses grupos com dez casos próprios de cada: qualidade, contexto, fontes, alucinação,
fora da base e injeção de instruções. O [golden JSONL](../evals/golden_emporio.jsonl)
acrescenta referências e verificações exatas de valores, ferramentas, fontes e isolamento
de autorização. Pré-condições de pedido são aplicadas pelo backend, sem passar e-mail ao juiz.

O runner existente aceita JSON/JSONL, filtros por grupo e ID, resumo por grupo e
validação sem modelos. Critérios, limiares e instruções constam em
[evals/README.md](../evals/README.md). Não foi copiado o conteúdo comercial da Yaitec,
seus modelos antigos, a média ponderada ou o painel de configuração: o banco usa as
métricas e o fluxo existentes da Empório. O [roteiro manual](teste-manual.md) permite
testar as mesmas regras pela interface.
