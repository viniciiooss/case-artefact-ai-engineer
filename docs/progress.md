# Estado da execução

- Inspeção inicial: diretório vazio, sem Git ou implementação anterior.
- ZIP analisado; enunciado e seis CSVs/manual preservados.
- Especificação e plano escritos; execução autorizada pelo pedido de solução completa.
- Tasks 1–2 implementadas: catálogo/regras, RAG do PDF e sessões. Validação: 44 testes passaram.
- Tasks 3–4 completas: grafo LangGraph, provedores, demo explícito, API/CLI e UI responsiva.
- Task 5 completa: README, Docker/Compose, CI, avaliação e cinco conversas executadas.
- Revisão independente identificou quatro problemas importantes. Foram reproduzidos,
  corrigidos e verificados novamente, incluindo guard monetário por domínio e memória.
- Validação final: 92 testes, Ruff, 12/12 cenários HTTP, instalação wheel, CLI, Chrome/API
  real desktop/mobile, Docker build e contêiner healthy com UID 10001. Evidências em validation.md.
- Sem chamadas a provedores LLM reais; nenhuma publicação externa ou envio de mensagens.
- Repositório local preservado na branch feat/emporio-agent, sem branch-base anterior.
- Solicitação seguinte: case Yaitec analisado em checkout local; suporte OpenRouter e
  classificação sanitizada de falhas adaptados. Credenciais e documentos antigos preservados na origem.
- Validação da atualização: 108 testes e 12/12 cenários com o lock atualizado; integração nativa
  OpenRouter testada com transporte controlado, sem consumo de créditos. Detalhes em reuse-yaitec.md.
- Revisão final da atualização aprovada; mensagens da CLI por código verificadas sem exposição
  do texto bruto do provedor, incluindo códigos desconhecidos.
- Pedido de ativação e qualidade: `.env` local 0600 configurado; credenciais Langfuse autenticadas,
  chave OpenRouter recusada com HTTP 401. Usuário informado para atualizar a variável local.
- Usuário substituiu a chave OpenRouter: autenticação confirmada com HTTP 200 em GET /key,
  servidor recarregado e healthcheck local OK. Geração e lote pago ainda não executados.
- Langfuse e DeepEval adicionados como extras independentes; duas métricas G-Eval em português,
  quatro casos próprios e relatório local, sem juiz no atendimento. SDKs testados offline.
- Revisão reproduziu uploads de mídia antes do masking e notas de juiz fora da faixa. Ambos
  corrigidos com regressões: mídia desativada e notas finitas limitadas a 0..1 no relatório.
- Validação atual: 123 testes, 12/12 cenários determinísticos, Ruff, wheel com extras, Docker
  healthy em demo, Langfuse presente e DeepEval ausente da imagem de produção. Sem geração paga.
- Ambiente macOS: uv exigiu acesso à configuração de rede fora do sandbox; instalação autorizada.
  Um atributo UF_HIDDEN no .pth da instalação editável bloqueou imports e foi removido localmente.
