# SPRINT 6 — Relatório
## Backtest Engine — IQO Strategy Lab

**Data:** 2026-08-11
**Status:** Integração concluída. 356 testes passando contra PostgreSQL real (328 das Sprints 1-5 + 28 do Backtest Engine), zero regressão.

---

## 0. Nota sobre a natureza desta Sprint

Ao contrário das Sprints 1-5 (implementadas do zero nesta conversa), a Sprint 6 chegou como um **pacote pré-construído** (`sprint6_backtest/`, com `INTEGRACAO_CLAUDE_CODE.md` como instrução explícita de integração) — 13 módulos do engine + 21 testes, já escritos e descritos como "já implementado e testado". Minha tarefa aqui foi **integrar, ligar aos serviços reais, verificar e corrigir o que a integração revelasse** — não reescrever o engine. Este relatório documenta isso com precisão: o que veio pronto, o que eu liguei, e os bugs reais que só apareceram ao conectar o engine aos tipos concretos deste repositório (não bugs no design do engine em si, que se provou correto nos 21 testes originais).

Antes de começar, uma inconsistência real foi encontrada e resolvida com o usuário: a Sprint 7 (recebida antes desta) pressupunha que a Sprint 6 já existia — não existia. Confirmado com o usuário que a ordem correta era implementar/integrar a Sprint 6 primeiro.

---

## 1. Resumo

O Backtest Engine é determinístico, causal (`dados <= T`), auditável e independente de IQ Option/credenciais/conta real — verificado tanto pelos 21 testes originais quanto por 7 testes adicionais escritos durante a integração. Dois pontos de contato com o resto do sistema, ambos via `Protocol` (nunca import direto): `CandleRepository` (Data Engine, Sprint 2) e `StrategyService` (Strategy Engine, Sprint 5). O único tipo compartilhado entre os dois mundos é `SignalDirection`, agora religado ao enum real do Strategy Engine.

A integração revelou e corrigiu **dois bugs reais de incompatibilidade de forma** entre o `Signal` real (Sprint 5) e o que o engine esperava (detalhados na seção 10) — nenhum dos dois aparecia nos 21 testes originais porque eles usam sinais forjados (`FixedDirection`) que nunca exercitam `.conditions`/`.regime` do jeito que o Strategy Engine real produz.

---

## 2. Arquitetura

```text
backend/app/backtest/          # os 13 módulos entregues, sem alteração de lógica
├── __init__.py                # + exports dos 2 novos adapters
├── types.py                   # SignalDirection religado (única alteração nos 13 módulos)
├── config.py / engine.py / equity.py / metrics.py / outcome.py
├── portfolio.py / reports.py / repository.py / runner.py / simulator.py
├── validation.py
└── adapters.py                 # NOVO — os dois adapters da integração (seção 4)
```

Fluxo real, ponta a ponta:

```text
PostgreSQL → CandleRepositoryAdapter.get_candles(symbol, tf, start, end)
   → CandleRepository.get_domain(...)          [Sprint 2, já filtra por período no SQL]
   → BacktestRunner.run(config)
      → validate_candles(...)                   [seção 48-51 da spec original, falha explícita]
      → BacktestEngine.run(candles, strategy_adapter, gap_indices)
         para cada índice i (causal, candles[:i+1]):
            → StrategyEvaluatorAdapter.evaluate(candles[:i+1], parameters)
               → build_snapshot(candles[:i+1], ...)      [Market Engine, Sprint 4]
               → IndicatorRegistry.calculate(...)         [Indicators Engine, Sprint 3]
               → StrategyContext(...) → Strategy.evaluate(context)   [Strategy Engine, Sprint 5]
               → _SignalWithRegime(evaluation.signal, snapshot.regime)
            → TradeSimulator.resolve(...) na expiração (T+N, nunca o próprio candle)
   → compute_metrics + compute_drawdown → BacktestResult
```

---

## 3. Módulos entregues (não alterados em lógica)

`config.py`, `engine.py`, `equity.py`, `metrics.py`, `outcome.py`, `portfolio.py`, `reports.py`, `repository.py`, `runner.py`, `simulator.py`, `validation.py`, `__init__.py` (só exports adicionados) — copiados exatamente como recebidos. `types.py` teve uma única linha alterada (o import do `SignalDirection`, ver seção 5).

Pontos de design que os testes originais já garantem (não reimplementados, só verificados nesta integração contra dados reais):

- **P&L**: WIN = `+stake*payout` (nunca devolve o stake), LOSS = `-stake`, DRAW = `0`.
- **Entrada/saída**: `close(T)` → `close(T+N)`, nunca `open()`.
- **Modelo sequencial**: um trade por vez; um novo sinal só é avaliado quando não há posição aberta.
- **`win_rate = wins/(wins+losses)`**, DRAW fora do denominador.
- **`profit_factor` → `None`** quando não há perdas (nunca infinito).
- **Gaps**: marcados por `validate_candles`; uma operação cujo período de holding atravessa um gap é bloqueada (`SkipReason.DATA_GAP`).
- **Dados inválidos** (fora de ordem, duplicados, OHLC quebrado, timestamp naive) → `BacktestDataInvalid`, falha explícita, nunca conserto silencioso.

---

## 4. Adapters (novo — `app/backtest/adapters.py`)

### `CandleRepositoryAdapter`

Satisfaz o `Protocol CandleRepository` de `runner.py` usando `app.repositories.candle_repository.CandleRepository.get_domain()` (Sprint 2). Devolve os candles de domínio **sem** converter `Decimal` para `float` — decisão revertida durante a integração (ver seção 10, bug #1).

### `StrategyEvaluatorAdapter`

Satisfaz o `Protocol StrategyService` de `engine.py` (`evaluate(candles, parameters) -> Signal | None`). Uma instância fica ligada a UMA `Strategy` já configurada (via `StrategyRegistry.create`); o `parameters` recebido em `evaluate()` é ignorado (os parâmetros já foram aplicados na construção). A cada chamada, reconstrói do zero — só com os candles causais recebidos (`candles[:i+1]`, nunca mais):

1. `MarketSnapshot` via `build_snapshot` (Sprint 4);
2. os indicadores que a estratégia declarar via `required_indicators()` (Sprint 3);
3. um `StrategyContext` (Sprint 5) e chama `Strategy.evaluate(context)`.

Retorna `evaluation.signal`, envolto em `_SignalWithRegime` (ver seção 10, bug #2).

---

## 5. `SignalDirection` religado

`backend/app/backtest/types.py`, única alteração num dos 13 módulos entregues:

```python
from app.strategies.types import SignalDirection  # antes: app.strategy.types (não existe)
```

Confirmado que é o **mesmo objeto de enum** (`SignalDirection is app.strategies.types.SignalDirection` → `True`), não uma cópia. O enum real tem um terceiro valor (`NONE`) que o fallback do pacote não tinha — inofensivo, porque `normalize_direction()` só aceita `CALL`/`PUT` e um `Signal` com direção `NONE` nunca é construído pelo Strategy Engine real (`StrategyEvaluation.signal` é `None` nesse caso, então nunca chega ao backtest).

---

## 6. Testes

**28 testes no total, todos passando contra o PostgreSQL real**, zero alteração nos 21 originais:

```text
tests/backtest/test_backtest.py               21 testes  (entregues; rodados sem alteração após religar o import)
tests/backtest/test_adapters.py                 4 testes  (novos; adapters isolados, sem banco)
tests/backtest/integration/
  test_backtest_integration.py                  3 testes  (novos; Postgres real — pipeline completo,
                                                             regressão dos 2 bugs, performance)
```

Os 21 testes entregues continuam passando **exatamente como vieram** — nenhuma asserção foi alterada. Os 7 novos foram escritos durante esta integração porque os 21 originais usam sinais forjados (`FixedDirection`, um objeto com só `.direction`) que nunca exercitam o caminho `.conditions`/`.regime` do jeito que um `Signal` real do Strategy Engine produz — exatamente onde os dois bugs da seção 10 viviam. Sem esses 7 testes, a integração ficaria "verde" nos testes entregues e ainda assim quebraria em produção contra qualquer estratégia real.

---

## 7. Smoke run com dados reais

Executado manualmente (seção 5 de `INTEGRACAO_CLAUDE_CODE.md`) e depois formalizado como teste de integração: 71 candles reais (tendência de alta sintética, mesma usada nos testes do Strategy Engine), estratégia `trend_following`, contra o PostgreSQL real.

```text
Backtest 9f731f88-9325-43aa-9b00-3dd539b68a22
  estratégia   : trend_following
  símbolo/TF   : SMOKE_BT M1
  período      : 2026-01-01 00:00:00+00:00 → 2026-01-01 01:10:00+00:00
  payout/stake : 0.8 / 10.0  (expiry=1 candles)

  trades       : 21  (W 13 / L 8 / D 0)
  win_rate     : 61.90%  (draws fora do denominador)
  P&L          : 24.00   ROI: 2.40%
  profit_factor: 1.3
  expectancy   : 1.1429
  avg win/loss : 8.00 / -10.00
  streaks      : +10 / -4 (atual -4)
  max drawdown : 40.00 (3.91%)

  não executados: 1  {'UNRESOLVED': 1}
```

`regime` e `conditions` de cada trade vieram corretamente povoados (`TRENDING_BULLISH`, `{'regime_compatible': True, 'market_direction_bullish': True, ...}`), confirmando que os dois bugs da seção 10 estão mesmo resolvidos, não só "não quebram mais".

**Nenhum número acima é uma afirmação de que a estratégia é lucrativa** — é um dataset sintético de 71 candles, criado para os testes do Strategy Engine, não dados de mercado reais. Serve só para provar que o pipeline funciona.

---

## 8. Performance

Não havia meta de performance no pacote entregue nem em `INTEGRACAO_CLAUDE_CODE.md`. Medido mesmo assim, e o resultado é uma limitação real de escala que vale documentar:

```text
   500 candles →  2.27s  (220 candles/s)
 1.000 candles →  6.83s  (146 candles/s)
 2.000 candles → 27.10s  ( 74 candles/s)
```

O throughput **cai** com o tamanho do dataset — não é O(n) constante, é claramente superlinear (dobrar de 1.000 para 2.000 candles quase quadruplicou o tempo). Causa raiz: `StrategyEvaluatorAdapter.evaluate()` recalcula o `MarketSnapshot` **inteiro** (detecção de swings sobre TODO o histórico causal) a cada um dos `n` candles do backtest — ou seja, o adapter faz `O(n)` recomputações de algo que já é `O(k)` para um prefixo de tamanho `k`, resultando em `O(n²)` total. Extrapolando a partir do ponto de 2.000 candles, um backtest de 100.000 candles (a escala usada nos testes de performance das Sprints 2-5) levaria **horas**, não segundos — por isso o teste de performance desta Sprint usa 1.000 candles, não 100.000.

Isso **não é um bug** — o adapter está correto (o resultado do backtest é o mesmo, só lento) — é uma limitação de arquitetura da integração *tal como feita aqui* (recomputação completa em vez de incremental), documentada e deliberadamente não resolvida nesta Sprint (ver seção 13, pendências). Nenhum dos dois lados (engine entregue, Market Engine da Sprint 4) tem bug de performance isolado — o Market Engine sozinho processa 100.000 candles em 0,77s (Sprint 4); o problema é *chamá-lo `n` vezes sobre prefixos crescentes* em vez de manter um estado incremental.

---

## 9. Regras de integração respeitadas

Conferido explicitamente contra a lista de "Regras que não podem ser violadas" de `INTEGRACAO_CLAUDE_CODE.md`:

- **Causalidade**: `StrategyEvaluatorAdapter` só recebe e só usa `candles[:i+1]` que o engine já recortou — nunca busca candles adicionais (não tem acesso a `CandleRepository` nem a `timestamp` além do que está na lista recebida).
- **Período**: `CandleRepositoryAdapter.get_candles` delega inteiramente a `get_domain(symbol, tf, start, end)`, que já filtra `timestamp BETWEEN start AND end` no SQL (Sprint 2) — nada além de `end` chega ao engine.
- **Falha explícita em dados ruins**: nenhum adapter faz qualquer tipo de "conserto" de candles — `validate_candles` (dado como está) continua sendo a única porta de entrada de qualidade de dados, e continua falhando com `BacktestDataInvalid` exatamente como os 21 testes originais provam.
- **Sem execução real**: `grep -rn "iqoption\|broker\|execution\|credential"` em todo `backend/app/backtest/` não retorna nada.

---

## 10. Problemas encontrados

| # | Problema | Como foi resolvido |
|---|---|---|
| 1 | **Decimal vs. float**: minha primeira versão do `CandleRepositoryAdapter` convertia os preços `Decimal` do domínio (Sprint 2) para `float` na fronteira, por analogia com `SimpleCandle`. Isso quebrou o smoke run com `TypeError: unsupported operand type(s) for +: 'decimal.Decimal' and 'float'` dentro de `app.market.structure.support_resistance._build_zone`, que soma preços de swing começando de `Decimal(0)` — porque o `StrategyEvaluatorAdapter` alimenta os MESMOS candles no `build_snapshot`/`IndicatorRegistry` (Sprints 3-4), que assumem `Decimal`. | Removida a conversão: `CandleRepositoryAdapter` devolve os candles de domínio inalterados. Verificado que o próprio Backtest Engine nunca mistura Decimal com float (`outcome.py`/`simulator.py` só comparam `entry_price` com `exit_price`, ambos do mesmo tipo; `compute_pl` só usa `stake`/`payout`, que são float do `BacktestConfig` e nunca tocam o preço do candle) — então manter Decimal não quebra nada no engine, e mantém compatibilidade com o resto do sistema. |
| 2 | **`conditions`/`regime` como dict**: `engine.py._resolve()` faz `dict(getattr(sig, "conditions", {}) or {})` e `_extract_regime()` tenta `signal.conditions.get("regime")` — ambos assumem `conditions` como um dict. O `Signal` real (Sprint 5) usa `conditions: list[str]` (a lista de condições satisfeitas) e não tem atributo `.regime` nenhum. Isso quebrava com `ValueError: dictionary update sequence element #0 has length 17; 2 is required` e, antes disso, com `AttributeError: 'list' object has no attribute 'get'`. Nenhum dos 21 testes originais pegou isso porque usam um sinal forjado com só `.direction`. | Em vez de alterar `engine.py` (um dos 13 módulos entregues), criado `_SignalWithRegime` em `adapters.py`: um wrapper fino que expõe `.regime` (do `MarketSnapshot` já calculado pelo mesmo adapter) e reescreve `.conditions` como `{nome: True para cada condição satisfeita}` — uma tradução fiel da lista real, não um dado inventado — delegando todo o resto para o `Signal` original. A correção ficou inteiramente do lado da integração, como as instruções pediam. |
| 3 | Encoding: `summary_text()` usa o caractere `→`, que quebra ao imprimir num console Windows com codepage `cp1252` padrão (`UnicodeEncodeError`). | Não é um bug do projeto — é uma particularidade do console local. Resolvido definindo `PYTHONIOENCODING=utf-8` na sessão ao rodar smoke tests manuais. Não afeta a suíte automatizada (pytest captura stdout de outra forma) nem uma futura API (que serializaria a string, não a imprimiria num terminal). |

---

## 11. Decisões arquiteturais

- **Não alterar os 13 módulos entregues além da linha do import em `types.py`.** Os dois bugs de forma (seção 10, #2) foram corrigidos inteiramente em `adapters.py`, via um wrapper (`_SignalWithRegime`), em vez de tocar em `engine.py` — exatamente o que `INTEGRACAO_CLAUDE_CODE.md` pede ("o problema está no adapter/ligação, não na lógica do engine").
- **Manter `Decimal` nos candles que atravessam a fronteira do backtest**, em vez de converter para `float`. Decisão tomada depois de confirmar, lendo o próprio engine, que ele nunca mistura os dois tipos internamente — e que convertê-los quebraria a compatibilidade com o Market/Indicators Engine, que são consumidos pelo mesmo adapter.
- **`StrategyEvaluatorAdapter` liga a UMA estratégia por instância**, não escolhe por nome a cada chamada — reflete fielmente como `runner.py`/`engine.py` já foram desenhados (`cfg.strategy` é só um rótulo para o `TradeRecord`, nunca passado para `strategy_service.evaluate()`).
- **Testes novos ficam em arquivos próprios** (`test_adapters.py`, `integration/test_backtest_integration.py`), nunca misturados com `test_backtest.py` — preserva o pacote entregue como uma unidade auditável e reproduzível independentemente da integração.

---

## 12. Dependências

**Nenhuma nova.** O pacote entregue já não tinha dependências externas (só stdlib); os adapters reaproveitam `app.data`, `app.repositories`, `app.indicators`, `app.market` e `app.strategies`, todos já presentes. Nenhuma entrada nova em `pyproject.toml`.

---

## 13. Pendências

1. **Escala**: o adapter atual não é viável para backtests muito longos (ver seção 8) — `O(n²)` pela recomputação completa do `MarketSnapshot` a cada candle. Resolver isso exigiria um `MarketSnapshot` incremental (manter estado de swings/estrutura entre chamadas em vez de recalcular do zero) — mudança de arquitetura real, fora do escopo desta integração, e melhor endereçada quando houver necessidade concreta de backtests de dezenas de milhares de candles.
2. **Persistência**: o pacote entregue só tem `InMemoryBacktestResultRepository`. Não existe ainda uma tabela `backtest_runs`/`trade_records` no Postgres, nem endpoints de API, nem página de frontend para o Backtest Lab — ao contrário de todas as Sprints 1-5, que sempre incluíram esses três. `INTEGRACAO_CLAUDE_CODE.md` não pediu nenhum dos três (o Definition of Done lá é só integração + testes + smoke run), então não foram adicionados por conta própria. Ver próxima seção.

---

## 14. Próxima Sprint

A integração descrita em `INTEGRACAO_CLAUDE_CODE.md` está com todos os itens do Definition of Done atendidos:

- [x] 13 módulos em `backend/app/backtest/`
- [x] `SignalDirection` real religado em `types.py`
- [x] `CandleRepository` e `StrategyService` reais plugados (via adapters finos)
- [x] `pytest tests/backtest/` com 21 (originais) + 7 (novos) passando, todos contra Postgres real
- [x] smoke run com dados reais imprimindo `summary_text` sem erro
- [x] nenhuma dependência de IQ Option/credenciais introduzida

Diferente das Sprints 1-5, esta não teve uma especificação própria pedindo API + persistência Postgres + frontend — só a integração. Antes de seguir para a Sprint 7 (Live Execution, que já estava em andamento quando esta inconsistência foi descoberta), fica uma decisão explícita para o usuário: adicionar o tratamento completo (endpoint `POST /api/backtest/run`, tabela `backtest_runs`/`trade_records` no Postgres, página "Backtest Lab" no frontend) agora, seguindo o mesmo padrão das Sprints 1-5, ou seguir direto para a Sprint 7 com o Backtest Engine utilizável apenas via código/CLI por enquanto.
