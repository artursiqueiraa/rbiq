# SPRINT 4 — Relatório
## Market Structure & Market Regime — IQO Strategy Lab

**Data:** 2026-08-11
**Status:** Concluída. 231 testes passando contra PostgreSQL real (150 das Sprints 1-3 + 81 novos), zero regressão.

---

## 1. Resumo

Construído o Market Engine: detecção causal de swing highs/lows com atraso de confirmação explícito, classificação de estrutura de mercado (HH/HL/LH/LL → BULLISH/BEARISH/RANGE/TRANSITION), detecção de zonas de suporte/resistência por clustering, classificação de regime (direção/volatilidade/força de tendência, todos normalizados de forma relativa, nunca com limiares absolutos fixos), e o `MarketSnapshot` — o contrato de saída que uma futura Strategy Engine vai consumir.

Nada aqui decide entrada, direção de operação ou conhece CALL/PUT — o pacote inteiro é auditável por análise estática de imports, não apenas por convenção (mesma técnica da Sprint 3).

Durante o teste de performance com 100.000 candles encontrei e corrigi um bug real de complexidade O(n²) no agrupamento de zonas de suporte/resistência (seção 17) — reduziu o tempo de 28,8s para 0,77s.

---

## 2. Arquitetura

```text
backend/app/market/
├── types.py                          # SwingPoint, StructureEvent, Zone, MarketSnapshot, enums
├── structure/
│   ├── swings.py                     # detect_swings — fractal com confirmação atrasada
│   ├── trend.py                      # compare_swing, classify_state (HH/HL/LH/LL -> StructureState)
│   ├── structure_engine.py           # analyze_structure — orquestração causal + eventos
│   └── support_resistance.py         # detect_zones — clustering de S/R
├── regime/
│   ├── volatility.py                 # normalized_atr_series, classify_volatility
│   ├── classifier.py                 # direction_from_structure, classify_regime
│   └── regime_engine.py              # compute_trend_strength, compute_regime
├── snapshot.py                       # build_snapshot — função pura, sem I/O
└── service.py                        # MarketService — busca candles + chama build_snapshot
```

Fluxo real, ponta a ponta:

```text
PostgreSQL → CandleRepository.get_domain(..., end=timestamp)   [causal: nunca busca além de `timestamp`]
   → build_snapshot(candles)   [função pura]
      → detect_swings()                          → list[SwingPoint]
      → analyze_structure(candles, swings)        → StructureState + StructureEvent[]
      → detect_zones(swings)                      → Zone[] (supports/resistances)
      → ATR(period).calculate(candles) / EMA(period).calculate(candles)   [reaproveitados da Sprint 3]
      → compute_regime(...)                       → direction + regime + volatility + trend_strength
   → MarketSnapshot
```

---

## 3. Swing Detection

`detect_swings(candles, left_bars=2, right_bars=2)`: candle `i` é um **swing high** se seu `high` é o máximo estrito da janela `[i-left_bars, i+right_bars]`; empates são resolvidos pegando apenas a **primeira ocorrência** do valor máximo dentro da janela (testado explicitamente em `test_tied_high_only_flags_the_leftmost_occurrence`). Regra simétrica para swing low.

`strength` é uma medida simples e documentada em unidades de preço bruto (quanto o swing se destaca da média dos outros extremos na janela) — deliberadamente **não normalizada** entre ativos, já que essa normalização (via ATR) é responsabilidade da camada de regime, que já tem acesso a isso.

---

## 4. Confirmation Model

Cada `SwingPoint` tem dois timestamps:

```text
timestamp               — quando o extremo aconteceu (candle central)
confirmation_timestamp  — quando havia candles suficientes à direita para confirmar
```

Um swing só é **retornado** por `detect_swings` quando `i + right_bars` existe dentro da lista de candles fornecida — ou seja, chamar a função com uma lista truncada nunca produz um swing "adiantado". Essa é a propriedade central que torna todo o Market Engine livre de look-ahead (seção 15, testes de look-ahead).

Verificado com um dataset `T0..T4` explícito (`test_swing_not_confirmed_until_enough_future_candles_exist`, `test_confirmation_timestamp_is_preserved_and_differs_from_occurrence`): com `T0..T3` o swing em `T2` não é confirmável; com `T0..T4` ele é, e `confirmation_timestamp == T4 > timestamp == T2`.

---

## 5. Market Structure

`classify_state(confirmed_highs, confirmed_lows)` — árvore de decisão determinística e documentada, comparando os **dois swings mais recentes de cada tipo**:

```text
menos de 2 highs OU menos de 2 lows confirmados  -> UNKNOWN
high_trend=HIGHER e low_trend=HIGHER             -> BULLISH   (HH + HL)
high_trend=LOWER  e low_trend=LOWER              -> BEARISH   (LL + LH)
high_trend=EQUAL ou low_trend=EQUAL              -> RANGE     (preço respeitando o mesmo extremo)
qualquer outra combinação (HH+LL ou LH+HL)       -> TRANSITION
```

Nenhum machine learning, conforme exigido. As três combinações pedidas explicitamente pela Sprint (seção 39) têm teste dedicado com datasets construídos à mão e **verificados executando o código antes de fixar as asserções** (ver seção 17, "Problemas encontrados" — depois do que aconteceu na Sprint 3, não confio mais em aritmética manual sem checar).

---

## 6. Structure Events

`analyze_structure` percorre os candles em ordem cronológica e só usa swings cujo `confirmation_timestamp` já foi alcançado pelo candle sendo processado — por isso repetir a análise sobre um prefixo produz exatamente os mesmos eventos (até aquele ponto) que a análise completa.

Eventos emitidos: `SWING_HIGH_CONFIRMED`, `SWING_LOW_CONFIRMED`, `HIGHER_HIGH`, `HIGHER_LOW`, `LOWER_HIGH`, `LOWER_LOW`, `STRUCTURE_CHANGE` (sempre que `classify_state` muda), `STRUCTURE_BREAK` (preço fecha abaixo da última HL confirmada durante um estado BULLISH, ou acima da última LH durante BEARISH — o "rompimento" da premissa da tendência atual, força o estado para `TRANSITION`).

---

## 7. Support & Resistance

`detect_zones(swings, tolerance_pct=0.001)`: agrupa swing lows em zonas `SUPPORT` e swing highs em zonas `RESISTANCE` por proximidade **relativa** de preço (0,1% por padrão — nunca um valor absoluto como `0.001` fixo, conforme a seção 53 exige). Algoritmo guloso: swings ordenados por preço, cada novo swing entra no grupo atual se estiver dentro da tolerância dos limites atuais do grupo; senão, um novo grupo começa.

`strength = touches * (1 + recency)`, onde `recency` é a posição temporal do último toque da zona dentro do intervalo total de confirmações observado (0 = mais antigo, 1 = mais recente) — fórmula simples e documentada, combinando os dois fatores que a seção 20 pede (número de testes e recência) sem inventar um score arbitrário.

---

## 8. Market Regime

`classify_regime(structure_state, volatility)`:

```text
BULLISH     -> TRENDING_BULLISH
BEARISH     -> TRENDING_BEARISH
TRANSITION  -> TRANSITION
RANGE       -> RANGING, exceto quando volatility=HIGH -> HIGH_VOLATILITY, ou volatility=LOW -> LOW_VOLATILITY
UNKNOWN     -> UNKNOWN
```

`direction` é derivada diretamente do `structure_state` já calculado (uma única fonte de verdade, não uma segunda lógica que poderia divergir). `regime` e `volatility` continuam como campos separados no `MarketSnapshot`, conforme a seção 21 pede.

---

## 9. Volatility

`normalized_atr_series = ATR / close` (relativo, não absoluto — seção 25). Classificação por **percentil móvel** dentro de uma janela configurável (`volatility_window`, padrão 100): tercil inferior → `LOW`, tercil superior → `HIGH`, meio → `NORMAL`. Isso significa que o mesmo ativo pode ser classificado de forma diferente dependendo apenas da sua própria história recente — nunca contra um limiar fixo que seria inadequado para ativos com escalas diferentes.

`trend_strength` (seção 26-27): `slope = (EMA[i] - EMA[i-slope_period]) / slope_period`; `trend_strength = min(1.0, abs(slope) / ATR[i])` — expressa a inclinação da EMA em "quantos ATRs por candle", escala livre entre ativos pela mesma razão. Nem ATR nem EMA são recalculados aqui — ambos vêm de `app.indicators` (Sprint 3).

---

## 10. Market Snapshot

`build_snapshot(candles, symbol, timeframe, params)` é uma **função pura** — sem banco, sem I/O. Isso é o que garante a causalidade "de graça": como ela só olha para índices dentro de `candles`, `build_snapshot(candles[:k])` nunca difere do que `build_snapshot(candles)` teria produzido naquele mesmo ponto (testado em `test_snapshot_at_a_point_in_time_is_unaffected_by_later_candles`).

`MarketParams` reúne todos os parâmetros configuráveis (`left_bars`, `right_bars`, `sr_tolerance_pct`, `volatility_window`, `trend_ema_period`, `trend_slope_period`, `atr_period`) — nenhum número mágico espalhado pelo código (seção 52).

Candles vazios → snapshot totalmente `UNKNOWN`, sem erro.

---

## 11. API

```text
GET /api/market/snapshot?symbol=&timeframe=&timestamp=
GET /api/market/structure?symbol=&timeframe=&start=&end=
```

Ambas verificadas com curl real contra o Postgres real (seção 15). A rota (`app/api/routes/market.py`) só converte tipos e delega para `MarketService` — nenhuma fórmula vive ali. Timeframe inválido → 400.

---

## 12. Frontend

Página **Market Lab** (quarta aba): formulário (ativo, timeframe, timestamp) + painel de estado (direction/structure/regime/volatility/trend strength) + gráfico + tabela de suportes/resistências.

O gráfico (`MarketChart.tsx`, SVG próprio, sem biblioteca nova) desenha explicitamente **dois marcadores por swing** — um círculo vazado na posição em que o swing aconteceu e um círculo preenchido na posição em que foi confirmado, ligados por uma linha tracejada — exatamente para não esconder o atraso de confirmação, conforme a seção 51 exige. Zonas de suporte/resistência aparecem como faixas horizontais semitransparentes.

---

## 13. Testes

**81 testes novos, todos passando (72 unitários + 9 de integração/performance), mais os 150 das Sprints 1-3 sem nenhuma quebra = 231 no total.**

```text
tests/market/structure/test_swings.py                 9 testes
tests/market/structure/test_trend.py                  10 testes
tests/market/structure/test_structure_engine.py        8 testes
tests/market/structure/test_support_resistance.py      7 testes
tests/market/regime/test_volatility.py                 9 testes
tests/market/regime/test_classifier.py                 8 testes
tests/market/regime/test_regime_engine.py               7 testes
tests/market/test_snapshot.py                          5 testes
tests/market/test_lookahead.py                         3 testes
tests/market/test_confirmation.py                       2 testes
tests/market/test_determinism_and_immutability.py       2 testes
tests/market/test_isolation.py                          1 teste  (análise estática via `ast`)
tests/market/integration/
  test_service_integration.py                          4 testes (Postgres real)
  test_api_integration.py                               4 testes (Postgres real)
  test_performance.py                                    1 teste (100.000 candles)
```

Datasets de referência (`tests/market/conftest.py`) foram **verificados executando o código real antes de serem fixados como esperados** — incluindo `BULLISH_CLOSES` (HH+HL confirmado), seu espelho `BEARISH_CLOSES` (LL+LH, gerado por `37 - x` para inverter picos/vales mantendo preços positivos), `RANGE_CLOSES` (onda triangular repetindo os mesmos picos/vales) e `BREAK_CLOSES` (o dataset bullish seguido de uma queda que rompe a última HL). Essa disciplina evitou repetir o erro de aritmética manual da Sprint 3.

---

## 14. Look-ahead validation

Três níveis, todos obrigatórios pela Sprint e todos implementados:

1. **Nível swing** (seção 9): com `T0..T3` um swing candidato em `T2` não é retornado; com `T0..T4` ele é — testado diretamente contra `detect_swings`.
2. **Nível swing "não muda com mais dados futuros"** (seção 42, aplicado a swings): um swing já confirmado a partir de um prefixo de candles mantém exatamente o mesmo preço/timestamp/confirmation_timestamp depois que mais candles são adicionados ao final.
3. **Nível snapshot** (seção 31/42): `build_snapshot` sobre um prefixo de candles produz `structure_state`, `direction`, `regime`, últimos swings e `structure_events` idênticos ao que a mesma função produziria sobre o dataset completo truncado no mesmo ponto — testado tanto em memória (`test_snapshot.py`) quanto através do banco real, pedindo o snapshot em um timestamp anterior a uma confirmação posterior (`test_snapshot_at_an_earlier_timestamp_only_sees_earlier_candles`).

---

## 15. Performance

100.000 candles (zigzag sintético com deriva lenta, gerando ~50.000 swings — um cenário deliberadamente mais adversarial que dados de mercado reais, para estressar o clustering de S/R):

```text
Busca de 100.000 candles do Postgres (CandleRepository.get_domain): 2.73s
Swings + Structure + Support/Resistance + Regime + Snapshot:
  antes da correção (seção 17):  28.83s
  depois da correção:             0.77s   (37x mais rápido)
```

---

## 16. Problemas encontrados

| # | Problema | Como foi resolvido |
|---|---|---|
| 1 | **Bug real de O(n²)** em `support_resistance._cluster`: a cada swing adicionado a um grupo, o código recalculava `min()`/`max()` sobre **todo o grupo acumulado até ali** para checar a tolerância. Com dados reais de 100k candles (zigzag denso), quase todos os ~50.000 swings ordenados por preço caíram em um único grupo gigante por causa da deriva lenta de preço — e recalcular min/max de um grupo de ~25.000 elementos a cada uma das ~25.000 inserções custou ~28,8s. Só apareceu no teste de performance obrigatório da seção 32; nenhum teste unitário (que usa poucos swings) o teria pego. | Como `sorted_swings` já vem ordenado por preço, o mínimo do grupo é sempre seu primeiro membro e o máximo é sempre o último adicionado — passei a rastrear `group_low`/`group_high` como variáveis correntes em vez de recalcular. O(n) por grupo em vez de O(n²). Testes unitários de `support_resistance` continuam passando sem alteração de comportamento, só de custo. |
| 2 | Ao escrever os testes de referência para `classify_volatility`, dois datasets que eu tinha escolhido "de cabeça" davam resultados diferentes do que eu esperava (um ficava `HIGH` em vez de `NORMAL`, outro `NORMAL` em vez de `LOW`) por causa de como a fórmula de rank trata empates (`<=`, não `<`). | Rodei `classify_volatility` diretamente antes de fixar os valores esperados nos testes (mesma disciplina adotada desde o problema #1 da Sprint 3) e ajustei os datasets para produzir resultados inequívocos, longe das fronteiras de tercil. |
| 3 | Um teste inicial de look-ahead assumia que 9 candles seriam suficientes para confirmar dois swings do dataset bullish; na verdade eram necessários 11 (o segundo swing de cada dataset de referência precisa de `right_bars` candles adicionais além do seu próprio índice). | Corrigido o tamanho do prefixo no teste depois de rodar `detect_swings` e conferir o resultado real, em vez de assumir. |

Nenhum outro problema bloqueante.

---

## 17. Decisões arquiteturais

- **`build_snapshot` é uma função pura, `MarketService` é a única coisa que toca o banco.** Mesma separação estabelecida nas Sprints 2-3 (Normalizer/Validator puros vs. `DataIngestionService`; indicadores puros vs. `IndicatorService`) — o que torna a causalidade e o determinismo triviais de testar sem precisar de Postgres na maioria dos testes.
- **Confirmação de swing via truncamento da lista de candles, não via um campo `is_confirmed`.** Um swing só existe na lista retornada por `detect_swings` se `i + right_bars` estiver dentro do range fornecido — não há como "esquecer" de checar uma flag, porque não existe.
- **`analyze_structure` processa candles e swings juntos em ordem cronológica** (via cursor sobre swings ordenados por `confirmation_timestamp`), não em duas passagens separadas — garante que nenhum evento apareça fora de ordem e que o `STRUCTURE_BREAK` (que depende do preço de fechamento de cada candle) veja exatamente o estado que existia naquele instante.
- **`Zone` como faixa (`lower_bound`/`upper_bound`), nunca um preço exato** — conforme a seção 18 pede, e necessário de qualquer forma já que zonas nascem de um agrupamento de múltiplos preços.
- **`regime` mapeia RANGE+volatilidade para HIGH_VOLATILITY/LOW_VOLATILITY** em vez de sempre retornar RANGING — decisão documentada na seção 8 do relatório e no docstring de `classify_regime`, para que o campo único `regime` carregue a informação mais útil quando a estrutura por si só não indica direção.
- **Nenhuma tabela nova no banco.** Tudo é recalculado sob demanda a partir de `candles` (que já está persistido desde a Sprint 2) — consistente com a seção 37 ("não persistir tudo ainda... priorizar cálculo determinístico").

---

## 18. Dependências

**Nenhuma.** Todo o Market Engine usa apenas a biblioteca padrão do Python e reaproveita `app.indicators` (ATR, EMA) e `app.data`/`app.repositories` já existentes. Nenhuma nova entrada em `pyproject.toml`.

---

## 19. Pendências

Nenhuma pendência técnica bloqueante.

- O `MarketChart` do frontend assume que os timestamps de swing existem no array de candles buscado para o gráfico (mesmo range de datas); se o usuário pedir um snapshot cujo lookback não inclua o candle exato de ocorrência/confirmação de um swing antigo, esse marcador específico simplesmente não é desenhado (sem erro, mas sem aviso visual) — comportamento aceitável para esta Sprint, mas vale revisitar se o Market Lab evoluir.

---

## 20. Próxima Sprint

Aguardando autorização explícita para iniciar a **Sprint 5**, que segundo a ordem definida na documentação (`docs/architecture.md`) é o **Strategy Engine** — a primeira Sprint que poderá consumir o `MarketSnapshot` como seu contrato de entrada (Trend Following, Pullback, Breakout, Mean Reversion, Price Action, Divergence), sem precisar conhecer candles, indicadores, swings ou suporte/resistência diretamente. Nenhuma estratégia, sinal, CALL/PUT ou lógica de entrada foi tocada nesta Sprint.
