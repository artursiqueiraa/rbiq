# SPRINT 7 — Relatório
## Live Execution Engine — IQO Strategy Lab

**Data:** 2026-08-12
**Status:** Implementação completa (types → config → broker → paper → guard → repository → executor → testes → iqoption). 423 testes passando (356 das Sprints 1-6 + 67 do Live Execution Engine), zero regressão. Validação manual em conta DEMO **não realizada** — depende de credenciais do usuário e de uma dependência a trocar (seção 8).

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

`IQOptionGateway.connect()` detecta essa ausência explicitamente (`ImportError` de `iqoptionapi.stable_api` capturado e relançado como `BrokerConnectionError` com uma mensagem acionável) em vez de deixar a integração falhar de forma confusa mais adiante. Isso está coberto por teste rodando contra o pacote **de fato instalado** neste projeto (`test_connect_fails_clearly_against_the_currently_installed_iqoptionapi_package`) — não é uma simulação, é o comportamento real do ambiente hoje.

**Decisão deliberada**: não escolhi nem hardcodei uma URL de fork alternativa como dependência — trocar por uma fork mantida que exponha `stable_api.IQ_Option` é uma decisão do operador (qual fork confiar é uma escolha de segurança, não uma escolha técnica que este código deva tomar sozinho).

Todo o resto de `iqoption.py` segue a especificação à risca:

- **Import tardio**: `from iqoptionapi.stable_api import IQ_Option` só existe dentro de `connect()` — nunca no topo do módulo (verificado por AST, `test_no_top_level_import_of_iqoptionapi`). Nenhum outro módulo do projeto (testes, API, wiring) paga o custo/risco desse import.
- **`# VERIFICAR`** em toda chamada da lib (`IQ_Option(...)`, `connect()`, `change_balance()`, `get_balance()`, `buy()`/`buy_digital_spot()`, `check_win_v4()`), documentando a assinatura esperada e onde ela costuma divergir entre forks.
- **2FA**: `connect()` inspeciona o motivo de uma falha de login; se parecer 2FA (`"2fa"`/`"code"`/`"verification"` no texto), levanta `TwoFactorAuthRequired` (subclasse de `BrokerConnectionError`) e para — nenhuma tentativa de submeter código de verificação dentro do fluxo automático.
- **`await_result`**: faz polling respeitando `poll_interval_s`/`poll_timeout_s`, com um `deadline` de `time.monotonic()` — nunca bloqueia além do timeout; resolve para `ExecutionStatus.ERROR` se estourar.
- **Profit bruto, não normalizado**: `ExecutionResult.profit` recebe exatamente o `profit` que `check_win_v4` devolveria, sem nenhuma tentativa de forçá-lo à convenção do backtest (`stake*payout`) — essa reconciliação fica para uma futura camada de métricas, fora do escopo desta Sprint.

---

## 9. Testes

**67 testes**, todos com `PaperBroker` ou dublês locais — nenhum toca rede:

```text
tests/execution/test_types.py       9 testes   idempotência, normalização de direção, imutabilidade
tests/execution/test_config.py     12 testes   travas de conta REAL, validação numérica, Credentials
tests/execution/test_guard.py       9 testes   kill switch, as 3 regras de risco, virada de dia
tests/execution/test_paper.py      10 testes   WON/LOST/TIE semeados, saldo, recusas forçadas
tests/execution/test_executor.py   11 testes   pipeline completo, nunca-levanta, idempotência, stake fixo
tests/execution/test_isolation.py   3 testes   AST: backtest <-> execution nunca se importam
tests/execution/test_iqoption.py    9 testes   import tardio, as 3 travas (ponto 3), erro real de dependência
```

Um teste em particular (`test_daily_counters_reset_on_new_day_but_open_orders_do_not` e os dois vizinhos de `max_daily_trades`/`max_daily_loss`) pegou um bug real durante o desenvolvimento: `record_placed()`/`record_resolved()` alteravam `GuardState` sem antes rolar o dia (`_roll_day_if_needed()`), então um `check()` chamado depois via a `current_day=None` inicial e **zerava** os contadores que tinham acabado de ser incrementados. Corrigido chamando `_roll_day_if_needed()` também nos dois métodos de registro, não só em `check()`.

---

## 10. Regressão

```text
423 testes passando (356 das Sprints 1-6 + 67 novos), 0 falhas, contra PostgreSQL real.
```

---

## 11. Decisões arquiteturais

- **`execute(signal, symbol)`**, não `execute(signal)`: o símbolo é passado explicitamente pelo chamador em vez de lido de dentro do `Signal` — reflete que quem chama já sabe o símbolo (é o mesmo usado para montar o `StrategyContext` que gerou o sinal), e evita depender de o `Signal` do Strategy Engine ter (ou não) um campo `.symbol` próprio.
- **`ExecutionRecord.request` é `Optional[OrderRequest]`**: o único caso em que fica `None` é um `Signal` tão malformado que nem `.direction` existe — aí o executor ainda produz um registro auditável (`status=ERROR`) em vez de deixar a exceção escapar, honrando "nunca levanta" de forma literal, inclusive para entradas inválidas.
- **`GuardState` é um objeto separado, passado explicitamente ao `ExecutionGuard`**: permite testes inspecionarem o estado diretamente e deixa a porta aberta para persistência futura sem acoplar a guarda a um mecanismo de storage específico.
- **`InMemoryExecutionRepository`, sem tabela Postgres própria**: mesma decisão da Sprint 6 para o `BacktestResultRepository` — o Protocol já define o contrato (`save`/`get`/`get_by_idempotency_key`/`list_all`); implementar sobre Postgres fica para quando a API/persistência completa desta engine for pedida explicitamente (ver pendências).

---

## 12. Dependências

Uma nova: `iqoptionapi>=0.5` (`pyproject.toml`, autorizado explicitamente pelo usuário). Ver seção 8 para a ressalva sobre essa versão específica do pacote.

`.env.example` recebeu `IQOPTION_EMAIL`/`IQOPTION_PASSWORD` (vazios, nunca preenchidos aqui) — únicas variáveis que `Credentials.from_env()` lê.

---

## 13. Pendências

1. **Fork de `iqoptionapi`**: trocar a dependência instalada por uma fork mantida que exponha `stable_api.IQ_Option`, antes de qualquer tentativa de conexão real (seção 8). Decisão do operador — não tomada por conta própria.
2. **Validação manual em conta DEMO**: a Definition of Done da especificação pede "validação manual de UMA ordem em conta DEMO documentada" — não realizada nesta Sprint porque depende de (a) a pendência acima resolvida e (b) o usuário fornecer credenciais de uma conta demo real e consentir explicitamente com uma tentativa de conexão de rede. Nenhuma credencial foi solicitada ou usada até aqui.
3. **Persistência/API/frontend**: assim como a Sprint 6, esta Sprint entrega só o engine + `InMemoryExecutionRepository`. Não há tabela `execution_records` no Postgres, endpoint de API, nem página de frontend — decisão consistente com o precedente já aberto na Sprint 6 (ver relatório anterior, seção 14), a ser resolvida junto com aquela pendência quando o usuário decidir.
4. **Escala/concorrência**: o modelo é sequencial (uma ordem por vez, `max_concurrent_orders` por padrão limita a isso) — igual ao Backtest Engine. Múltiplas ordens simultâneas (relevante para operar vários símbolos em paralelo) é extensão futura, fora do escopo desta Sprint.

---

## 14. Próxima Sprint

Aguardando autorização explícita do usuário, conforme convenção do projeto. Nenhum trabalho adicional será iniciado até então.
