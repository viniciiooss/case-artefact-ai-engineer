# Latência e referências na resposta

As medições abaixo registram a configuração anterior, com MiMo-V2.6-Pro e juiz GLM-5.3.
A configuração atual usa Claude Haiku 5.5 no atendimento e GPT-6 Luna no juiz; veja
[README](../README.md). A troca de modelos não transforma esta amostra em um benchmark
do Haiku. A rota pública sem geração continua ativa.

O caso observado foi “qual o canal de atendimento”: **12.669 ms**, com duas gerações
de aproximadamente **7.030 ms** e **5.604 ms** nos metadados dos traces. O texto voltou
a citar o manual apesar da instrução no prompt. A busca local não era o principal custo;
os traces já mostravam leitura de cache de entrada do provedor.

## Mudança aplicada

O LangGraph agora tem um nó conservador para contato, horário e endereço. Ele usa a
mesma ferramenta `search_policies`, recupera os trechos do turno e formata os fatos
encontrados. Telefones, horários e endereço não são duplicados em constantes de resposta.
Se faltarem fatos, o fluxo continua para o modelo com um protocolo de ferramentas válido.
Pedidos, dados privados, ações, valores, e-mail ambíguo e perguntas mistas continuam no
agente habitual. Não foi adicionado cache de respostas que pudesse reutilizar preço,
estoque ou autorização de outro turno.

Nos turnos generativos, `model_payload` envia os trechos integrais como `policy_context`
e os demais dados comerciais, sem IDs, páginas e arquivos do envelope `sources`.
Os resultados originais permanecem disponíveis para grounding, avaliação e UI. Uma
função de apresentação remove atribuições internas reconhecíveis do texto final e do
histórico enviado ao modelo, preservando o histórico salvo e condições que exigem o
manual físico do produto. Essa função não é uma garantia semântica para qualquer redação.

O atendimento OpenRouter usa `EMPORIO_ATTENDANT_REASONING_EFFORT=none`; `default` omite
o parâmetro e restaura o padrão do provedor. O MiMo e o endpoint Xiaomi foram mantidos,
com teto de 1.600 tokens, sem fallback nem retries automáticos. O juiz GLM-5.3 continua
com esforço `max` e fora do atendimento. O parâmetro segue a
[documentação de raciocínio do OpenRouter](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

## Medições locais

Execução em 4 de novembro de 2026, com o mesmo modelo configurado, Langfuse ativo,
SQLite temporário e dados reais do snapshot. O baseline é a requisição observada do
usuário; não constitui um experimento controlado com o provedor.

| Consulta | Medida no serviço | Gerações |
| --- | --- | --- |
| Canal, antes da alteração | 12.669 ms, uma observação | 2 |
| Canal, após a rota direta | 12,71–17,99 ms; mediana **13,21 ms**, cinco consultas | **0** |
| Canal, horário e endereço | Mediana 13,21 ms, sete consultas no total | **0** |
| Promoção Kalani/PIX | 11.410 ms, uma consulta | 3 |
| Esclarecimento de devolução | 3.821 ms, uma consulta | 1 |
| Condições de devolução | 7.029 ms, uma consulta | 2 |
| Devolução após separar metadados | 14.064 ms, um reteste do segundo turno | 2 |

As gerações medidas reportaram zero tokens de raciocínio. No último reteste, o modelo
recebeu `policy_context` sem `sources` e preservou sete dias, embalagem, acessórios e
manuais; a fonte da página 4 permaneceu no backend. O primeiro turno desse reteste foi
semeado a partir da resposta real anterior para evitar repeti-lo no provedor.

Os resultados mostram ganho nas perguntas simples, sem afirmar que a latência de
respostas generativas foi resolvida. A duração do provedor varia e ainda domina esses
turnos. Não houve chamada ao juiz nem execução paga dos 60 casos do golden.
Relatórios locais: `var/latency-optimization.json` e `var/latency-projection-check.json`.

Após instalar o wheel e reiniciar a aplicação, o Chrome contra a API real repetiu a
pergunta de canal em **21,19 ms** no serviço, com zero gerações. O tempo exibido ficou
em **21 ms**, persistiu após reload e as fontes permaneceram disponíveis. Desktop e
mobile passaram sem erro JavaScript ou overflow; histórico anterior preservado.
Evidência: `var/chat-speed-live.json` e capturas `var/chat-speed-live-*.png`.

## Por que não adicionar Laya/Jev agora

[Jev](https://docs.typesafe.ai/introduction) produz decisões estruturadas, como escolha
e pontuação, sem geração de texto. [Laya](https://github.com/NandhaKishorM/laya) oferece
um modelo não autorregressivo para decisões estruturadas. Ambos podem servir a um
roteador; não substituem sozinhos a geração das respostas abertas deste agente.

Para estas três intenções públicas, o roteamento determinístico evita outra inferência,
SDK, pesos locais e calibração de confiança. É uma decisão de escopo, sem benchmark
comparativo de Laya/Jev. Com muitas intenções ou mais variação de linguagem, um roteador
aprendido pode ser avaliado contra o golden antes de entrar no fluxo.
