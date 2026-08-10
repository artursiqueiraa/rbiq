# IQO Strategy Lab

## Especificação Técnica Completa do Projeto

**Versão:** 1.0
**Objetivo:** reconstrução completa do projeto do zero
**Plataforma-alvo de dados:** IQ Option / fontes de mercado compatíveis
**Modo operacional:** análise, backtest e paper trading
**Idioma da aplicação:** Português — Brasil

---

# 1. VISÃO GERAL

O IQO Strategy Lab será uma plataforma de pesquisa e análise quantitativa destinada a estudar estratégias de mercado utilizando dados históricos e dados de mercado em tempo real.

O sistema NÃO deve começar pela execução de operações.

A prioridade será construir uma infraestrutura confiável capaz de:

1. receber dados;
2. armazenar candles;
3. calcular indicadores;
4. identificar condições de mercado;
5. gerar sinais hipotéticos;
6. executar backtests;
7. executar paper trading;
8. registrar absolutamente tudo;
9. comparar estratégias;
10. avaliar robustez;
11. apresentar os resultados em um dashboard.

A arquitetura deve ser modular para que uma estratégia possa ser adicionada ou removida sem alterar o restante do sistema.

---

# 2. OBJETIVO PRINCIPAL

O sistema deve responder perguntas como:

* Qual estratégia apresenta melhor resultado histórico?
* Em qual ativo determinada estratégia funciona melhor?
* Em quais horários ela funciona?
* Qual timeframe apresenta melhor comportamento?
* A estratégia funciona em tendência?
* Funciona em lateralização?
* Como ela se comporta em alta volatilidade?
* Quantas perdas consecutivas podem ocorrer?
* Qual é o drawdown máximo?
* O resultado continua existindo fora da amostra utilizada para desenvolvimento?
* A estratégia depende de parâmetros muito específicos?
* Pequenas alterações nos parâmetros destroem o resultado?
* Qual estratégia é mais robusta?

O sistema NÃO deve assumir previamente que uma estratégia funciona.

Ele deve testar a hipótese.

---

# 3. PRINCÍPIO FUNDAMENTAL

Não procurar:

> "Uma estratégia que ganha 90%."

Procurar:

> "Uma estratégia que apresente comportamento estatisticamente consistente em diferentes períodos e condições de mercado."

Uma estratégia com 60% de acerto e comportamento consistente pode ser mais interessante para pesquisa do que uma estratégia com 90% de acerto em um único período histórico.

---

# 4. ARQUITETURA GERAL

Arquitetura proposta:

```text
                    ┌──────────────────────┐
                    │      DATA SOURCES    │
                    │                      │
                    │ IQ Option / Histórico│
                    │ Outros provedores    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    DATA INGESTION    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   DATA NORMALIZER    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    MARKET DATABASE   │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       ┌────────────┐   ┌────────────┐   ┌────────────┐
       │Indicators  │   │Market      │   │Features    │
       │Engine      │   │Regime      │   │Engine      │
       └─────┬──────┘   └─────┬──────┘   └─────┬──────┘
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                    ┌──────────────────────┐
                    │  STRATEGY ENGINE     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    SIGNAL ENGINE     │
                    └──────────┬───────────┘
                               │
                    ┌──────────┴───────────┐
                    ▼                      ▼
             ┌─────────────┐       ┌─────────────┐
             │ BACKTEST    │       │ PAPER       │
             │ ENGINE      │       │ TRADING     │
             └──────┬──────┘       └──────┬──────┘
                    │                     │
                    └──────────┬──────────┘
                               ▼
                    ┌──────────────────────┐
                    │ PERFORMANCE ENGINE   │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │     DASHBOARD        │
                    └──────────────────────┘
```

---

# 5. STACK TECNOLÓGICA

## Backend

Python 3.11+

Framework:

* FastAPI

Bibliotecas:

* pandas
* numpy
* pydantic
* SQLAlchemy
* Alembic
* httpx
* websockets
* pytest
* pytest-asyncio
* loguru
* scipy
* scikit-learn

Indicadores:

Preferencialmente implementar os indicadores internamente ou utilizar biblioteca consolidada, mas manter uma camada própria para evitar acoplamento.

---

# 6. BANCO DE DADOS

Utilizar PostgreSQL.

Durante desenvolvimento local, SQLite pode ser permitido para testes rápidos, mas a arquitetura deve ser compatível com PostgreSQL.

---

# 7. ESTRUTURA DO PROJETO

```text
iqo-strategy-lab/

├── backend/
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── assets.py
│   │   │   │   ├── candles.py
│   │   │   │   ├── strategies.py
│   │   │   │   ├── signals.py
│   │   │   │   ├── backtests.py
│   │   │   │   ├── paper_trading.py
│   │   │   │   ├── performance.py
│   │   │   │   └── system.py
│   │   │   └── dependencies.py
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   │
│   │   ├── data/
│   │   │   ├── providers/
│   │   │   ├── ingestion/
│   │   │   ├── normalizer.py
│   │   │   └── validator.py
│   │   │
│   │   ├── indicators/
│   │   │   ├── ema.py
│   │   │   ├── sma.py
│   │   │   ├── rsi.py
│   │   │   ├── macd.py
│   │   │   ├── bollinger.py
│   │   │   ├── atr.py
│   │   │   ├── stochastic.py
│   │   │   └── cci.py
│   │   │
│   │   ├── market/
│   │   │   ├── structure.py
│   │   │   ├── support_resistance.py
│   │   │   ├── volatility.py
│   │   │   └── regime.py
│   │   │
│   │   ├── strategies/
│   │   │   ├── base.py
│   │   │   ├── registry.py
│   │   │   ├── trend_following.py
│   │   │   ├── pullback.py
│   │   │   ├── breakout.py
│   │   │   ├── mean_reversion.py
│   │   │   ├── price_action.py
│   │   │   └── divergence.py
│   │   │
│   │   ├── signals/
│   │   │   ├── generator.py
│   │   │   ├── scorer.py
│   │   │   └── validator.py
│   │   │
│   │   ├── backtest/
│   │   │   ├── engine.py
│   │   │   ├── simulator.py
│   │   │   ├── metrics.py
│   │   │   ├── walk_forward.py
│   │   │   └── monte_carlo.py
│   │   │
│   │   ├── paper/
│   │   │   ├── engine.py
│   │   │   └── simulator.py
│   │   │
│   │   ├── performance/
│   │   │   ├── analyzer.py
│   │   │   ├── statistics.py
│   │   │   └── reports.py
│   │   │
│   │   ├── models/
│   │   │   ├── asset.py
│   │   │   ├── candle.py
│   │   │   ├── strategy.py
│   │   │   ├── signal.py
│   │   │   ├── backtest.py
│   │   │   └── paper_trade.py
│   │   │
│   │   └── database/
│   │       ├── session.py
│   │       ├── models.py
│   │       └── migrations/
│   │
│   └── tests/
│       ├── indicators/
│       ├── strategies/
│       ├── backtest/
│       ├── data/
│       └── api/
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── services/
│   │   ├── hooks/
│   │   └── types/
│   └── package.json
│
├── data/
│   ├── raw/
│   ├── normalized/
│   └── exports/
│
├── docker/
├── docker-compose.yml
├── .env.example
├── README.md
└── docs/
    ├── architecture.md
    ├── strategies.md
    ├── backtesting.md
    └── api.md
```

---

# 8. MODELO DE DADOS

## Asset

```text
id
symbol
name
market
timezone
active
created_at
updated_at
```

## Candle

```text
id
asset_id
timeframe
timestamp
open
high
low
close
volume
source
created_at
```

Criar índice:

```text
(asset_id, timeframe, timestamp)
```

Nunca permitir candles duplicados.

---

# 9. INDICADORES

O sistema deve possuir uma camada independente de indicadores.

Indicadores iniciais:

### Tendência

* SMA
* EMA 9
* EMA 20
* EMA 50
* EMA 100
* EMA 200

### Momentum

* RSI
* MACD
* Stochastic
* CCI

### Volatilidade

* ATR
* Bollinger Bands

### Estrutura

* máximas locais
* mínimas locais
* swing highs
* swing lows
* suporte
* resistência

Cada indicador deve possuir testes unitários.

Exemplo:

```python
calculate_ema(candles, period=20)
calculate_rsi(candles, period=14)
calculate_atr(candles, period=14)
```

---

# 10. MARKET REGIME

Uma das partes mais importantes do sistema.

Antes de analisar uma estratégia, o sistema deve tentar identificar o regime atual.

Categorias iniciais:

```text
TREND_UP
TREND_DOWN
RANGE
HIGH_VOLATILITY
LOW_VOLATILITY
UNCERTAIN
```

Exemplo:

```text
EMA20 > EMA50
+
inclinação positiva
+
estrutura de máximas ascendentes

=> TREND_UP
```

Outro exemplo:

```text
EMA20 próxima da EMA50
+
ATR baixo
+
preço oscilando em uma faixa

=> RANGE
```

O algoritmo não deve assumir que essa classificação é perfeita.

Ela também precisa ser testada no backtest.

---

# 11. ESTRATÉGIA — INTERFACE PADRÃO

Todas as estratégias devem implementar a mesma interface.

Exemplo conceitual:

```python
class Strategy:

    name: str

    def prepare(self, market_data):
        pass

    def evaluate(self, context):
        pass

    def get_parameters(self):
        pass
```

Resultado:

```python
Signal(
    strategy="pullback",
    direction="CALL",
    confidence=0.78,
    timestamp=...,
    metadata={}
)
```

Importante:

O sistema deve tratar isso como **sinal de pesquisa**, não como ordem.

---

# 12. ESTRATÉGIA 1 — TREND FOLLOWING

Hipótese:

> Estratégias que acompanham a tendência podem apresentar comportamento diferente das estratégias de reversão.

Variáveis:

* EMA20
* EMA50
* EMA200
* estrutura de mercado

Exemplo de classificação:

```text
EMA20 > EMA50 > EMA200
+
preço acima da EMA200
=
tendência de alta
```

O backtester deve medir o desempenho dessa condição.

Não assumir que ela é lucrativa.

---

# 13. ESTRATÉGIA 2 — PULLBACK

Hipótese:

> Após um movimento direcional, o preço pode retornar temporariamente para uma região de interesse antes de continuar seu movimento.

Componentes:

* tendência no timeframe maior;
* região de suporte/resistência;
* retorno do preço;
* confirmação no timeframe menor.

O sistema deve permitir configurar:

```text
TIMEFRAME_CONTEXT
TIMEFRAME_ENTRY
EMA_FAST
EMA_SLOW
ZONE_TOLERANCE
CONFIRMATION_TYPE
```

---

# 14. ESTRATÉGIA 3 — BREAKOUT

Hipótese:

> Uma consolidação pode ser seguida por expansão de volatilidade.

Identificar:

```text
RANGE
    ↓
compressão
    ↓
rompimento
    ↓
expansão
```

Variáveis:

* tamanho do range;
* ATR;
* volume, quando disponível;
* distância do rompimento;
* duração da consolidação.

O backtester deve identificar falsos rompimentos separadamente.

---

# 15. ESTRATÉGIA 4 — MEAN REVERSION

Hipótese:

> Em determinados regimes laterais, movimentos extremos podem apresentar retorno em direção à média.

Indicadores possíveis:

* Bollinger Bands;
* RSI;
* distância da média;
* ATR.

IMPORTANTE:

Essa estratégia deve ser habilitada preferencialmente apenas quando o classificador indicar RANGE.

---

# 16. ESTRATÉGIA 5 — PRICE ACTION

Criar um módulo de estrutura de mercado.

Detectar:

* swing high;
* swing low;
* rompimento;
* rejeição;
* engolfo;
* candle de força;
* falso rompimento.

A estratégia não deve depender exclusivamente de indicadores.

---

# 17. ESTRATÉGIA 6 — DIVERGÊNCIA

Detectar divergências entre:

* preço × RSI;
* preço × MACD;
* preço × Stochastic.

Tipos:

```text
BULLISH_DIVERGENCE
BEARISH_DIVERGENCE
```

Registrar:

```text
price_swing_1
price_swing_2
indicator_swing_1
indicator_swing_2
distance
time_between_swings
```

---

# 18. SCORE DE SINAL

O sistema pode possuir um score, mas o score não deve ser tratado como "probabilidade real de vitória".

Exemplo:

```text
Trend condition       +30
Market regime         +20
Support/resistance    +15
Momentum              +15
Volatility             +10
Price action           +10
--------------------------
Total                  100
```

O sistema deve permitir testar:

```text
threshold = 60
threshold = 70
threshold = 80
threshold = 90
```

e comparar resultados.

---

# 19. MULTI-TIMEFRAME

O sistema deve permitir análise simultânea:

```text
M15
 ↓
contexto

M5
 ↓
estrutura intermediária

M1
 ↓
sinal de pesquisa
```

O timeframe deve ser configurável.

Não deixar M1/M15 fixos no código.

---

# 20. BACKTEST ENGINE

Essa é uma das partes mais importantes.

O backtest deve reproduzir a sequência temporal real.

Nunca permitir:

```text
futuro → passado
```

ou utilização de dados futuros na decisão.

Cada candle deve ser processado na ordem:

```text
candle 1
candle 2
candle 3
...
candle N
```

A estratégia só pode utilizar informações disponíveis naquele instante.

---

# 21. EVITAR LOOK-AHEAD BIAS

Exemplo proibido:

Utilizar uma máxima futura para decidir que um suporte existia no passado.

O algoritmo precisa considerar somente informações que já estavam disponíveis.

Isso deve possuir testes automatizados.

---

# 22. BACKTEST CONFIG

Exemplo:

```json
{
  "asset": "EURUSD",
  "timeframe": "M1",
  "start_date": "2025-01-01",
  "end_date": "2025-06-30",
  "strategy": "pullback",
  "parameters": {
    "ema_fast": 20,
    "ema_slow": 50,
    "rsi_period": 14
  }
}
```

---

# 23. MÉTRICAS

Cada backtest deve gerar:

```text
Total de sinais
Sinais válidos
Sinais inválidos
Acertos
Erros
Taxa de acerto
Sequência máxima de acertos
Sequência máxima de erros
Drawdown máximo
Retorno acumulado
Expectancy
Profit Factor
Sharpe Ratio
Sortino Ratio
```

Não utilizar somente win rate para avaliar estratégia.

---

# 24. WALK-FORWARD

Dividir os dados:

```text
┌──────────────┬──────────────┬──────────────┐
│ TREINAMENTO  │ VALIDAÇÃO    │ TESTE        │
└──────────────┴──────────────┴──────────────┘
```

Depois avançar a janela.

Exemplo:

```text
Train → Validate → Test
        ↓
Move janela
        ↓
Train → Validate → Test
```

O objetivo é verificar se a estratégia continua funcionando quando aplicada a períodos que não foram usados para desenvolvimento.

---

# 25. OUT-OF-SAMPLE

Reservar uma parcela dos dados que nunca será usada para otimização.

Exemplo:

```text
70% desenvolvimento
15% validação
15% teste final
```

O resultado do teste final deve ser preservado.

Não ficar ajustando parâmetros depois de olhar o resultado.

---

# 26. MONTE CARLO

Criar simulações de diferentes ordens dos resultados históricos para avaliar:

* drawdown possível;
* sequências de perdas;
* distribuição dos resultados;
* risco de resultados extremos.

O objetivo não é prever o futuro.

É avaliar a fragilidade do resultado encontrado.

---

# 27. OTIMIZAÇÃO DE PARÂMETROS

O sistema deve permitir:

```text
EMA_FAST:
10 → 30

EMA_SLOW:
40 → 100

RSI:
10 → 20

THRESHOLD:
60 → 90
```

Porém:

NÃO selecionar automaticamente o melhor resultado sem verificar robustez.

Uma estratégia que funciona apenas em:

```text
EMA20
RSI14
threshold73
```

pode ser excessivamente ajustada.

O sistema deve procurar regiões de estabilidade.

Exemplo:

```text
EMA 18–24
RSI 12–16
Threshold 70–80
```

Se vários parâmetros próximos apresentam resultados semelhantes, isso é um sinal de maior robustez.

---

# 28. PAPER TRADING

O paper trading deve simular os sinais sem enviar ordens reais.

Fluxo:

```text
Dados reais
    ↓
Estratégia
    ↓
Sinal
    ↓
Paper Executor
    ↓
Resultado simulado
    ↓
Banco
```

Registrar:

```text
timestamp
ativo
estratégia
direção
preço de referência
timestamp de expiração
resultado
motivo do sinal
indicadores
regime
```

---

# 29. AUDITORIA DE SINAIS

Cada sinal precisa ser completamente reproduzível.

Salvar um snapshot:

```json
{
  "strategy": "pullback",
  "asset": "EURUSD",
  "timeframe": "M1",
  "timestamp": "...",
  "market_regime": "TREND_UP",
  "ema20": 1.123,
  "ema50": 1.121,
  "rsi": 54.2,
  "atr": 0.0012,
  "support_distance": 0.0003,
  "score": 78
}
```

Isso permite descobrir posteriormente:

> Por que o sistema gerou esse sinal?

---

# 30. DASHBOARD

Frontend em:

```text
React + TypeScript + Vite
```

Páginas:

## Dashboard

Mostrar:

* sinais recentes;
* estratégias ativas;
* paper trades;
* desempenho;
* regime atual;
* ativos monitorados.

## Estratégias

Lista:

```text
Trend Following
Pullback
Breakout
Mean Reversion
Price Action
Divergence
```

Cada estratégia deve mostrar:

```text
Status
Parâmetros
Último sinal
Performance
```

## Backtests

Permitir:

```text
Selecionar ativo
Selecionar período
Selecionar estratégia
Selecionar parâmetros
Executar
```

Mostrar gráficos.

## Comparação

Permitir comparar:

```text
Estratégia A
vs
Estratégia B
vs
Estratégia C
```

## Sinais

Tabela:

```text
Data
Ativo
Estratégia
Regime
Direção
Score
Resultado
```

## Performance

Gráficos:

* equity curve;
* drawdown;
* distribuição de resultados;
* resultados por horário;
* resultados por ativo;
* resultados por regime;
* resultados por dia da semana.

---

# 31. ANÁLISE POR REGIME

Essa funcionalidade é obrigatória.

Exemplo:

```text
                 TREND UP
Strategy A       63%
Strategy B       52%
Strategy C       48%

                 RANGE
Strategy A       47%
Strategy B       61%
Strategy C       53%
```

Isso permite descobrir que uma estratégia pode funcionar melhor em determinado ambiente.

---

# 32. ANÁLISE POR HORÁRIO

Gerar:

```text
00:00–01:00
01:00–02:00
...
23:00–00:00
```

E calcular métricas para cada janela.

Não assumir previamente que determinado horário é melhor.

---

# 33. ANÁLISE POR ATIVO

Exemplo:

```text
EURUSD
GBPUSD
USDJPY
AUDUSD
...
```

Mostrar:

```text
Quantidade de sinais
Taxa de acerto
Expectancy
Drawdown
Resultado
```

---

# 34. ANÁLISE POR TIMEFRAME

Permitir comparar:

```text
M1
M5
M15
M30
H1
```

A estratégia deve receber timeframe como parâmetro.

---

# 35. SISTEMA DE CONFIGURAÇÃO

Não colocar parâmetros diretamente no código.

Utilizar configuração:

```yaml
strategy:
  name: pullback

parameters:
  ema_fast: 20
  ema_slow: 50
  rsi_period: 14
  threshold: 70

market:
  timeframe: M1
  context_timeframe: M15
```

---

# 36. LOGS

Utilizar logs estruturados.

Exemplo:

```text
INFO  DATA_CONNECTED
INFO  CANDLE_RECEIVED
INFO  INDICATORS_UPDATED
INFO  REGIME_CHANGED
INFO  SIGNAL_GENERATED
INFO  PAPER_TRADE_CREATED
INFO  PAPER_TRADE_CLOSED
ERROR DATA_PROVIDER_ERROR
WARNING DATA_GAP_DETECTED
```

---

# 37. MONITORAMENTO

Criar health checks:

```text
/api/system/health
/api/system/database
/api/system/data-provider
```

Resposta:

```json
{
  "status": "healthy",
  "database": true,
  "data_provider": true,
  "last_candle": "2026-08-10T08:30:00"
}
```

---

# 38. TRATAMENTO DE FALHAS

O sistema deve sobreviver a:

* queda de internet;
* provider indisponível;
* candle duplicado;
* candle fora de ordem;
* candle faltando;
* banco indisponível;
* erro de indicador;
* estratégia lançando exceção.

Uma falha em uma estratégia não pode derrubar todo o sistema.

---

# 39. TESTES

Cobertura mínima:

## Unitários

* EMA;
* RSI;
* MACD;
* Bollinger;
* ATR;
* detecção de swing;
* suporte/resistência;
* regime.

## Estratégias

Para cada estratégia:

```text
entrada válida
entrada inválida
dados insuficientes
dados faltantes
mudança de regime
```

## Backtest

Testar:

* ausência de look-ahead;
* ordenação temporal;
* candles duplicados;
* candles faltantes;
* resultado reproduzível.

## Integração

Testar:

```text
provider → normalizer → database
database → indicators
indicators → strategy
strategy → backtest
```

---

# 40. SEGURANÇA

Nunca colocar credenciais no código.

Utilizar:

```text
.env
```

Adicionar:

```text
.env
```

ao `.gitignore`.

Criar:

```text
.env.example
```

sem credenciais reais.

---

# 41. DOCKER

Serviços:

```text
backend
frontend
postgres
```

Opcional:

```text
redis
```

Estrutura:

```text
docker compose up -d
```

deve iniciar o ambiente.

---

# 42. API

Endpoints mínimos:

```text
GET /api/system/health

GET /api/assets

GET /api/candles

GET /api/strategies

POST /api/backtests

GET /api/backtests

GET /api/backtests/{id}

GET /api/signals

GET /api/paper-trades

GET /api/performance

GET /api/performance/by-asset

GET /api/performance/by-strategy

GET /api/performance/by-regime
```

---

# 43. REGISTRO DE ESTRATÉGIAS

Criar registry.

Exemplo:

```python
StrategyRegistry.register(TrendFollowing())
StrategyRegistry.register(Pullback())
StrategyRegistry.register(Breakout())
StrategyRegistry.register(MeanReversion())
StrategyRegistry.register(PriceAction())
StrategyRegistry.register(Divergence())
```

O sistema deve descobrir estratégias automaticamente.

Adicionar nova estratégia não deve exigir alterações no backtester.

---

# 44. PLUGIN ARCHITECTURE

A arquitetura deve permitir futuramente:

```text
Data Provider
      ↓
Strategy
      ↓
Execution Adapter
```

Os módulos devem ser independentes.

Por exemplo:

```text
IQ Option
Provider A
CSV
Parquet
API externa
```

podem alimentar o mesmo motor.

---

# 45. REQUISITO IMPORTANTE — DADOS

Nunca misturar:

```text
dados de treinamento
```

com:

```text
dados de teste
```

O sistema deve identificar claramente:

```text
TRAIN
VALIDATION
TEST
LIVE/PAPER
```

---

# 46. REPRODUTIBILIDADE

Todo backtest deve gerar um identificador.

Exemplo:

```text
BACKTEST-20260810-001
```

Salvar:

```text
estratégia
versão
parâmetros
dataset
período
resultado
timestamp
```

Assim o mesmo backtest pode ser reproduzido posteriormente.

---

# 47. VERSIONAMENTO DA ESTRATÉGIA

Cada estratégia deve possuir:

```text
name
version
parameters
```

Exemplo:

```text
Pullback v1.0
Pullback v1.1
Pullback v2.0
```

Não sobrescrever resultados antigos.

---

# 48. FLUXO COMPLETO

```text
1. Provider fornece candle

2. Normalizer valida candle

3. Banco armazena candle

4. Indicator Engine calcula indicadores

5. Market Regime classifica ambiente

6. Strategy Engine analisa contexto

7. Signal Engine gera sinal hipotético

8. Signal é armazenado

9. Backtest/Paper Engine processa sinal

10. Performance Engine calcula resultado

11. Dashboard apresenta dados

12. Sistema registra logs
```

---

# 49. ORDEM DE DESENVOLVIMENTO

Não desenvolver tudo simultaneamente.

## FASE 1

Infraestrutura.

Criar:

* backend;
* frontend;
* PostgreSQL;
* Docker;
* configuração;
* logging;
* health check.

---

## FASE 2

Data Engine.

Implementar:

* provider;
* normalização;
* candles;
* armazenamento;
* validação;
* recuperação histórica.

Não avançar até os dados estarem confiáveis.

---

## FASE 3

Indicators Engine.

Implementar:

* EMA;
* SMA;
* RSI;
* MACD;
* Bollinger;
* ATR;
* Stochastic;
* CCI.

Criar testes.

---

## FASE 4

Market Structure.

Implementar:

* swing highs;
* swing lows;
* suporte;
* resistência;
* tendência;
* volatilidade;
* regime.

---

## FASE 5

Strategy Engine.

Implementar inicialmente:

1. Trend Following
2. Pullback
3. Breakout
4. Mean Reversion
5. Price Action
6. Divergence

---

## FASE 6

Backtest.

Implementar:

* engine;
* simulator;
* métricas;
* equity curve;
* drawdown;
* walk-forward;
* out-of-sample.

---

## FASE 7

Paper Trading.

Executar sinais em tempo real sem operações reais.

---

## FASE 8

Dashboard.

Criar:

* visão geral;
* estratégias;
* backtests;
* sinais;
* paper trading;
* performance.

---

## FASE 9

Robustez.

Testar:

* queda de conexão;
* dados inválidos;
* dados faltantes;
* reinicialização;
* banco indisponível;
* provider indisponível;
* múltiplas estratégias simultâneas.

---

# 50. CRITÉRIOS DE ACEITAÇÃO

O projeto somente deve ser considerado pronto quando:

### Dados

* [ ] candles não duplicam;
* [ ] candles possuem timestamp correto;
* [ ] gaps são detectados;
* [ ] dados podem ser reproduzidos.

### Indicadores

* [ ] todos possuem testes;
* [ ] resultados são determinísticos.

### Estratégias

* [ ] todas possuem interface comum;
* [ ] parâmetros são configuráveis;
* [ ] não utilizam dados futuros.

### Backtest

* [ ] não existe look-ahead;
* [ ] resultados são reproduzíveis;
* [ ] métricas são calculadas;
* [ ] walk-forward funciona;
* [ ] out-of-sample funciona.

### Paper Trading

* [ ] sinais são registrados;
* [ ] resultados são simulados;
* [ ] nenhuma operação real é enviada.

### Dashboard

* [ ] estratégias aparecem;
* [ ] backtests podem ser executados;
* [ ] resultados podem ser comparados;
* [ ] sinais podem ser consultados.

---

# 51. O QUE NÃO FAZER

Não implementar:

* martingale;
* recuperação automática de perdas;
* promessa de percentual de acerto;
* estratégia baseada em um único indicador;
* parâmetros hardcoded;
* utilização de dados futuros;
* otimização somente pelo maior win rate;
* operação real durante a fase de desenvolvimento;
* mecanismos para burlar limitações ou detecção da plataforma.

---

# 52. PRINCIPAL OBJETIVO DO PROJETO

O resultado final esperado não é simplesmente:

> "um bot que faz operações."

O resultado esperado é:

> "um laboratório capaz de descobrir, testar e validar sistematicamente hipóteses de estratégias de mercado."

A arquitetura deve permitir adicionar uma nova estratégia em poucos minutos.

Exemplo:

```text
strategies/
    nova_estrategia.py
```

A nova estratégia deve automaticamente poder ser utilizada pelo:

```text
Backtest
Paper Trading
Dashboard
Performance Engine
```

sem precisar reescrever esses módulos.

---

# 53. FUTURA CAMADA DE EXECUÇÃO

A arquitetura pode deixar uma abstração preparada:

```text
Strategy
   ↓
Signal
   ↓
Risk/Validation
   ↓
Execution Adapter
```

Porém, durante este projeto, o adapter deve permanecer em modo simulado.

Exemplo:

```text
PaperExecutionAdapter
```

A existência de uma camada abstrata permitirá futuramente estudar integrações compatíveis sem acoplar o núcleo do sistema a uma plataforma específica.

---

# 54. INSTRUÇÃO FINAL PARA O DESENVOLVEDOR

Reconstrua o projeto seguindo esta documentação.

Não tente criar tudo em um único arquivo.

Não comece pela estratégia.

Primeiro garanta:

```text
INFRAESTRUTURA
↓
DADOS
↓
INDICADORES
↓
MARKET REGIME
↓
ESTRATÉGIAS
↓
BACKTEST
↓
PAPER TRADING
↓
DASHBOARD
```

Cada fase deve possuir testes antes da próxima fase.

Sempre que uma decisão de arquitetura for necessária, priorizar:

1. confiabilidade;
2. testabilidade;
3. separação de responsabilidades;
4. reprodutibilidade;
5. observabilidade;
6. facilidade de adicionar novas estratégias.

O sistema deve ser construído como um produto de pesquisa quantitativa, e não como um script de trading.

# FIM DA ESPECIFICAÇÃO

