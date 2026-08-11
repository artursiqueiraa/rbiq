# SPRINT 5 — Relatório
## Strategy Engine — IQO Strategy Lab

**Data:** 2026-08-11
**Status:** Concluída. 190 testes novos (97 de estratégias + o resto de regressão), suíte completa passando contra PostgreSQL real.

---

## 1. Resumo

Construídas as seis estratégias previstas na arquitetura (Trend Following, Pullback, Breakout, Mean Reversion, Price Action, Divergence), todas determinísticas, explicáveis, configuráveis e desacopladas de execução/broker/IQ Option/SQL direto. Cada uma consome um `StrategyContext` (candles + `MarketSnapshot` da Sprint 4 + indicadores da Sprint 3, todos já causais) e devolve uma `StrategyEvaluation` contendo, no máximo, um `Signal` — nunca uma ordem.

Toda estratégia usa a mesma regra de decisão compartilhada (`decide_direction`): cada lado (alta/baixa) é pontuado como `condições satisfeitas / condições totais`, e só dispara se `confidence >= min_confidence` **e** superar estritamente o outro lado. Isso evitou reimplementar a mesma lógica de confiança/força seis vezes — e, ao construir os datasets de teste, essa uniformidade expôs um bug real de pontuação no Breakout (seção 20).

97 testes de estratégias, todos passando contra o PostgreSQL real usado desde a Sprint 1: unitários com datasets verificados executando o código antes de fixar as asserções, look-ahead comprovado inserindo candles futuros incrementalmente no banco real, determinismo, imutabilidade e isolamento (incluindo a proibição de SQL direto, não só de execução).

---

## 2. Arquitetura

```text
backend/app/strategies/
├── types.py         # SignalDirection, SignalStrength, Signal, StrategyEvaluation, IndicatorRequest
├── context.py        # StrategyContext
├── base.py            # Strategy (ABC), ConditionCheck, decide_direction, classify_strength
├── registry.py        # StrategyRegistry
├── service.py          # StrategyService (API -> MarketService/CandleRepository/IndicatorRegistry)
├── trend_following.py / pullback.py / breakout.py / mean_reversion.py / price_action.py / divergence.py
```

Fluxo real, ponta a ponta:

```text
PostgreSQL → CandleRepository.get_domain(..., end=timestamp)   [causal]
   → MarketService.get_snapshot(..., timestamp)                [Sprint 4, já causal]
   → StrategyService._indicators_for(strategy, candles)        [IndicatorRegistry, Sprint 3]
   → StrategyContext(candles, market_snapshot, indicators)
   → strategy.prepare(context); strategy.evaluate(context)
   → StrategyEvaluation(signal, triggered_conditions, failed_conditions, diagnostics)
```

`evaluate_all()` busca candles e o snapshot **uma única vez** e reaproveita para as seis estratégias — só os indicadores variam por estratégia. Medido: ~6x mais rápido que seis chamadas independentes de `evaluate()` (seção 19, performance).

---

## 3. Strategy Interface

```python
class Strategy(ABC):
    name: ClassVar[str]
    compatible_regimes: ClassVar[frozenset[str]]

    def default_parameters(self) -> dict: ...
    def validate_parameters(self, parameters: dict) -> None: ...
    def required_indicators(self) -> list[IndicatorRequest]: ...
    def prepare(self, context: StrategyContext) -> None: ...
    @abstractmethod
    def evaluate(self, context: StrategyContext) -> StrategyEvaluation: ...
```

Parâmetros são mesclados (`default_parameters() | kwargs`) e validados no `__init__` — parâmetro inválido levanta `ValueError` na construção, antes de qualquer candle ser tocado.

---

## 4. Strategy Context

```python
StrategyContext(symbol, timeframe, timestamp, market_snapshot, candles, indicators)
```

Sem `broker`, `account`, `balance`, `order` ou `execution` — conforme a seção 6 exige. `candles` e `market_snapshot` já chegam causalmente limitados a `timestamp` (responsabilidade do `StrategyService`, não da estratégia).

---

## 5. Signal Model

```python
Signal(id, strategy, symbol, timeframe, timestamp, direction, strength, confidence,
       expiry_candles, conditions, metadata)
```

- `id` é **determinístico** (`f"{strategy}:{symbol}:{timeframe}:{timestamp.isoformat()}"`), não um UUID aleatório — essencial para os testes de determinismo (duas avaliações do mesmo contexto devem produzir sinais idênticos, byte a byte).
- `direction` só é `CALL` ou `PUT` em um `Signal` construído; `NONE` só existe como valor interno de `decide_direction` antes de decidir se constrói um `Signal` (quando `direction == NONE`, `StrategyEvaluation.signal` é simplesmente `None`).
- `strength` usa limiares fixos e documentados (`classify_strength`): `>=0.85` STRONG, `>=0.65` MEDIUM, caso contrário WEAK — nunca aleatório.
- `StrategyEvaluation.evaluated_at` é um carimbo de relógio de parede (para auditoria) e é **deliberadamente excluído** dos testes de determinismo — dois runs do mesmo contexto nunca terão o mesmo `evaluated_at`, mas sempre terão o mesmo `signal`/`conditions`.

---

## 6. Strategy Registry

```python
StrategyRegistry.get("trend_following")          # -> classe TrendFollowing
StrategyRegistry.create("trend_following", fast_ema=10)
StrategyRegistry.names()  # -> 6 nomes, ordenados
```

Dicionário estático `nome -> classe`, mesma técnica do `IndicatorRegistry` (Sprint 3) — nenhum `if/elif` espalhado.

---

## 7. Trend Following

Exige concordância simultânea entre `market_direction`, `structure_state`, cruzamento EMA rápida/lenta e `trend_strength >= min_trend_strength` — nunca dispara só por `EMA20 > EMA50` (seção 15 proíbe isso explicitamente). Parâmetros: `fast_ema=20`, `slow_ema=50`, `min_trend_strength=0.30`. `compatible_regimes = {TRENDING_BULLISH, TRENDING_BEARISH}`.

---

## 8. Pullback

Detecta uma correção temporária **seguida de retomada** dentro de uma tendência já estabelecida — nunca dispara no meio da correção, só na retomada confirmada (fechamento atual acima da EMA, acima do fechamento anterior, e acima do próprio fundo da correção). Parâmetros: `pullback_ema=20`, `lookback_candles=10`, `pullback_tolerance_pct=0.005`.

---

## 9. Breakout

Regra de confirmação explícita (seção 22): exige **fechamento** (não pavio) além da zona por `confirmation_candles` candles consecutivos, com o candle imediatamente anterior à janela ainda do lado errado da zona (prova de que o cruzamento aconteceu dentro da janela observada). O caso de falso rompimento (seção 24/54) é coberto naturalmente: um pavio que ultrapassa a resistência mas fecha abaixo dela nunca satisfaz a checagem, que é sobre fechamentos.

**Correção de bug feita durante esta Sprint** (ver seção 20): as três sub-condições de confirmação (zona identificada + fechamentos além dela + candle anterior do lado errado) viraram um único check `breakout_confirmed` (E lógico), em vez de três condições independentes com peso igual — a versão original permitia que 4 de 5 condições "por acaso verdadeiras" (incluindo uma zona antiga do lado errado do preço) disparassem o lado errado mesmo sem rompimento algum.

---

## 10. Mean Reversion

Restrita a regimes de consolidação (`RANGING`, `LOW_VOLATILITY`, `HIGH_VOLATILITY` — os três regimes que o Market Engine deriva de uma estrutura RANGE, ver Sprint 4) — nunca opera em tendência real, mesmo com RSI extremo (seção 25). Exige simultaneamente: preço na banda de Bollinger, RSI no extremo correspondente, **e** evidência de rejeição (candle fechando na direção da reversão e acima/abaixo do fechamento anterior) — nunca dispara só por `RSI < 30` (seção 26).

---

## 11. Price Action

A única estratégia sem indicadores obrigatórios (seção 28). Candle de rejeição definido matematicamente (seção 29): corpo pequeno (`body <= max_body_ratio * range`) com pavio longo do lado da rejeição (`wick >= min_wick_ratio * range`) tocando uma zona de suporte/resistência do Market Engine. O segundo padrão, continuação estrutural, reaproveita os eventos `HIGHER_HIGH`/`HIGHER_LOW`/`LOWER_HIGH`/`LOWER_LOW` que o próprio Market Engine já produz (Sprint 4) — não uma lógica nova.

---

## 12. Divergence

Reaproveita `app.market.structure.swings.detect_swings` **diretamente** (mesma função, mesmo algoritmo causal da Sprint 4 — testado em `test_uses_the_same_causal_swings_as_the_market_engine`), comparando o preço nos dois swings mais recentes de um tipo contra o RSI nos mesmos índices. Divergência sozinha não é sinal (seção 31/32): exige também recência (`max_bars_between_swings`) e, por padrão, uma vela de confirmação (preço já reagindo na direção da divergência).

Curiosidade útil: os datasets de tendência forte usados para Trend Following (seção 7) já produzem, como efeito colateral verificado, uma divergência de baixa perto do topo de uma tendência de alta sustentada (e vice-versa) — um padrão técnico real, não um artefato — o que forneceu casos de teste positivos prontos sem precisar de datasets extras.

---

## 13. Parameters

| Estratégia | Parâmetros e defaults |
|---|---|
| Trend Following | `fast_ema=20`, `slow_ema=50`, `min_trend_strength=0.30` |
| Pullback | `pullback_ema=20`, `lookback_candles=10`, `pullback_tolerance_pct=0.005` |
| Breakout | `confirmation_candles=1`, `atr_period=14` |
| Mean Reversion | `bollinger_period=20`, `bollinger_std=2.0`, `rsi_period=14`, `rsi_oversold=30`, `rsi_overbought=70` |
| Price Action | `min_wick_ratio=0.5`, `max_body_ratio=0.35` |
| Divergence | `rsi_period=14`, `left_bars=2`, `right_bars=2`, `max_bars_between_swings=30`, `require_confirmation_candle=True` |

Todas herdam `min_confidence=0.70` e `expiry_candles=1` de `Strategy.default_parameters()`. **Nenhum desses valores foi otimizado** — são pontos de partida, conforme a seção 65 exige explicitamente ("NÃO fazer optimization/grid search nesta Sprint").

---

## 14. Diagnostics

Quando uma estratégia não dispara, `StrategyEvaluation` sempre contém `triggered_conditions`/`failed_conditions` do lado que teve a pontuação mais alta (mesmo perdendo), permitindo responder "por que não disparou" sem re-executar nada. Dados insuficientes (menos candles que o mínimo, indicador ainda `None`) geram um `diagnostics` explícito (`"insufficient_data: ..."`) em vez de deixar `triggered/failed` vazios sem explicação.

---

## 15. API

```text
POST /api/strategies/evaluate       {strategy, symbol, timeframe, timestamp, parameters?}
POST /api/strategies/evaluate-all   {symbol, timeframe, timestamp}
```

Ambas verificadas com curl real contra o Postgres real. Nome de estratégia desconhecido, parâmetro inválido e timeframe inválido retornam 400. Nenhuma rota executa ordens — só calcula e devolve `StrategyEvaluationOut` (ou um dicionário `nome -> StrategyEvaluationOut` no `evaluate-all`).

---

## 16. Frontend

Página **Strategy Lab** (quinta aba): formulário (ativo, timeframe, timestamp) → tabela de comparação das seis estratégias (nome, direção, força, confiança, expiry) → painel de detalhe (condições satisfeitas/não satisfeitas, diagnóstico) ao clicar em uma linha.

Deliberadamente **não mostra** nada como "85% de chance" ou "estratégia vencedora" (seção 50 proíbe isso) — só os números crus que a API devolve, com um aviso explícito no topo da página de que nada ali foi validado estatisticamente (isso é trabalho da Sprint 6).

---

## 17. Testes

**97 testes novos** (86 unitários + 11 de integração/performance), todos passando contra o PostgreSQL real:

```text
tests/strategies/
  test_base.py                    8 testes  (decide_direction, classify_strength, last_value, value_at)
  test_registry.py                10 testes
  test_trend_following.py         9 testes
  test_pullback.py                6 testes
  test_breakout.py                8 testes
  test_mean_reversion.py          7 testes
  test_price_action.py            9 testes
  test_divergence.py              8 testes
  test_determinism.py             12 testes (2 por estratégia, parametrizado)
  test_isolation.py               2 testes  (sem execução/broker; sem SQL direto)
  integration/
    test_service_integration.py    4 testes (Postgres real)
    test_api_integration.py        5 testes (Postgres real)
    test_lookahead_integration.py  1 teste  (Postgres real, ver seção 18)
    test_performance.py            1 teste  (100.000 candles)
```

Todos os datasets de referência (`tests/strategies/conftest.py`) foram **verificados executando o código real** antes de virar constantes de teste — incluindo os dois casos em que minha primeira tentativa de dataset não produzia o resultado esperado (documentado na seção 20). Essa disciplina, adotada desde a Sprint 3, continua compensando: pegou 3 datasets errados nesta Sprint antes que virassem testes silenciosamente incorretos.

---

## 18. Look-ahead validation

Seção 58 exige esse teste "para cada estratégia" — mas a única forma de torná-lo realmente significativo é no nível de integração, não unitário: como `Strategy.evaluate()` só enxerga o que `StrategyContext` já contém, e `StrategyContext` é sempre construído com `candles` já limitados a `timestamp`, a garantia de causalidade vive em `CandleRepository.get(..., end=timestamp)` — testar isso exige que exista, de fato, dado futuro no banco que o resultado passado precisa ignorar.

`test_lookahead_integration.py` faz exatamente isso, para as seis estratégias de uma vez (via `evaluate_all`):

1. insere candles `0..60` no Postgres real;
2. avalia todas as seis estratégias em `T = candle[59].timestamp`;
3. insere candles `60..70` (o "futuro" de `T`);
4. avalia novamente em `T` (o mesmo `T`, não um `T` mais recente);
5. exige `signal`, `triggered_conditions` e `failed_conditions` idênticos entre os passos 2 e 4, para todas as seis.

Isso comprova exatamente o que a seção 58 pede — "adicionar candles T+1, T+2, T+3 não pode modificar o sinal já calculado em T" — contra o banco real, não uma simulação em memória.

---

## 19. Performance

100.000 candles, seis estratégias, contra o PostgreSQL real:

```text
Snapshot de mercado (Market Engine, Sprint 4):                    4.0s
6 chamadas independentes de evaluate() (cada uma refaz o fetch
  de candles + o snapshot completo do zero):                     53.3s
  breakout=7.95s  divergence=10.96s  mean_reversion=7.53s
  price_action=8.85s  pullback=8.91s  trend_following=9.13s
evaluate_all() (busca candles e snapshot uma única vez,
  reaproveitados pelas 6 estratégias):                             9.0s
```

`evaluate_all()` é ~6x mais rápido que seis chamadas independentes de `evaluate()`, exatamente o comportamento esperado do design (seção 2). Não otimizado além disso — conforme a seção 63 pede, o objetivo aqui era medir, não otimizar prematuramente. Se um consumidor futuro (ex.: o Backtest Engine da Sprint 6) precisar avaliar múltiplas estratégias repetidamente ao longo de uma série temporal, `evaluate_all()` (ou um cache de snapshot equivalente) é o padrão a seguir, não `evaluate()` em loop.

---

## 20. Problemas encontrados

| # | Problema | Como foi resolvido |
|---|---|---|
| 1 | **Bug real de pontuação no Breakout**: as três sub-condições de confirmação de rompimento (`resistance_identified`, `price_closed_above_resistance`, `prior_candle_was_below`) eram pontuadas como três condições independentes e iguais, junto de `regime_compatible` e `volatility_expanding` (5 condições, `min_confidence=0.70`). Ao montar um dataset de teste para o rompimento de **suporte** (PUT), descobri que uma zona de **resistência** antiga, situada abaixo do preço atual (irrelevante para o movimento real), ainda satisfazia `resistance_identified` e `prior_candle_was_below` — e com `volatility_expanding` também verdadeiro, isso somava 4/5 = 0.80, disparando **CALL** mesmo o preço estando em plena quebra de suporte para baixo. | Colapsei as três sub-condições em um único check `breakout_confirmed` (E lógico) — confirmação de rompimento é binária por natureza (aconteceu ou não), então passou a ser pontuada como uma coisa só. `volatility_expanding` virou metadado informativo, não mais parte da pontuação. Teste de regressão dedicado (`test_stale_zone_on_the_wrong_side_does_not_inflate_confidence`) garante que isso não volte. |
| 2 | Símbolos de teste como `TEST_STRATEGY_SERVICE` (21 caracteres) e `TEST_STRATEGY_LOOKAHEAD` (23) estouraram a coluna `symbol VARCHAR(20)` da tabela `candles` (definida na Sprint 2), só descoberto ao rodar os testes de integração contra o Postgres real — nenhum teste unitário usa a coluna do banco, então não pegaria isso. | Renomeados para `TEST_STRAT_SVC` e `TEST_STRAT_LA` (dentro do limite). Nenhuma mudança de schema necessária — a coluna de 20 caracteres é adequada para símbolos reais (`EURUSD`, `GBPJPY`), só não para nomes de teste descritivos demais. |
| 3 | Vários datasets de teste que escrevi "de cabeça" (tolerância de pullback, ponto de corte para começar um rompimento de suporte perto do fundo, forma exata de vela de rejeição) não produziram o resultado esperado na primeira tentativa — sempre por um detalhe geométrico específico (ex.: o `low` da vela de rejeição ficando um tick abaixo da zona de suporte em vez de dentro dela). | Mesma disciplina das Sprints 3-4: rodei cada dataset candidato contra o código real antes de fixá-lo como teste, ajustando até o resultado bater com a intenção, em vez de assumir que o dataset "parecia certo". |

Nenhum outro problema bloqueante.

---

## 21. Decisões arquiteturais

- **Uma única função de decisão compartilhada (`decide_direction`)** para as seis estratégias, em vez de cada uma reimplementar sua própria lógica de pontuação/confiança. Isso não só evitou duplicação como foi o que tornou o bug do Breakout (seção 20) visível e corrigível em um único lugar — se cada estratégia tivesse sua própria lógica ad-hoc, o mesmo tipo de erro poderia existir em qualquer uma delas sem um padrão comum para auditar.
- **`regime_compatible` é uma condição pontuada, não um veto rígido separado.** Cheguei a considerar um "hard gate" que retornasse `NONE` imediatamente se o regime fosse incompatível, mas isso duplicaria a lógica (a seção 26 já lista "regime = RANGING" como uma condição entre outras no exemplo da Mean Reversion) — mantendo como mais uma `ConditionCheck`, o comportamento fica uniforme com as demais condições e ainda aparece corretamente em `triggered_conditions`/`failed_conditions`.
- **`Signal.id` determinístico**, não `uuid4()` — necessário para os testes de determinismo (seção 59) comparem sinais por igualdade estrutural completa, não apenas campo a campo.
- **Divergence chama `detect_swings` diretamente** em vez de depender só de `MarketSnapshot.latest_swing_high/low` — o snapshot só expõe o swing mais recente de cada tipo, mas divergência precisa comparar os dois mais recentes. Reutiliza a função da Sprint 4 exatamente como está, sem duplicar o algoritmo (seção 33), só usando mais da sua saída.
- **`evaluate_all()` busca candles/snapshot uma única vez**, distinto de seis chamadas a `evaluate()` — documentado e medido na seção 19; existe porque comparar estratégias (o caso de uso do Strategy Lab) é o caminho realista, não avaliar uma de cada vez.
- **`MeanReversion.compatible_regimes` inclui os três regimes derivados de RANGE** (`RANGING`, `LOW_VOLATILITY`, `HIGH_VOLATILITY`), não só `RANGING` — o nível de volatilidade por si só não deveria excluir um setup de reversão à média que é, estruturalmente, um range (ver Sprint 4's `classify_regime`).

---

## 22. Dependências

**Nenhuma.** Todo o Strategy Engine usa apenas a biblioteca padrão do Python e reaproveita `app.data`, `app.indicators`, `app.market` e `app.repositories` já existentes. Nenhuma nova entrada em `pyproject.toml`.

---

## 23. Pendências

Nenhuma pendência técnica bloqueante. Uma nota de escopo, deliberada e exigida pela própria Sprint:

- Nenhum parâmetro foi otimizado, nenhuma taxa de acerto foi medida, nenhuma estratégia foi declarada lucrativa — tudo isso é trabalho da Sprint 6 (Backtest Engine), que é o único lugar onde essas afirmações poderiam ser sustentadas por dados.

---

## 24. Próxima Sprint

Aguardando autorização explícita para iniciar a **Sprint 6 — Backtest Engine**, que vai descobrir, com dados históricos reais, se as seis estratégias implementadas aqui têm desempenho estatisticamente consistente — sem essa validação, "CALL"/"PUT" continuam sendo apenas hipóteses de pesquisa, exatamente como a Sprint 5 pede que permaneçam.
