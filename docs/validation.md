# Evidência de validação

Execução local em **4 de novembro de 2026**, com Python 3.12.6/macOS e contêiner
Python 3.12.16/Linux arm64. Dependências instaladas a partir de `uv.lock` com uv 0.9.3.
Os dados utilizados são o snapshot do ZIP fornecido, sem modificar o conteúdo original.

## Resultados

| Verificação | Resultado observado |
| --- | --- |
| Suíte pytest completa | **123 testes passaram**, incluindo OpenRouter, Langfuse e DeepEval |
| Ruff check | Sem erros |
| Ruff format --check | Nenhuma alteração de formatação necessária |
| Avaliação HTTP em processo | **12 de 12 cenários aprovados**, serviço e SQLite reais |
| Instalação não editável | Wheel reinstalado com extras `observability` e `eval` |
| CLI instalada | Consulta do GD20 no PIX retornou R$ 2.089,05, com fontes |
| Chrome + API real | Desktop 1440px e mobile 375px; sem overflow; zero erros JavaScript |
| Docker build | Imagem `emporio-artefact:local` construída com sucesso |
| Docker Compose | `docker compose config --quiet` sem erros |
| Contêiner em execução | UID 10001, healthcheck **healthy**, leitura/gravação e rotas verificadas |
| Revisão independente | Achados funcionais corrigidos; regressões finais aprovadas |
| Langfuse real | Autenticação confirmada, sem envio de conteúdo de conversas |
| OpenRouter real | Nova chave fornecida pelo usuário autenticada com **HTTP 200** em `GET /api/v1/key`; geração não executada |

## Reproduzir as verificações automatizadas

Na raiz do checkout:

```bash
uv sync --locked --no-editable --extra observability --extra eval
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pytest
uv run --no-sync python scripts/evaluate.py --report var/evaluation.json
EMPORIO_PROVIDER=demo EMPORIO_MODEL=deterministic-v1 EMPORIO_LANGFUSE_ENABLED=false uv run --no-sync emporio ask "Quanto custa o Takamine GD20 no PIX?"
docker build -t emporio-artefact:local .
docker compose config --quiet
docker compose up
```

O relatório JSON da avaliação é gravado em `var/evaluation.json`, fora do Git. As cinco
conversas versionadas em `examples/` foram geradas com `--write-examples`; incluem o modo
demo, o modelo e hashes dos dados. Não são transcrições de chamadas a uma LLM remota.

## Navegador e contêiner

O teste de navegador usou Playwright/Chrome contra o servidor HTTP real, sem interceptar
respostas: consulta de produto, continuação no PIX, fontes, e-mail incorreto com 403 sem
perder a conversa, identificação correta do pedido 8, rastreamento, reload do histórico,
layout mobile, exclusão e nova sessão sem autorização herdada. Os testes isolados de UI
também conferiram erro 503 sem perder rascunho, renderização de HTML como texto, Escape,
foco de modais e limites de entrada. Capturas da execução real:

- [Tela inicial](assets/welcome.png)
- [Conversa desktop](assets/chat-desktop.png)
- [Conversa mobile](assets/chat-mobile.png)

No Docker, o teste executou requisições HTTP a partir do próprio contêiner: health com
65 produtos/20 pedidos/28 trechos, criação e persistência de conversa, GD20 + PIX, arquivos
JS/PDF presentes no pacote, autorização do pedido 8, rastreamento e exclusão. O usuário
efetivo era 10001. O contêiner temporário foi encerrado e removido após o teste.

## O que os resultados comprovam

Os testes de regras usam os CSVs/PDF reais e bancos temporários. A avaliação usa FastAPI
TestClient para exercitar HTTP e o serviço completo, incluindo autorização. Testes de
protocolo substituem a rede/modelo por respostas controladas e mantêm schemas, grafo, SQL
e ferramentas reais. Um deles usa o próprio ChatOpenAI com `httpx.MockTransport` para
validar a serialização de function calling no SDK.

A revisão identificou e reproduziu respostas sem fundamentação, chamada malformada,
reutilização indevida de data de devolução e prioridade incorreta da memória sobre ID.
Cada correção ganhou regressão. A separação entre valor de política (por exemplo frete)
e preço de produto também tem teste, assim como sinônimos legítimos de status de pedido.

**Não foram executadas gerações com OpenAI, OpenRouter ou servidor Ollama reais.** Após
o pedido de ativação, as chaves necessárias foram copiadas para o `.env` local ignorado,
com permissão 0600. O Langfuse autenticou. A chave OpenRouter original retornou HTTP 401;
após a substituição pelo usuário, a nova chave autenticou com HTTP 200. Os testes usam
chaves fictícias e transporte controlado. Os resultados
não medem qualidade de linguagem livre,
resistência universal a prompt injection, adequação jurídica das políticas ou segurança de
produção. A defesa de resposta é conservadora e heurística; não substitui avaliação real.
O workflow GitHub Actions foi preparado, mas não executado em um repositório remoto.

## Atualização: reaproveitamento Yaitec/OpenRouter

A suíte passou novamente com 108 testes, incluindo os 12 testes do módulo de provedores.
O SDK OpenRouter real foi exercitado com respostas HTTP controladas: envio dos schemas,
consulta do produto #95, tool result, resposta fundamentada, chave independente e
atribuição da aplicação. Também foram verificados timeout de 45 segundos convertido para
45.000 milissegundos, teto de tokens e ausência de repetição automática diante de erro 503.
Erros 401/402/404/429 recebem códigos operacionais sanitizados, sem o texto bruto do provedor.
Seis regressões adicionais da CLI verificam mensagens seguras por código e resposta genérica
para códigos desconhecidos, mesmo quando o texto original da exceção contém um segredo.

O novo lock inclui `langchain-openrouter==0.2.9` e seu SDK; a resolução selecionou Pydantic
2.12.5, compatível com suas restrições. Todos os testes e os 12 cenários de avaliação
foram reexecutados nessa resolução. Os testes de SDK não comprovam a qualidade semântica
do modelo configurado. O [levantamento](reuse-yaitec.md) registra o que foi aproveitado.

O wheel foi reinstalado e a imagem Docker reconstruída após o ajuste final. A nova imagem
incluiu o SDK, executou uma consulta HTTP de GD20/PIX com fontes e histórico, e atingiu
healthcheck `healthy` como UID 10001. O contêiner temporário e seu volume foram removidos.

## Atualização: DeepEval e Langfuse

O lock inclui `langfuse==5.1.0` no extra `observability` e `deepeval==4.3.3` no extra
`eval`. O runtime Docker inclui somente Langfuse. Os plugins automáticos de pytest
instalados pelo DeepEval foram desativados: a suíte de regressão usa os SDKs diretamente,
sem abrir servidor de plugins ou acionar a avaliação paga.

Os 15 novos testes verificam o caminho real dos SDKs com transporte/exportação controlados:

- LangGraph e ferramentas geram spans com duração e sessão derivada por hash.
- Inputs, outputs, metadados livres e erros brutos não aparecem nos spans exportados,
  incluindo o status OpenTelemetry. A fila de mídia é desativada antes de criar o cliente:
  o SDK processa mídia antes do masking, e a regressão confirma ausência de uploads.
- Falha de inicialização do coletor não impede o atendimento.
- O juiz suporta schemas Pydantic em chamadas síncronas e assíncronas pelo OpenRouter.
- G-Eval real normaliza e reprova notas controladas; rejeita notas negativas, acima do
  limite, NaN ou infinito antes de registrar sucesso. Não há notas inventadas em falhas.
- Erro de créditos interrompe o lote sem repetir chamadas; sessões da avaliação são apagadas.

Os quatro casos revisados em `evals/llm_cases.json` têm referências próprias da Empório.
O comando `scripts/evaluate_llm.py` está pronto, mas não há relatório de notas reais nesta
entrega. A nova chave OpenRouter autenticou; a execução paga aguarda autorização explícita.
`var/deepeval-live.json` não foi gerado.
Não houve consumo de créditos nos testes descritos. A autenticação Langfuse foi conferida
separadamente; o recebimento de uma conversa real no serviço ainda depende da execução real.

A imagem reconstruída foi exercitada via HTTP em demo: Langfuse instalado, DeepEval
ausente, `.env` ausente no pacote, UID 10001, GD20/PIX com fontes e histórico, e healthcheck
`healthy`. O contêiner e seu volume temporário foram removidos após a verificação.

O servidor local foi recarregado com o wheel e `.env` atualizados; `/api/health` respondeu
`ok`, `provider=openrouter`, `model=xiaomi/mimo-v2.5`. Esse endpoint não testa conectividade
do modelo nem garante que a chave aceita gerações.

## Ambiente desta sessão

O sandbox do macOS bloqueou configuração de rede, Git, porta local e acesso ao Docker;
as operações necessárias foram autorizadas no ambiente de execução. A instalação editável
recebeu atributo macOS `UF_HIDDEN` no `.pth`, que fez o Python ignorá-lo. A instalação por
wheel (`--no-editable`), utilizada nos comandos de entrega e Docker, evitou essa dependência.
