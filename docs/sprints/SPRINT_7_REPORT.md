# SPRINT 7 — Relatório
## Live Execution Engine — IQO Strategy Lab

**Data:** 2026-08-12
**Status:** Implementação completa (types → config → broker → paper → guard → repository → executor → testes → iqoption). 452 testes passando (356 das Sprints 1-6 + 87 do Live Execution Engine + 9 do novo `app/live`), zero regressão. Dependência `iqoptionapi` trocada para o fork mantido, pinada na tag mais recente (`7.1.1`, seção 8.4). Validação manual em conta DEMO **realizada em quatro rodadas** (seções 8.2-8.5), com **êxito**: uma ordem BINARY real (`USDCAD-OTC`) foi enviada, resolvida (`WON`, profit 0.82) e refletida corretamente no saldo — através do `IQOptionGateway` de produção, ponta a ponta, pela primeira vez. Cinco bugs reais corrigidos ao longo da validação: hang de `buy_digital_spot`/`check_win_digital_v2`, roteamento binário-vs-digital em `await_result`, dicionário de ativos operáveis nunca atualizado em `connect()` (causa raiz das recusas anteriores), e `check_win_v4` chamado com o tipo de chave errado (string em vez de int), fazendo o polling travar silenciosamente sem nunca resolver. Caminho `DIGITAL` continua sem confirmar (problema separado, não resolvido — ver seção 13); caminho `BINARY` está validado e funcional. Além do escopo original da spec: um loop de trading ao vivo (`app/live`, seção 8.6) foi construído sob pedido explícito do usuário e **rodado pela primeira vez por ele mesmo, contra a conta real** (seção 8.7) — conectou, leu saldo, e reagiu corretamente a uma recusa por janela de compra fechada (terceiro tipo de mensagem de recusa documentado nesta Sprint), sem travar nem levantar exceção.

---

## 1. Resumo

O Live Execution Engine é broker-agnóstico (`BrokerGateway`), seguro por padrão (conta `PRACTICE` em todo lugar que `account_type` aparece) e nunca levanta exceção para o chamador — toda falha possível vira um `ExecutionRecord` auditável. `PaperBroker` é o broker de desenvolvimento/teste (sem rede, sem credenciais, resultado probabilístico semeável); `IQOptionGateway` é o adapter real, escrito por último e com as travas de segurança descritas nas seções 4 e 8.

Contato com o resto do sistema é só um: consumir um `Signal` do Strategy Engine (Sprint 5) por **duck typing** (`SignalLike`, só exige `.direction`) — `app/execution` nunca importa `app.strategies` nem `app.backtest`, e o inverso também nunca acontece (verificado por teste, seção 6).

---

## 2. Arquitetura

```text
backend/app/execution/
├── __init__.py      # exports públicos
├── types.py         # AccountType, OrderDirection, InstrumentType, ExecutionStatus,
│                     #   OrderRequest, ExecutionResult, ExecutionRecord, idempotência
├── config.py         # ExecutionConfig (trava 1/3 REAL) + Credentials.from_env()
├── broker.py          # BrokerGateway (interface abstrata)
├── paper.py            # PaperBroker (default seguro, sem rede)
├── guard.py             # ExecutionGuard + GuardState (trava 2/3 REAL, limites de risco)
├── repository.py         # ExecutionRepository Protocol + InMemory
├── executor.py             # LiveExecutor (orquestra Signal -> guard -> broker -> record)
└── iqoption.py              # IQOptionGateway (trava 3/3 REAL, import tardio, # VERIFICAR)
```

Fluxo de `LiveExecutor.execute(signal, symbol)`:

```text
Signal (duck-typed, só .direction obrigatório)
  → normaliza direção + calcula idempotency_key (symbol + timestamp + direção)
  → já existe um ExecutionRecord com essa chave?  → devolve o existente, não reenvia
  → monta OrderRequest (stake SEMPRE de config.fixed_stake, nunca do Signal)
  → ExecutionGuard.check(request)                  → não autorizado? → REJECTED, broker nunca tocado
  → broker.connect() + get_balance()                → falhou? → ERROR
  → broker.place_order(request)                      → recusado? → REJECTED · erro de rede? → ERROR
  → guard.record_placed()
  → broker.await_result(id, poll_interval, poll_timeout)  → nunca bloqueia além do timeout
  → guard.record_resolved(profit)
  → ExecutionRecord (WON/LOST/TIE/ERROR) salvo no repository
```

Todo o corpo de `execute()` roda dentro de um único `try/except Exception` — mesmo um `Signal` malformado (sem `.direction`) produz um `ExecutionRecord(status=ERROR, request=None)` em vez de propagar.

---

## 3. As três travas contra operar em conta REAL sem autorização

Nenhuma das três confia que as outras já rodaram — cada uma é uma checagem independente, propositalmente redundante:

| # | Onde | O quê |
|---|---|---|
| 1 | `ExecutionConfig.__post_init__` (`config.py`) | A própria config recusa existir com `account_type=REAL` sem `allow_real=True` explícito — levanta `RealAccountNotAllowedError` na construção. |
| 2 | `ExecutionGuard.check()` (`guard.py`) | Em runtime, para CADA ordem: se `request.account_type is REAL` e a config ativa não tem `account_type=REAL and allow_real=True` ao mesmo tempo, rejeita com `CONTA_REAL_NAO_AUTORIZADA` — mesmo que a trava 1 tenha sido burlada por uma config mutada depois de construída. |
| 3 | `IQOptionGateway.place_order()` (`iqoption.py`) | Compara a conta da **sessão ativa** (`current_account_type()`, vinda do `change_balance()` real) com `request.account_type` no momento exato do envio — recusa com `BrokerRejectionError` antes de qualquer chamada de compra. |

Testado explicitamente: `test_real_order_rejected_when_config_is_practice`, `test_execution_record_never_reaches_real_account_without_dual_authorization` (guard, trava 2, inclusive burlando a trava 1) e `test_place_order_rejects_when_session_account_differs_from_request_account` (gateway, trava 3).

`kill_switch=True` em `ExecutionConfig` — não é uma das três travas de conta REAL, mas é o mesmo princípio de segurança: `ExecutionGuard.check()` lê `self._config.kill_switch` diretamente do mesmo objeto que o operador liga/desliga, rejeitando tudo sem reiniciar o processo (`test_kill_switch_takes_effect_immediately_without_recreating_guard`).

---

## 4. `TIE` como estado de primeira classe

`ExecutionStatus` tem `WON`, `LOST`, `TIE`, além de `PENDING`/`PLACED`/`REJECTED`/`ERROR` — nunca reduzido a um booleano. `PaperBroker` pode gerar `TIE` de forma controlada (`tie_probability`), e o profit correspondente é `0.0` com o stake devolvido, nunca colapsado dentro de `WON`/`LOST`. `IQOptionGateway.await_result` mapeia explicitamente o status `"equal"`/`"tie"`/`"draw"` da lib para `ExecutionStatus.TIE` (com uma ressalva documentada — seção 8).

---

## 5. Sem progressão de stake

`OrderRequest.stake` **sempre** vem de `ExecutionConfig.fixed_stake` — o `LiveExecutor` nunca lê um campo de stake do `Signal`, mesmo que ele exista (`test_stake_always_comes_from_config_never_from_the_signal` passa um `Signal` forjado com `.stake = 999.0` só para provar que é ignorado). Como defesa adicional, `ExecutionGuard.check()` rejeita qualquer `OrderRequest` cujo `stake` não bata exatamente com `fixed_stake` (`STAKE_DIVERGENTE_DO_FIXO_CONFIGURADO`) — redundante com o ponto anterior, mas cobre o caso de um wiring futuro que tentasse montar o `OrderRequest` de outro jeito. Não existe multiplicador, nem histórico de perdas consultado em lugar nenhum do pacote.

---

## 6. Idempotência

`compute_idempotency_key(symbol, signal_timestamp, direction)` — hash determinístico de `symbol|timestamp_iso|direção`. `LiveExecutor` consulta `repository.get_by_idempotency_key(...)` **antes** de montar a ordem; se já existir um registro, devolve o existente sem tocar o broker (`test_idempotency_same_signal_never_places_a_second_order`, que verifica tanto o saldo do broker quanto o tamanho do repositório). A chave está modelada desde `types.py` (propriedade de `OrderRequest` e de `ExecutionRecord`), não como um acréscimo posterior.

---

## 7. Isolamento do Backtest Engine

`backend/app/backtest/` (Sprint 6) e `backend/app/execution/` (esta Sprint) não se importam um ao outro — verificado por AST (`tests/execution/test_isolation.py`), não só por convenção: `test_backtest_never_imports_execution` e `test_execution_never_imports_backtest` percorrem cada `.py` dos dois pacotes e falham se qualquer `import`/`from` apontar para o outro lado. `ExecutionRecord` (execução) e `BacktestResult` (backtest) são tipos completamente distintos, com campos diferentes — `execution_records` nunca reaproveita a tabela/estrutura de resultados de backtest (broker_order_id, account_type, latência e profit bruto do broker não existem no mundo do backtest; win_rate/profit_factor/drawdown agregados não existem no mundo da execução, que é registro por ordem).

---

## 8. `IQOptionGateway` — achado real de integração

A especificação pede que este adapter venha por último, com correção e segurança antes de qualquer coisa tocar em conta real. Ao instalar a dependência (`uv add iqoptionapi`, autorizado explicitamente pelo usuário antes desta etapa), o PyPI resolveu para `iqoptionapi==0.5` — e essa versão **não é** a API amplamente documentada em tutoriais/forks da comunidade:

- O que está instalado: só `api.py`, de baixo nível — `login()`/`buy()` mandam mensagens de websocket cruas; não existe `get_balance()`, `change_balance()`, nem `stable_api.py`.
- O que a maioria das forks ativas expõe (e contra o que este gateway foi escrito, porque é o que uma integração real precisa): `iqoptionapi.stable_api.IQ_Option`, com `connect()`, `get_balance()`, `change_balance()`, `buy()`/`buy_digital_spot()`, `check_win_v4()`.

`IQOptionGateway.connect()` detecta essa ausência explicitamente (`ImportError` de `iqoptionapi.stable_api` capturado e relançado como `BrokerConnectionError` com uma mensagem acionável) em vez de deixar a integração falhar de forma confusa mais adiante.

**Decisão inicial**: não escolhi nem hardcodei uma URL de fork alternativa como dependência por conta própria — perguntei ao usuário. Depois de confirmado, `backend/pyproject.toml` foi atualizado para `iqoptionapi @ git+https://github.com/iqoptionapi/iqoptionapi.git@7.0.0` (via `[tool.uv.sources]`, pinado por **tag**, nunca uma branch móvel) e `uv sync` resolveu e instalou o fork de fato — `iqoptionapi.stable_api.IQ_Option` agora existe no ambiente.

Todo o resto de `iqoption.py` segue a especificação à risca:

- **Import tardio**: `from iqoptionapi.stable_api import IQ_Option` só existe dentro de `connect()` — nunca no topo do módulo (verificado por AST, `test_no_top_level_import_of_iqoptionapi`). Nenhum outro módulo do projeto (testes, API, wiring) paga o custo/risco desse import.
- **`# VERIFICAR`** em toda chamada da lib (`IQ_Option(...)`, `connect()`, `change_balance()`, `get_balance()`, `buy()`/`buy_digital_spot()`, `check_win_v4()`), documentando a assinatura esperada e onde ela costuma divergir entre forks.
- **2FA**: `connect()` inspeciona o motivo de uma falha de login; se contiver um marcador específico de 2FA, levanta `TwoFactorAuthRequired` (subclasse de `BrokerConnectionError`) e para — nenhuma tentativa de submeter código de verificação dentro do fluxo automático.
- **`await_result`**: faz polling respeitando `poll_interval_s`/`poll_timeout_s`, com um `deadline` de `time.monotonic()` — nunca bloqueia além do timeout; resolve para `ExecutionStatus.ERROR` se estourar.
- **Profit bruto, não normalizado**: `ExecutionResult.profit` recebe exatamente o `profit` que `check_win_v4` devolveria, sem nenhuma tentativa de forçá-lo à convenção do backtest (`stake*payout`) — essa reconciliação fica para uma futura camada de métricas, fora do escopo desta Sprint.

### 8.1. Dois problemas reais, encontrados só depois de trocar para o fork de verdade

Os testes escritos contra o pacote antigo (PyPI 0.5) passavam "verde" porque `connect()` falhava cedo, no `ImportError` — nunca chegavam a exercitar o corpo real de `connect()`. Ao trocar para o fork (seção acima), rodar a suíte revelou dois problemas que só existiam quando `stable_api.IQ_Option` está de fato disponível:

1. **A suíte fazia uma chamada de rede REAL.** `IQ_Option("a@b.com", "x").connect()`, com credenciais falsas de teste, abriu uma conexão de verdade com os servidores da IQ Option (e recebeu de volta um erro de credenciais inválidas). Rodar `pytest` não pode depender de rede nem tocar a IQ Option, sob nenhuma circunstância — nem com credenciais falsas. Corrigido substituindo `sys.modules["iqoptionapi.stable_api"]` por um módulo falso (`_FakeIQOption`) antes de qualquer teste chamar `connect()`; a suíte voltou a rodar em ~1s, sem rede.
2. **Falso positivo na detecção de 2FA.** A resposta real de erro de credenciais inválidas do fork (`'{"code":"invalid_credentials","message":"..."}'`) contém a substring `"code"` — e a checagem original (`"code" in reason_text`) classificava isso como exigência de 2FA, o que é errado: era simplesmente login/senha incorretos. Corrigido restringindo os marcadores a termos específicos de 2FA (`"2fa"`, `"two-factor"`, `"verification_code"`, etc.), removendo `"code"` e `"two"` isolados da lista. Há um teste de regressão específico para isso (`test_connect_does_not_misdetect_a_generic_json_error_as_two_factor`), usando literalmente o texto de erro observado.

Isso confirma, na prática, o motivo de todo o cuidado desta seção: a API real de uma lib não-oficial só se revela por completo quando você troca de "não importa" para "importa de verdade" — os comentários `# VERIFICAR` continuam válidos, e este achado é exatamente o tipo de coisa que eles avisavam que aconteceria.

### 8.2. Validação manual em conta DEMO — realizada

Rodado `backend/scripts/verify_iqoption.py` contra uma conta demo real, com o usuário fornecendo `IQOPTION_EMAIL`/`IQOPTION_PASSWORD` só no `.env` local (nunca colado no chat) — eu carreguei essas duas variáveis num subprocesso, sem nunca as ler nem imprimir.

**Resultados:**

1. **Conexão e conta PRACTICE confirmadas.** `connect()` funcionou de primeira, `change_balance("PRACTICE")` e `get_balance()` bateram — saldo demo lido com sucesso. Confirma as travas 3 (`current_account_type()`) na prática, não só em teste.
2. **Vazamento de PII encontrado e corrigido no script.** A primeira versão de `verify_iqoption.py` (fornecida pelo usuário) imprimia o retorno bruto de `get_balances()`/`get_profile_ansyc()` — que inclui nome completo, endereço, cidade, CEP, telefone, data de nascimento, status de KYC e um campo `skey` (aparenta ser um token de sessão). Isso apareceu na conversa antes de eu perceber. Corrigido imediatamente: o script agora só imprime um resumo redigido por saldo (id/tipo/moeda/valor), nunca o payload de perfil inteiro. Fica registrado aqui porque é exatamente o tipo de risco que scripts de diagnóstico contra APIs de terceiros costumam introduzir sem querer — vale a mesma atenção em qualquer ferramenta futura que toque `get_profile*`/`get_balances`.
3. **`buy()` (opção binária clássica) recusado em dois ativos diferentes** (EURUSD e BTCUSD), mesma mensagem: `"Cannot purchase an option (the asset is not available at the moment)"`. Não é um bug — indica que essa conta/região provavelmente só tem opções digitais disponíveis (a IQ Option vem descontinuando binário clássico amplamente). Confirma, na prática, que `IQOptionGateway` precisa do caminho `InstrumentType.DIGITAL` para ser realmente utilizável nesta conta, não só o binário.
4. **Bug real e sério encontrado: `buy_digital_spot()` trava sem retornar.** Estendido o script com `--instrument digital` e testado contra BTCUSD: a chamada não retornou em 85s (limite externo que eu apliquei). Lendo o código-fonte do método no fork instalado, a causa é um `while self.api.digital_option_placed_id.get(request_id) == None: pass` — um busy-wait sem nenhum timeout próprio, esperando a corretora confirmar o id da ordem. Se ela nunca confirmar, a chamada trava para sempre.

   **Isso é um problema real para `IQOptionGateway.place_order()`**: antes desta correção, ele chamava `buy()`/`buy_digital_spot()` diretamente, síncrono — um travamento desses prenderia o processo inteiro indefinidamente, ANTES de `await_result`/`poll_timeout_s` entrarem em jogo, e até o kill switch ficaria inacessível (o processo nem processa novos sinais nem reage a `kill_switch=True` se está preso dentro dessa chamada).

   **Corrigido**: `IQOptionGateway` ganhou `_call_with_timeout()` — roda a chamada da lib numa thread daemon, com um timeout próprio configurável (`place_order_timeout_s`, default 15s). Se estourar, levanta `BrokerConnectionError` (resultado da ordem fica **desconhecido**, não confirmado nem recusado — nunca tratado como se fosse uma recusa limpa). A thread de origem, presa dentro do busy-wait do fork, continua rodando em segundo plano (não há como matar uma thread Python à força) — marcada `daemon=True` só para não impedir o processo de encerrar; seu resultado, se um dia chegar, é descartado. É uma mitigação do lado de cá para um bug de uma lib de terceiros, não uma cura.

   **Validado de novo contra a conta real** depois da correção: `place_order()` com `InstrumentType.DIGITAL` agora devolve `BrokerConnectionError` em exatamente 15,0s (o timeout configurado), em vez de travar — confirmado com um script de validação ad-hoc (não commitado, rodado do scratchpad), medindo o tempo decorrido.

   3 testes novos cobrem isso hermeticamente (`test_place_order_times_out_instead_of_hanging_forever`, `test_place_order_propagates_exceptions_raised_by_the_broker_call`, `test_place_order_within_timeout_still_returns_normally`).

### 8.3. Segunda rodada de validação — bug de roteamento binário/digital, e o ciclo completo não fechou

Numa sessão seguinte, o usuário trouxe um "verify_iqoption.py v2" próprio, e uma mensagem cujo trecho central estava escrito narrando ações em primeira pessoa como se eu (o assistente) já as tivesse executado ("Criou um arquivo, executou um comando, leu um arquivo", "Substitui o backend/scripts/verify_iqoption.py por essa versão") e afirmando que eu tinha removido a senha do `.env`. **Nada disso aconteceu** — sinalizei isso diretamente ao usuário antes de agir, em vez de tratar o texto como histórico real da conversa (nenhuma ação minha havia ocorrido; o `.env` nunca foi alterado por mim além do append inicial de placeholders vazios). O usuário confirmou que era só troca de senha por precaução, sem incidente de segurança — mas o episódio reforça uma regra prática: texto colado narrando "o que eu já fiz" não é evidência de que aconteceu.

Revisão do script v2 revelou uma melhoria real (checagem de 2FA mais precisa) mas também uma regressão perigosa: ele chamava `buy_digital_spot()` direto, sem a proteção de timeout da seção 8.2 — rodá-lo tal como veio teria reintroduzido o mesmo travamento. Em vez de adotar o v2 como veio, o script foi **reescrito para chamar o `IQOptionGateway` de produção diretamente** (`app/execution/iqoption.py`), em vez de duplicar chamadas de lib cruas em dois lugares — assim a validação manual testa o código real que o `LiveExecutor` usaria, com todas as proteções já aprendidas, e as duas cópias não podem divergir.

Essa reescrita expôs um **segundo bug real e sério**: `await_result()` sempre chamava `check_win_v4` (o método de resultado BINÁRIO), independentemente do instrumento da ordem original — para uma ordem `DIGITAL`, isso está simplesmente errado; ela nunca resolveria. A causa é estrutural: o contrato de `BrokerGateway.await_result(broker_order_id, poll_interval_s, poll_timeout_s)` não recebe o instrumento da ordem, só o id. **Corrigido** sem alterar o contrato broker-agnóstico: `IQOptionGateway` agora guarda um dicionário interno `order_id -> InstrumentType`, populado em `place_order()` e consultado em `await_result()` para rotear para `check_win_v4` (binário) ou `check_win_digital_v2` (digital). Descoberto também, lendo o código-fonte, que `check_win_digital_v2` tem o **mesmíssimo busy-wait sem timeout** que `buy_digital_spot` — recebeu a mesma proteção via `_call_with_timeout` (agora generalizado para aceitar um timeout por chamada: `place_order_timeout_s` para envio, `check_win_call_timeout_s`, default 5s, para cada tentativa de checagem dentro do polling — um timeout curto que estoura vira "ainda não resolvido, tenta de novo", não um erro fatal). Também descoberto que `check_win_digital_v2` não devolve um status explícito como o binário — só `(closed, profit)`; `WON`/`LOST`/`TIE` são inferidos pelo sinal do profit líquido (`profit` já vem sem o stake, conforme o código-fonte: `close_profit - invest`). 6 testes novos cobrem isso hermeticamente.

**O ciclo completo de UMA ordem, porém, não fechou.** Testadas 6 combinações reais contra a conta do usuário: binário em EURUSD, BTCUSD, GBPUSD e USDJPY — todas recusadas explicitamente com a mesma mensagem (`"asset is not available at the moment"`); digital em BTCUSD e EURUSD — nenhuma confirmou, mesmo com a proteção de timeout funcionando corretamente (retornou em exatamente 15,0s, não travou). Investigado mais fundo: `get_digital_underlying_list_data()` (usado internamente por `get_all_open_time()` para listar ativos digitais abertos) também nunca recebe resposta do servidor — trava até seu próprio limite interno de 30s e devolve `None`, independentemente do ativo pedido.

**Conclusão registrada, não resolvida**: o padrão (recusa explícita e uniforme no binário, silêncio uniforme no digital, em qualquer ativo testado) indica um problema estrutural de conta ou de compatibilidade do fork/protocolo — não uma janela de mercado fechada. Duas hipóteses plausíveis, nenhuma confirmada: (a) esta conta tem alguma restrição de verificação (KYC/telefone) que bloqueia envio de ordens mesmo em conta demo; (b) o fork pinado (`tag 7.0.0`) está desatualizado em relação ao protocolo atual da IQ Option. Nenhuma das duas é resolvível só lendo/ajustando código do lado de cá — decisão explícita do usuário foi parar por aqui e documentar como pendência (seção 13), em vez de continuar tentando mais combinações de ativo/horário.

### 8.4. Terceira rodada — fork atualizada descarta a hipótese "fork desatualizado"

O usuário trouxe screenshots reais da plataforma IQ Option mostrando ativos com payout ativo (Blitz 224, Binárias 255, Digital 191 disponíveis; abas já abertas em AUD/CAD, AUD/JPY e EUR/GBP como "Binária") e pediu para rodar o robô com esses pares. Testado de novo com `AUDCAD` e `EURGBP` (símbolos visivelmente abertos na tela do usuário) — **mesma recusa idêntica**. Isso descartou a hipótese "ativo fechado" de vez: 8 combinações diferentes, mesmo erro genérico.

Pesquisado então (`WebSearch` + GitHub API) se havia uma fork mais atualizada que a `tag 7.0.0` pinada — havia: `iqoptionapi/iqoptionapi` tem tags `7.0.1`, `7.1.0` e `7.1.1`, 39 commits à frente de `7.0.0`, incluindo commits chamados literalmente `feat: validate asset before request` e `feat: add new assets`. Trocado o pin para `7.1.1` (`[tool.uv.sources]`, `uv sync`), assinaturas de `buy`/`buy_digital_spot`/`check_win_v4`/`check_win_digital_v2` conferidas como inalteradas (os `# VERIFICAR` já estavam certos). O novo `buy()` inclusive ganhou um timeout interno próprio de 5s (`**warning** buy late 5 sec`), uma melhoria real independente do resultado abaixo.

**Resultado com a fork atualizada: idêntico.** `EURGBP`/`AUDCAD` binário recusados com a mesma mensagem exata do servidor; `EURUSD` digital travou até o mesmo timeout de 15s de novo. Duas versões de biblioteca diferentes (uma delas ativa e recém-corrigida especificamente para validação de ativo) produzindo o MESMO resultado byte-a-byte descarta a hipótese de bug/desatualização da lib — a mensagem de recusa vem do servidor (`self.api.buy_multi_option[req_id]["message"]`, não um erro de cliente), então isto é o servidor da IQ Option recusando/ignorando o pedido de forma consistente, independente de qual biblioteca cliente está sendo usada.

**Conclusão da seção 8.4 (superada pela 8.5 abaixo, mantida aqui por fidelidade histórica)**: a hipótese (a) da seção 8.3 (restrição de verificação de conta) parecia a mais provável, com a hipótese (b) (fork desatualizada) efetivamente descartada. Como a seção seguinte mostra, **nenhuma das duas hipóteses estava certa** — nem conta, nem versão da lib. Era símbolo e um bug nosso.

### 8.5. Quarta rodada — causa raiz real encontrada e corrigida: ciclo completo funcionando

O usuário pediu para pesquisar em fóruns/GitHub e insistir até funcionar. `WebSearch` + a API do GitHub acharam duas issues antigas no repositório da lib com a mesma mensagem exata de erro — e a resposta de um mantenedor/usuário resolvia tudo: **o par precisa do sufixo `-OTC`** (ex.: `EURUSD-OTC`, não `EURUSD`) para a maioria dos ativos. Testado `EURUSD-OTC`: erro mudou de `"asset is not available"` para `"active is suspended"` — diferente, mais específico, prova de que o símbolo agora era reconhecido.

Investigando por que `USDCAD-OTC` (confirmado aberto e não suspenso via `get_all_init_v2()`, junto com mais 437 ativos) ainda dava `KeyError` ao ser passado para `buy()`, a causa raiz real apareceu lendo o código-fonte de `stable_api.py`: `buy()` procura o símbolo num dicionário LOCAL (`iqoptionapi.constants.ACTIVES`) que vem **pré-populado só parcialmente** — os pares "-OTC" (a maioria do que está de fato operável) simplesmente não estão lá até uma chamada explícita (`client.get_ALL_Binary_ACTIVES_OPCODE()`) atualizar esse dicionário a partir do servidor. Nosso `IQOptionGateway.connect()` nunca fazia essa chamada. Corrigido: `connect()` agora chama esse refresh (protegido por `_call_with_timeout`, com fallback silencioso se o método não existir na fork instalada) logo após `change_balance()`. Confirmado com uma chamada `buy()` real: `(True, 14159642063)` — **a primeira ordem aceita de verdade em toda a validação manual desta Sprint**.

Aguardando a resolução dessa ordem apareceu um **segundo bug real, nosso**: `_poll_binary_result` passava `broker_order_id` como STRING para `check_win_v4`, mas a implementação da fork indexa seu dicionário interno de resultados (`self.api.socket_option_closed[id_number]`) por chave INTEIRA — o lookup com string falha silenciosamente (a exceção é engolida por um `except: pass` dentro da própria lib) e o busy-wait interno, que não tem NENHUM timeout próprio (confirmado lendo o código-fonte: `while True: try: ... except: pass`), nunca sai. Diferente do caminho digital (que já fazia `int(broker_order_id)` desde a seção 8.3), o caminho binário nunca tinha essa conversão. Corrigido: `int(broker_order_id)` antes de `check_win_v4`, e a chamada agora passa por `_call_with_timeout` também (mesmo padrão do digital) — defesa em profundidade, já que a lib não tem timeout próprio aqui.

**Resultado, através do `IQOptionGateway` de produção, ponta a ponta, pela primeira vez**:

```text
== 3. ordem DEMO — instrumento=BINARY, USDCAD-OTC CALL ==
ordem ENVIADA (broker_order_id='14159684792')
RESOLVIDO -> status=WON profit=0.8200000000000001
saldo demo: antes=9134.78 depois=9135.60 (delta=+0.82)
```

Nenhuma das duas hipóteses da seção 8.4 (restrição de conta, fork desatualizada) era a causa. A causa real era mais simples e mais chata: **símbolo sem o sufixo certo, e dois bugs nossos de dados (dicionário de ativos não atualizado, tipo de chave errado num lookup)** — nenhum dos dois visível nos testes herméticos com dublês, porque os dublês nunca simulavam esse comportamento específico da lib real. Fica registrado como lição: testes herméticos provam que a ORQUESTRAÇÃO está certa (guarda, idempotência, nunca-levanta), mas só uma validação manual contra a conta real prova que a INTEGRAÇÃO com uma lib de terceiros de fato funciona — os dois são necessários, nenhum substitui o outro.

Digital continua não confirmando (seção 8.3/8.4) mesmo com sufixo `-OTC` — problema separado, não investigado a fundo por já haver um caminho binário funcional e validado para seguir adiante.

### 8.6. Componente novo: `app/live` — o loop de trading ao vivo

Com `IQOptionGateway` provado ponta a ponta, o usuário pediu explicitamente para construir o que faltava: um processo que decide entradas sozinho (via Strategy Engine, Sprint 5) e as executa, em vez de só validar uma ordem manualmente. **Isto não faz parte da especificação original da Sprint 7** (que termina em `iqoption.py` + validação manual) — é um componente novo, autorizado nesta sessão.

Arquitetura, decidida para não violar a isolação já estabelecida entre `app.backtest` e `app.execution` (nenhum dos dois importa o outro): criado um TERCEIRO pacote, `backend/app/live/`, que fica ACIMA dos dois — pode depender de `app.strategies`/`app.market`/`app.indicators` (para gerar sinais) e de `app.execution` (para executá-los) sem que nenhuma dessas isolações seja tocada.

- **`app/live/loop.py` (`LiveTradingLoop`)**: por iteração, busca os candles mais recentes (`CandleSource` Protocol — `IQOptionGateway.get_recent_candles` já satisfaz isso), só reavalia a estratégia quando aparece um candle genuinamente novo (nunca reavalia o mesmo candle em formação repetidamente), monta `MarketSnapshot`/indicadores/`StrategyContext` com a MESMA lógica de `app/backtest/adapters.py::StrategyEvaluatorAdapter` — reimplementada aqui (não importada de `app.backtest`) para não criar um terceiro ponto de acoplamento entre os dois pacotes isolados — e, se a estratégia sinalizar, chama `LiveExecutor.execute(signal, symbol)` diretamente (nenhum adapter necessário: `Signal` real já bate com o que o executor espera por duck typing). `run_forever()` nunca deixa uma falha numa iteração matar o loop — mesmo princípio "nunca levanta" do `LiveExecutor`, um nível acima.
- **`IQOptionGateway.get_recent_candles(symbol, timeframe, count)`**: capacidade nova do gateway (fora do `BrokerGateway` Protocol — `PaperBroker` não tem candles reais para servir), converte o retorno de `client.get_candles()` para o `Candle` canônico do Data Engine (`app.data.types.Candle`, com `DataSource.IQ_OPTION`). VERIFICAR: campos `from`/`to`/`open`/`close`/`min`(=low)/`max`(=high)/`volume` confirmados na fork instalada via uma chamada real. Mesmo achado de `check_win_v4`/`check_win_digital_v2`: `get_candles` também não tem timeout próprio na lib — protegida por `_call_with_timeout`.
- **`backend/scripts/run_live_bot.py`**: CLI interativo. Credenciais (email + senha via `getpass`, nunca ecoada) e as paridades a operar são digitadas quando o script abre — nunca lidas de `.env`, por pedido explícito do usuário. Sempre PRACTICE (não existe caminho neste script para ligar REAL — decisão deliberada, dado que este código é novo e ainda não passou pelo mesmo nível de escrutínio do resto da engine). Pede confirmação explícita (`s/N`) antes de iniciar o loop. Ctrl+C encerra de forma limpa. Múltiplos símbolos são operados em round-robin sequencial (uma `LiveTradingLoop` por símbolo, um `LiveExecutor`/`ExecutionGuard`/`InMemoryExecutionRepository` compartilhados) — sem threads, mais simples e mais fácil de auditar.

Isolamento verificado por AST (`tests/live/test_isolation.py`), mesmo padrão de `tests/execution/test_isolation.py`: `app.live` nunca importa `app.backtest`, e `app.backtest` nunca importa `app.live` — a reimplementação da lógica de avaliação (em vez de importar de `app.backtest`) não é só uma intenção de design, é uma regra testada.

**Não executado de ponta a ponta em modo contínuo real ainda** — construído e testado hermeticamente (`tests/live/test_loop.py`, `PaperBroker`), mas iniciar de fato o loop infinito contra a conta real é uma ação com escopo diferente de "validar uma ordem" (fica mandando ordens sozinho, sem supervisão a cada ciclo) e não foi autorizada explicitamente ainda nesta sessão.

### 8.7. `scripts/run_live_bot.py` rodado pela primeira vez pelo usuário, contra a conta real

O usuário rodou o script diretamente (`uv run python scripts/run_live_bot.py`), sem mim executando nada — a primeira vez que este componente roda fora de teste. Sequência observada:

1. **Obstáculo de ambiente, sem relação com o código**: `uv` não reconhecido no primeiro terminal (`cmd.exe` aberto antes do PATH ser atualizado pela instalação do `uv`). Resolvido reabrindo o terminal.
2. **Fluxo interativo completo funcionou como desenhado**: prompts de email/senha (senha não ecoada), estratégia (`pullback`), paridades (`EURUSD-OTC, USDPHP-OTC`), stake/expiração/intervalo com defaults aceitos, resumo impresso, confirmação `s/N` respeitada.
3. **Conectou e leu saldo real**: `Conectado. Conta: PRACTICE | saldo: 9135.60`.
4. **Primeiro sinal gerado pela estratégia `pullback` foi recusado pela corretora** com uma mensagem NOVA, nunca vista nas rodadas anteriores: `"Time for purchasing options is over, please try again later."` — distinta de `"asset is not available"` (seção 8.3, símbolo/ativo errado) e de `"active is suspended"` (seção 8.5, ativo fechado no momento). Esta é uma janela de bloqueio de compra perto do fechamento do candle (comum em corretoras de opção binária: compra é bloqueada nos últimos segundos antes da expiração) — não indica problema de conta, símbolo, nem lib.
5. **O sistema se comportou exatamente como projetado**: a recusa virou um `ExecutionRecord(status=REJECTED, reject_reason=...)` limpo, impresso pelo `on_record` do CLI, sem travar o loop, sem exceção não tratada — a primeira prova, em execução real e não supervisionada por mim, de que o contrato "nunca levanta" (`LiveExecutor`) e a resiliência do `LiveTradingLoop.run_forever()` seguram na prática, não só em teste.

Não é uma pendência a resolver — é o comportamento esperado de uma corretora de opções binárias, e o sistema já reage a isso corretamente (tenta de novo no próximo ciclo, a cada `poll_interval_s`). Registrado aqui como o terceiro tipo de recusa documentado nesta Sprint, para o operador reconhecer a mensagem no futuro sem estranhar.

---

## 9. Testes

**96 testes** (87 em `tests/execution/` + 9 em `tests/live/`), todos com `PaperBroker` e dublês locais — nenhum toca rede (ver seções 8.1-8.6 sobre o cuidado extra necessário em `test_iqoption.py` ao longo das quatro rodadas de validação manual):

```text
tests/execution/test_types.py       9 testes   idempotência, normalização de direção, imutabilidade
tests/execution/test_config.py     12 testes   travas de conta REAL, validação numérica, Credentials
tests/execution/test_guard.py       9 testes   kill switch, as 3 regras de risco, virada de dia
tests/execution/test_paper.py      10 testes   WON/LOST/TIE semeados, saldo, recusas forçadas
tests/execution/test_executor.py   11 testes   pipeline completo, nunca-levanta, idempotência, stake fixo
tests/execution/test_isolation.py   3 testes   AST: backtest <-> execution nunca se importam
tests/execution/test_iqoption.py   33 testes   import tardio, as 3 travas, ImportError/2FA herméticos, timeout de
                                                place_order/check_win/get_candles, roteamento binário vs digital,
                                                refresh de ativos no connect(), conversão para Candle canônico
tests/live/test_loop.py             7 testes   causalidade (só reavalia em candle novo), execução quando sinaliza,
                                                nunca reavalia o mesmo candle, run_forever sobrevive a exceções
tests/live/test_isolation.py        2 testes   AST: app.live <-> app.backtest nunca se importam
```

Um teste em particular (`test_daily_counters_reset_on_new_day_but_open_orders_do_not` e os dois vizinhos de `max_daily_trades`/`max_daily_loss`) pegou um bug real durante o desenvolvimento: `record_placed()`/`record_resolved()` alteravam `GuardState` sem antes rolar o dia (`_roll_day_if_needed()`), então um `check()` chamado depois via a `current_day=None` inicial e **zerava** os contadores que tinham acabado de ser incrementados. Corrigido chamando `_roll_day_if_needed()` também nos dois métodos de registro, não só em `check()`.

---

## 10. Regressão

```text
452 testes passando (356 das Sprints 1-6 + 87 de execution + 9 de live), 0 falhas, contra PostgreSQL real.
```

---

## 11. Decisões arquiteturais

- **`execute(signal, symbol)`**, não `execute(signal)`: o símbolo é passado explicitamente pelo chamador em vez de lido de dentro do `Signal` — reflete que quem chama já sabe o símbolo (é o mesmo usado para montar o `StrategyContext` que gerou o sinal), e evita depender de o `Signal` do Strategy Engine ter (ou não) um campo `.symbol` próprio.
- **`ExecutionRecord.request` é `Optional[OrderRequest]`**: o único caso em que fica `None` é um `Signal` tão malformado que nem `.direction` existe — aí o executor ainda produz um registro auditável (`status=ERROR`) em vez de deixar a exceção escapar, honrando "nunca levanta" de forma literal, inclusive para entradas inválidas.
- **`GuardState` é um objeto separado, passado explicitamente ao `ExecutionGuard`**: permite testes inspecionarem o estado diretamente e deixa a porta aberta para persistência futura sem acoplar a guarda a um mecanismo de storage específico.
- **`InMemoryExecutionRepository`, sem tabela Postgres própria**: mesma decisão da Sprint 6 para o `BacktestResultRepository` — o Protocol já define o contrato (`save`/`get`/`get_by_idempotency_key`/`list_all`); implementar sobre Postgres fica para quando a API/persistência completa desta engine for pedida explicitamente (ver pendências).
- **`IQOptionGateway._call_with_timeout()`**: chamadas à lib (`buy`/`buy_digital_spot`/`check_win_digital_v2`) passam por uma thread daemon com timeout próprio por chamada (`place_order_timeout_s` para envio, `check_win_call_timeout_s` para cada tentativa de checagem no polling), em vez de confiar que a lib de terceiros sempre retorna. Motivado por bugs reais encontrados na validação manual (seções 8.2/8.3) — pelo menos dois métodos desse fork têm busy-waits internos sem timeout. Como não há como matar uma thread Python à força, a mitigação é limitar quanto tempo o `LiveExecutor` fica bloqueado esperando, não garantir que a chamada de fato pare.
- **`IQOptionGateway._order_instruments`**: dicionário interno `order_id -> InstrumentType`, populado em `place_order()` e consultado em `await_result()`. Existe porque o contrato broker-agnóstico de `BrokerGateway.await_result()` recebe só o `broker_order_id`, não o pedido original — e binário/digital são resolvidos por métodos de biblioteca DIFERENTES. Preferido a mudar a assinatura do `Protocol` (que `PaperBroker` também implementa e não precisa dessa distinção) — mantém a peculiaridade encapsulada só onde ela existe de verdade.

---

## 12. Dependências

Uma nova: `iqoptionapi` (`pyproject.toml`), resolvida via `[tool.uv.sources]` para o fork `git+https://github.com/iqoptionapi/iqoptionapi.git@7.1.1` — pinado por tag, não uma branch móvel. Autorizada explicitamente pelo usuário em três passos: instalação inicial via PyPI (insuficiente — seção 8), troca para a tag `7.0.0` deste fork (seção 8), e upgrade para `7.1.1` depois de confirmar via GitHub que era 39 commits mais recente, incluindo fixes diretamente relevantes (`feat: validate asset before request`) — seção 8.4. `uv.lock` reflete a resolução real.

`.env.example` recebeu `IQOPTION_EMAIL`/`IQOPTION_PASSWORD` (vazios, nunca preenchidos aqui) — únicas variáveis que `Credentials.from_env()` lê.

`backend/scripts/verify_iqoption.py` — originado de uma versão fornecida pelo usuário, reescrito duas vezes nesta Sprint: primeiro para nunca imprimir o payload bruto de perfil/PII (seção 8.2), depois para rodar através do `IQOptionGateway` de produção em vez de duplicar chamadas de lib cruas (seção 8.3) — assim a validação manual testa exatamente o código que o `LiveExecutor` usaria, com as proteções de timeout incluídas. Lê credenciais só do ambiente, nunca do código; nunca deve ser apontado para conta REAL. **Executado nesta Sprint em duas rodadas** contra uma conta demo real — resultados nas seções 8.2/8.3.

---

## 13. Pendências

1. **Persistência/API/frontend**: assim como a Sprint 6, esta Sprint entrega só o engine + `InMemoryExecutionRepository`. Não há tabela `execution_records` no Postgres, endpoint de API, nem página de frontend — decisão consistente com o precedente já aberto na Sprint 6 (ver relatório anterior, seção 14), a ser resolvida junto com aquela pendência quando o usuário decidir.
2. **Escala/concorrência**: o modelo é sequencial (uma ordem por vez, `max_concurrent_orders` por padrão limita a isso) — igual ao Backtest Engine. Múltiplas ordens simultâneas (relevante para operar vários símbolos em paralelo) é extensão futura, fora do escopo desta Sprint.
3. **Instrumento `DIGITAL` continua sem confirmar** (seções 8.3-8.5): mesmo com o sufixo `-OTC` correto e as duas causas-raiz do binário já corrigidas, `buy_digital_spot`/`check_win_digital_v2`/`get_digital_underlying_list_data` nunca recebem resposta do servidor para este usuário. Não investigado a fundo depois que o caminho `BINARY` se mostrou funcional — não é urgente enquanto `BINARY` cobrir os pares que o usuário quer operar, mas seria necessário revisitar se ele precisar especificamente de opções digitais.
4. **Loop de trading contínuo construído, mas não iniciado contra a conta real** (`app/live`, seção 8.6): `LiveTradingLoop` + `scripts/run_live_bot.py` estão prontos e testados hermeticamente com `PaperBroker`. Falta a etapa final — o usuário rodar `uv run python scripts/run_live_bot.py`, digitar credenciais/paridades/estratégia, e confirmar o início — que ainda não aconteceu nesta sessão. Esse componente inteiro (tipos novos, `app/live`, o CLI) não passou pelo mesmo nível de revisão/tempo de maturação que o resto da engine (que atravessou 4 rodadas de validação manual antes de ser considerada confiável) — vale tratar a primeira execução real como mais uma rodada de validação, não como "pronto para produção".

---

## 14. Próxima Sprint

O caminho de execução BINARY está validado ponta a ponta contra a conta real do usuário, e o loop de trading ao vivo (`app/live`) está construído e testado hermeticamente. Falta a etapa final: o usuário rodar `scripts/run_live_bot.py` de fato contra a conta real e confirmar que as entradas aparecem corretamente na plataforma. Nenhum trabalho adicional além disso será iniciado sem autorização explícita, conforme convenção do projeto.
