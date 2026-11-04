# Reaproveitamento do case Yaitec

O case anterior, **YAITEC RAG Assistant**, foi localizado e analisado no checkout local
do autor. Sua estrutura usa FastAPI, LangGraph, OpenAI/OpenRouter, embeddings,
PostgreSQL/pgvector, avaliação DeepEval, Langfuse e voz. A análise consultou README,
configuração, cliente LLM, grafo, retrieval, embeddings, guardrails e testes.

## Componentes e decisão

| Componente do case anterior | Aplicação no desafio Artefact |
| --- | --- |
| Seleção OpenAI/OpenRouter, chave independente e identificação da aplicação em `config.py`/`llm.py` | **Adaptado.** `EMPORIO_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, slug `xiaomi/mimo-v2.5` configurável e atribuição própria da Empório. |
| Erros de autenticação, modelo inválido e rate limit | **Adaptado.** Classificação sanitizada por status, incluindo créditos insuficientes e timeout. A CLI e o log operacional distinguem as causas; a API preserva sua mensagem genérica para o cliente. |
| Geração JSON e roteamento de fallback | **Contrato diferente.** O agente da Artefact precisa executar ferramentas comerciais e verificar grants. Usa `ChatOpenRouter.bind_tools` no grafo existente, sem trocar silenciosamente de modelo nem substituir uma falha por demo. |
| LangGraph e fontes anexadas no backend | **Padrão já presente.** A versão da Artefact mantém ferramentas tipadas e referências derivadas de seus resultados reais. |
| DeepEval/GEval, juiz em português e avaliação por dimensões | **Próxima evolução útil.** Adaptar rubricas para preço, estoque, regras de pagamento, devolução e privacidade. As perguntas de planos/SLA da Yaitec não avaliam uma loja de instrumentos. |
| Langfuse e captura de latência/tokens | **Próxima evolução útil.** Instrumentar geração/retrieval/ferramentas com dados mínimos e separar falha operacional de qualidade da resposta. A versão atual já oferece duração e resultado das ferramentas, sem exportação de traces. |
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
EMPORIO_MODEL=xiaomi/mimo-v2.5
OPENROUTER_API_KEY=sua-chave
```

Depois:

```bash
uv sync --locked --no-editable
uv run --no-sync emporio serve
```

O projeto Yaitec foi apenas consultado. Nenhuma chave, documento da empresa, pergunta
da base antiga ou credencial foi copiada. Os testes usam chaves fictícias e transporte
controlado, sem consumo de créditos e sem envio aos provedores.
