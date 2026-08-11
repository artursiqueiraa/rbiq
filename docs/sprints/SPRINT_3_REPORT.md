# SPRINT 3 — Relatório
## Indicators Engine — IQO Strategy Lab

**Data:** 2026-08-11
**Status:** Concluída. 150 testes passando contra PostgreSQL real (44 Sprint 2 + 106 novos), zero regressão.

---

## 1. Resumo

Construído o Indicators Engine: oito indicadores técnicos (SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic, CCI), todos deterministas, causais (sem look-ahead), com política uniforme para dados insuficientes, um `IndicatorRegistry` para evitar cadeias de `if/elif`, um `IndicatorService` que liga `CandleRepository → indicadores`, e um endpoint `POST /api/indicators/calculate`. O engine não sabe o que é uma estratégia, um sinal, CALL/PUT ou execução — isso é verificado por um teste que analisa estaticamente os imports de todo o pacote `app/indicators/`, não apenas por convenção.

106 testes novos (98 unitários + 8 de integração/performance), todos passando contra o mesmo PostgreSQL real usado desde a Sprint 1. Os 44 testes das Sprints 1 e 2 continuam passando sem alteração — nenhum contrato existente foi quebrado.

---

## 2. Arquitetura

```text
backend/app/indicators/
├── __init__.py       # re-exporta as 8 classes + IndicatorRegistry + calculate_indicators
├── base.py           # Indicator (ABC)
├── types.py          # IndicatorResult
├── registry.py       # IndicatorRegistry, calculate_indicators, result_key
├── service.py         # IndicatorService (API/CLI -> Registry -> Indicator)
├── sma.py / ema.py / rsi.py / macd.py / bollinger.py / atr.py / stochastic.py / cci.py
```

Fluxo real, ponta a ponta:

```text
PostgreSQL → CandleRepository.get_domain() → list[Candle] (domínio, não ORM)
   → IndicatorService.calculate()
      → IndicatorRegistry.create(nome, **parâmetros)  (uma instância por indicador pedido)
      → calculate_indicators(candles, [instâncias])   (roda todos sobre a mesma série)
      → dict {"EMA_20": IndicatorResult, "RSI_14": IndicatorResult, ...}
   → API serializa em JSON
```

Cada arquivo de indicador expõe uma função pura `*_series(...)` (só listas de `float`/`None` — testável isoladamente, sem depender de `Candle` ou banco) e uma classe `Indicator` que converte `Candle.close/high/low` (`Decimal`) para `float` na borda e empacota o resultado em `IndicatorResult`. MACD reaproveita `ema_series` de `ema.py`; Bollinger, Stochastic e CCI reaproveitam `sma_series` de `sma.py` — sem duplicar a média móvel em quatro lugares.

---

## 3. Indicadores implementados

| Indicador | Parâmetros (default) | Séries retornadas |
|---|---|---|
| SMA | `period=20` | `value` |
| EMA | `period=20` | `value` |
| RSI | `period=14` | `value` |
| MACD | `fast_period=12, slow_period=26, signal_period=9` | `macd`, `signal`, `histogram` |
| Bollinger | `period=20, std_multiplier=2.0` | `middle`, `upper`, `lower` |
| ATR | `period=14` | `value` |
| Stochastic | `k_period=14, d_period=3, smooth=3` | `k`, `d` |
| CCI | `period=20` | `value` |

Todos rejeitam parâmetros inválidos (`period <= 0`, etc.) com `ValueError` na construção — antes de qualquer cálculo rodar.

---

## 4. Fórmulas/definições

Cada uma documentada na docstring do próprio módulo (fonte da verdade), resumo aqui:

- **SMA**: média aritmética simples da janela.
- **EMA**: `alpha = 2/(period+1)`, semente = SMA da primeira janela, depois a recorrência exponencial padrão.
- **RSI**: suavização de **Wilder** (não uma SMA simples de ganhos/perdas) — a definição clássica de 1978, que é o que toda plataforma de gráficos chama de "RSI" sem qualificar. `avg_loss == 0` → RSI = 100 (convenção documentada para evitar divisão por zero).
- **MACD**: `EMA(fast) - EMA(slow)`; sinal = `EMA(signal_period)` aplicada à própria linha MACD (não aos preços).
- **Bollinger**: desvio padrão **populacional** (divide por N, não N-1) — escolha deliberada e documentada, já que bibliotecas de estatística costumam usar amostral por padrão.
- **ATR**: True Range definido e testado separadamente (`true_range_series`), depois suavizado com o método de **Wilder** (mesma família de recorrência do RSI).
- **Stochastic**: variante "slow" por padrão (o %K bruto é suavizado antes de virar o %K reportado) — `smooth=1` reduz para o %K "fast"/bruto. Documentado explicitamente porque a definição de "Stochastic" sem qualificador é ambígua entre as duas variantes.
- **CCI**: definição original de Lambert, constante fixa `0.015`. `mean_deviation == 0` → CCI = 0 (janela perfeitamente plana), documentado.

Nenhuma biblioteca externa de indicadores foi usada para comparação — os valores de referência foram derivados manualmente a partir da definição matemática de cada indicador (seção 6) e depois conferidos contra a implementação.

---

## 5. Registry

```python
IndicatorRegistry.get("EMA")                  # -> classe EMA
IndicatorRegistry.create("EMA", period=20)    # -> instância EMA(period=20)
IndicatorRegistry.names()                     # -> lista ordenada dos 8 nomes
calculate_indicators(candles, [SMA(period=20), RSI(period=14)])
# -> {"SMA_20": IndicatorResult, "RSI_14": IndicatorResult}
```

Implementado com um dicionário estático (`name -> classe`), não uma cadeia `if nome == "SMA": ... elif ...`. Adicionar um nono indicador é uma linha em `registry.py`.

---

## 6. Indicator Service

`IndicatorService.calculate(symbol, timeframe, start, end, indicator_specs)`:
1. busca candles via `CandleRepository.get_domain()` (já convertidos para o tipo de domínio, não linhas ORM);
2. constrói uma instância de cada indicador pedido via `IndicatorRegistry.create()`;
3. roda `calculate_indicators()`;
4. devolve timestamps + closes + resultados — pronto para a API serializar.

Nenhuma fórmula vive aqui; é só encanamento. Símbolo sem candles no intervalo retorna séries vazias (não é erro).

---

## 7. API

```text
POST /api/indicators/calculate
```

Corpo:

```json
{
  "symbol": "EURUSD",
  "timeframe": "M1",
  "start": "2026-01-01T00:00:00Z",
  "end": "2026-01-02T00:00:00Z",
  "indicators": [
    {"name": "EMA", "parameters": {"period": 20}},
    {"name": "RSI", "parameters": {"period": 14}}
  ]
}
```

Resposta (verificada com curl real contra o Postgres real, seção 11):

```json
{
  "symbol": "EURUSD",
  "timeframe": "M1",
  "timestamps": ["2026-01-01T00:00:00Z", ...],
  "close": [10.0, 11.0, ...],
  "indicators": {
    "EMA_20": {"parameters": {"period": 20}, "series": {"value": [...]}},
    "RSI_14": {"parameters": {"period": 14}, "series": {"value": [...]}}
  }
}
```

**Desvio deliberado do exemplo da seção 22 da Sprint**: lá, `"EMA_20": [...]` aparece como array plano. Isso não generaliza para indicadores multi-série (MACD tem 3 séries, Bollinger 3, Stochastic 2) sem um formato de resposta inconsistente entre indicadores. Escolhi um formato único (`{"parameters": ..., "series": {...}}`) para todos, incluindo os de série única — mais verboso para SMA/EMA/RSI/ATR/CCI, mas previsível para quem consome a API sem precisar saber de antemão quais indicadores são "simples" e quais são "compostos". `timestamps` e `close` foram adicionados ao nível raiz da resposta (não pedidos explicitamente na Sprint) porque são necessários para qualquer gráfico alinhar o eixo X — sem eles o Indicator Lab não conseguiria desenhar nada.

Validação: nome de indicador desconhecido, parâmetro inválido (`period <= 0`) e timeframe inválido retornam **400** com o motivo em `detail`. A rota (`app/api/routes/indicators.py`) não contém nenhuma fórmula — só conversão de tipos e tratamento de `ValueError → HTTPException`.

---

## 8. Frontend

Página **Indicator Lab** (terceira aba, ao lado de Início e Data Center):

- formulário: ativo, timeframe, início, fim, checkboxes para os 8 indicadores (parâmetros fixos nos defaults documentados na seção 3 — um formulário totalmente dinâmico para todos os parâmetros de todos os indicadores foi deliberadamente deixado de fora para não estourar o escopo da Sprint, conforme a seção 35 autoriza: *"se a interface começar a consumir muito tempo, priorizar o backend e os testes"*);
- gráfico de **Preço + SMA/EMA** e gráfico de **RSI** separado, exatamente como pedido na seção 36;
- tabela com os últimos 10 valores de cada indicador calculado.

O gráfico (`LineChart.tsx`) é um componente SVG próprio, ~40 linhas, sem nenhuma biblioteca de charting nova — evita adicionar uma dependência (recharts, chart.js, etc.) só para duas linhas simples, consistente com a seção 39 ("evitar criar dependência de uma biblioteca inteira apenas para uma função simples").

---

## 9. Testes

**150 testes no total, todos passando contra o PostgreSQL real** (o mesmo container desde a Sprint 1):

```text
tests/indicators/
  test_sma.py, test_ema.py, test_rsi.py, test_macd.py,
  test_bollinger.py, test_atr.py, test_stochastic.py, test_cci.py   → 8 arquivos, ~7-9 testes cada:
      valores de referência (calculados à mão a partir da fórmula, depois conferidos —
      ver seção 12), série constante, série crescente/decrescente, vazio,
      dados insuficientes, parâmetro inválido, formato do IndicatorResult
  test_registry.py                       12 testes
  test_lookahead.py                       8 testes (1 por indicador, parametrizado)
  test_determinism_and_immutability.py   16 testes (determinismo + não-mutação, 1 par por indicador)
  test_isolation.py                       1 teste (análise estática de imports via `ast`)
  integration/
    test_service_integration.py           3 testes (Postgres real via IndicatorService)
    test_api_integration.py               4 testes (Postgres real via API)
    test_performance.py                   1 teste (100.000 candles)

98 testes unitários + 8 de integração/performance = 106 novos
+ 44 das Sprints 1 e 2, sem nenhuma quebra = 150 no total
```

### Look-ahead (seção 31)

Para cada um dos 8 indicadores: calcula sobre `candles[:6]`, depois sobre `candles` completo (10 candles), e verifica que os valores nos primeiros 6 índices são idênticos nos dois casos. Isso é testado de verdade, não assumido — se qualquer indicador olhasse à frente, esse teste quebraria.

### Determinismo e imutabilidade (seções 29-30)

Para cada indicador: roda duas vezes sobre os mesmos candles e compara os resultados (`==` exato — sem aleatoriedade envolvida, então isso é uma garantia real, não uma tolerância). Depois verifica que a lista de candles de entrada continua exatamente com os mesmos objetos, na mesma ordem, após o cálculo.

### Isolamento (seção 38)

`test_isolation.py` não importa nenhum módulo do Indicators Engine e o *executa* — em vez disso, faz `ast.parse()` de cada arquivo `.py` sob `app/indicators/` e verifica estaticamente se algum importa `app.strategies`, `app.signals`, `app.backtest`, `app.paper` ou `app.execution`. Como nenhum desses pacotes existe ainda, um teste que só tentasse importar tudo e checar erros não provaria nada — a análise estática é o que realmente garante a fronteira, inclusive contra sprints futuras.

---

## 10. Performance

100.000 candles, os 8 indicadores calculados de uma vez, contra o PostgreSQL real:

```text
Busca de 100.000 candles do Postgres (CandleRepository.get_domain): 2.62s
Cálculo dos 8 indicadores sobre os 100.000 candles:                  1.78s
```

Sem otimização — implementação em Python puro, sem numpy/pandas (ver seção 13, dependências). Se isso se tornar um gargalo quando o Backtest Engine rodar isso repetidamente sobre janelas deslizantes, o candidato óbvio é vetorizar com numpy, mas isso fica para quando houver necessidade real, não preventivamente.

---

## 11. Problemas encontrados

| # | Problema | Como foi resolvido |
|---|---|---|
| 1 | Ao rastrear manualmente os valores esperados de EMA para os testes de referência, cometi um erro de aritmética (usei `alpha` de um período diferente do que estava calculando). O código em si estava correto — o erro era só no meu cálculo de conferência. | Em vez de confiar só em aritmética manual, rodei os `*_series()` diretamente via `uv run python -c "..."` para ver os valores reais **antes** de escrever qualquer `assert` nos testes, e conferi cada um contra a definição matemática outra vez. Os valores usados nos testes de referência (seção 12) são os que sobreviveram a essa dupla checagem. |
| 2 | Nenhum outro problema bloqueante. | — |

Isso não é um bug no produto — é uma nota sobre como os *valores de referência dos testes* foram validados, incluída aqui porque a Sprint pede rigor explícito nisso (seção 26-27).

---

## 12. Decisões arquiteturais

- **Sem numpy/pandas.** Todos os 8 indicadores são Python puro sobre `list[float]`. Com 100k candles rodando em menos de 2 segundos para os 8 juntos, não havia necessidade real de uma dependência pesada — e a Sprint pede explicitamente para evitar bibliotecas desnecessárias (seção 39).
- **`Decimal` só na borda.** `Candle.open/high/low/close` continuam `Decimal` (como definido na Sprint 2); cada indicador converte para `float` no início de `calculate()` e nunca escreve de volta no candle original — os dados armazenados no banco nunca são tocados.
- **Política única para dados insuficientes: `None` alinhado por índice**, nunca `NaN`, nunca lista truncada. Isso significa que `IndicatorResult.series["value"]` sempre tem o mesmo tamanho que a lista de candles de entrada — essencial para o teste de look-ahead (comparar índice a índice entre uma execução truncada e uma completa) e para o frontend alinhar timestamps com valores sem lógica extra.
- **RSI e ATR usam suavização de Wilder, não SMA simples.** É a definição clássica de cada um; usar uma SMA simples produziria números que ninguém reconheceria como "RSI padrão".
- **MACD reaproveita `ema_series`; Bollinger/Stochastic/CCI reaproveitam `sma_series`.** Em vez de reimplementar médias móveis quatro vezes, os módulos mais simples (`sma.py`, `ema.py`) são a fonte única de verdade, importados pelos módulos compostos — sem violar a separação por arquivo pedida na seção 4 (cada indicador ainda tem seu próprio arquivo com sua própria classe pública).
- **Formato de resposta da API único para todos os indicadores** (série única ou múltipla), mesmo custando verbosidade extra para os simples — ver justificativa na seção 7.
- **`CandleRepository.get_domain()` como novo método**, não substituindo `get()` — mantém o `IndicatorService` (e qualquer engine futura) desacoplado de `CandleModel` (SQLAlchemy), consistente com a camada Repository → Domain já estabelecida na Sprint 2.

---

## 13. Dependências adicionadas

**Nenhuma.** Todo o Indicators Engine usa apenas a biblioteca padrão do Python (`math` não foi nem necessário — `** 0.5` cobre a raiz quadrada do desvio padrão). Nenhuma nova entrada em `pyproject.toml`.

---

## 14. Pendências

Nenhuma pendência técnica bloqueante. Uma nota de escopo, deliberada:

- O formulário do Indicator Lab usa parâmetros fixos (os defaults) para cada indicador em vez de permitir configurar todos os parâmetros de todos os 8 indicadores pela UI — a API já suporta isso; só o formulário não expõe. Fica como extensão natural de uma Sprint futura de dashboard, se necessário.

---

## 15. Próxima Sprint

Aguardando autorização explícita para iniciar a **Sprint 4 — Market Structure & Market Regime**, que consumirá os indicadores construídos aqui (via `IndicatorService`/`IndicatorRegistry`, nunca reimplementando médias móveis) para classificar tendência, suporte/resistência e regime de mercado — sem tocar em estratégias ou sinais, que continuam fora de escopo até a Sprint correspondente.
