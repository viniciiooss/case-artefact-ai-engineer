# OpenRouter, Langfuse e DeepEval

Objetivo: ativar o OpenRouter local e acrescentar observabilidade e avaliação ao fluxo existente.
Escopo autorizado: pedido do usuário para configurar e acrescentar os dois frameworks sem
complexidade desnecessária. O grafo, as ferramentas e a avaliação determinística continuam
como base; a avaliação com juiz roda em comando separado.

- [x] Configuração e observabilidade: testar configuração, exportação sanitizada de spans
  do grafo/ferramentas, isolamento por conversa e falha do coletor sem quebrar o atendimento.
  Implementar `observability.py`, integrar `service.py`/`agent.py` e liberar o buffer no
  encerramento HTTP/CLI. Instalar Langfuse via extra `observability`.
- [x] Avaliação: testar o adaptador de juiz OpenRouter com schemas reais do DeepEval,
  pontuações e falhas. Acrescentar quatro casos com respostas de referência revisadas,
  duas métricas G-Eval em português e `scripts/evaluate_llm.py` com limite de casos e
  relatório local. DeepEval permanece no extra `eval`, fora do atendimento.
- [ ] Ativação local: criar `.env` com permissão 0600 usando somente as credenciais
  necessárias do checkout Yaitec, sem imprimir valores nem alterar o projeto original.
  Verificar autenticação e executar uma amostra real pequena, com geração e juiz.
  Estado: `.env` criado e Langfuse autenticado; OpenRouter retornou 401. Execução real
  pendente de chave válida e autorização da execução externa.
- [x] Entrega: atualizar README, comandos, CI, Docker e evidências. Executar pytest,
  Ruff, 12 regressões determinísticas, validação dos SDKs, wheel e Docker; revisar o diff.

Critérios de conclusão: atendimento real via OpenRouter configurado; traces sem conteúdo
das conversas ou credenciais; falhas de telemetria independentes do atendimento; avaliação
reproduzível com notas, justificativas e erros explícitos; nenhuma credencial no Git.

Referências: documentação oficial de Langfuse v5 (callbacks/masking) e DeepEval 4 (G-Eval
e modelos customizados), confrontada com os SDKs instalados no lock.
