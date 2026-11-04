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
- Na entrega inicial, sem chamadas a provedores LLM reais. Nenhuma publicação externa ou envio de mensagens.
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
  servidor recarregado e healthcheck local OK.
- Langfuse e DeepEval adicionados como extras independentes; duas métricas G-Eval em português,
  quatro casos próprios e relatório local, sem juiz no atendimento. SDKs testados offline.
- Revisão reproduziu uploads de mídia antes do masking e notas de juiz fora da faixa. Ambos
  corrigidos com regressões: mídia desativada e notas finitas limitadas a 0..1 no relatório.
- Usuário autorizou explicitamente o lote pago: quatro casos executados com os modelos iniciais,
  2/4 aprovados. Primeiro relatório preservado; acompanhamento de PIX, simulação e separação
  das dimensões da rubrica corrigidos. Limiares e referências comerciais mantidos.
- Langfuse confirmou 70 observações reais do primeiro lote, com seis raízes e inputs/outputs
  vazios, modelo e tokens presentes. Sem conteúdo de conversas nos traces.
- Usuário pediu MiMo-V2.6-Pro e GLM-5.3 Max: modelos configurados, esforço max explícito no
  juiz, orçamento de 8.192 tokens e timeout de 120 segundos separados do runtime.
- Primeiro endpoint do novo MiMo (DeepInfra) retornou 429; chave válida e com limite disponível.
  Atendimento local encaminhado ao endpoint Xiaomi, mantendo modelo e fallback desativado.
- Validação atual: 142 testes, 12/12 cenários determinísticos, Ruff, wheel com extras, Docker
  reconstruído e healthy em demo; Langfuse presente, DeepEval e .env ausentes da imagem.
- Servidor local recarregado com MiMo-V2.6-Pro; health e página inicial HTTP 200 na porta 8000.
- Último lote completo com os novos modelos aprovou catálogo/PIX e devolução; métrica de
  privacidade da injeção passou após repetição pontual de falha operacional. Rótulo real
  de desconto promocional corrigido com regressões; revisão confirmou 8/8 respostas capturadas.
- Langfuse com MiMo-V2.6-Pro: 70 observações recebidas, sete raízes, 15 gerações e 10 spans
  de ferramenta; todos os inputs/outputs vazios, com tokens presentes.
- Reteste da promoção aprovado: 1,0 comercial e 0,9 privacidade. Quatro casos validados
  em rodadas com retestes direcionados, sem apresentar o resultado como um único lote 4/4.
  Resumo com origem de cada métrica em var/deepeval-validation-summary.json; relatórios
  anteriores preservados. Servidor final pronto para teste manual em http://127.0.0.1:8000.
- Ambiente macOS: uv exigiu acesso à configuração de rede fora do sandbox; instalação autorizada.
  Um atributo UF_HIDDEN no .pth da instalação editável bloqueou imports e foi removido localmente.
