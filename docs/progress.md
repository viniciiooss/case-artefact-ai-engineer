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
- Dataset Yaitec analisado: golden de oito casos e banco de 60 perguntas em seis grupos.
  Criado golden Empório com 60 casos próprios, referências e checks exatos, filtros e
  identificação prévia pelo backend; quatro casos rápidos e 12 regressões preservados.
- Roteiro manual entregue em docs/teste-manual.md, incluindo o pedido fictício 8 e a
  verificação de isolamento. Comandos e formato do banco em evals/README.md.
- Validação desta atualização: 160 testes, Ruff e 12/12 regressões HTTP aprovados;
  60 casos validados offline, com referências/identificações conferidas e revisão independente.
  Wheel reinstalado e CLI de validação executada a partir do pacote instalado.
  Nenhum caso novo foi enviado a modelos pagos nesta atualização; o banco de 60 está pronto
  para execução explícita. Página e healthcheck locais continuam respondendo HTTP 200.
- Chat ajustado para exibir negrito/itálico com DOM seguro, mantendo o texto original para
  comparação do histórico e preservando fontes abertas entre turnos. Prompt, demo e mensagens
  comerciais agora respondem diretamente, com referências apenas na área de fontes.
- Golden e juiz comercial alinhados às fontes separadas; privacidade continua sem receber
  as referências comerciais. Validação: 165 testes, Ruff, 12/12 cenários e 60 casos válidos
  offline. Regressão Chrome exercitou formatação, HTML malicioso, fontes, histórico e mobile.
- Devolução em dois turnos repetida com MiMo real: negrito visível, nenhuma citação interna
  no texto, fontes preservadas e histórico/mobile aprovados. Sem chamada ao juiz; sessão
  temporária excluída. Wheel reinstalado e servidor atualizado em http://127.0.0.1:8000.
- Tempo de resposta adicionado sob o texto da Mel e persistido no histórico, com migração
  aditiva que preserva mensagens antigas sem estimar latência. Cabeçalho, mensagens e campo
  de envio alinhados na mesma coluna; parágrafos/listas com espaçamento e recuo consistentes.
- Validação: 167 testes, Ruff, 12/12 cenários HTTP e Chrome em seis larguras de 320 a 1440 px.
  API real em demo confirmou persistência após reload, sem chamadas a modelos pagos.
  Revisão independente sem falhas críticas/importantes; centralização vertical corrigida.
- Wheel reinstalado e servidor principal atualizado, com assets conferidos. A migração
  preservou as quatro sessões e 12 mensagens existentes. Servidor temporário encerrado.
- Novo pedido: remover a atribuição interna que reapareceu e reduzir os 12,7 s da resposta
  de contato. Traces mostraram duas gerações como principal custo. Criado nó conservador
  de FAQ para contatos/horários/endereço com busca real e zero chamadas ao modelo.
- Cinco consultas locais de canal: mediana 13,21 ms. Modelo MiMo e endpoint Xiaomi mantidos;
  raciocínio do atendimento em none, juiz separado em max. Metadados de fontes separados
  dos fatos enviados ao modelo e atribuições internas tratadas sem remover manuais do produto.
- Laya/Jev pesquisados nas fontes oficiais; não adicionados ao runtime para estas três
  intenções fixas. Escolha e medições documentadas em docs/latency.md, sem benchmark comparativo.
- Validação: 200 testes, Ruff, 12/12 cenários HTTP e regressão Chrome aprovados. Incompatibilidade
  do demo com o payload novo reproduzida e corrigida com testes de pagamento/garantia.
  Revisão final sem bloqueadores. Retestes MiMo preservaram preço/condições; consultas
  generativas ainda variaram entre 3,8 e 14,1 s. Nenhum novo juiz ou lote pago de 60 casos.
- Wheel atualizado e servidor principal reiniciado. A pergunta exata de contato no Chrome/API
  real retornou em 21,19 ms, com zero gerações, fonte na página 6 e sem atribuição interna.
  Reload/mobile aprovados; sessão de teste excluída e quatro conversas/14 mensagens preservadas.
- Ambiente macOS: uv exigiu acesso à configuração de rede fora do sandbox; instalação autorizada.
  Um atributo UF_HIDDEN no .pth da instalação editável bloqueou imports e foi removido localmente.
