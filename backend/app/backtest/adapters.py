"""
Adapters finos entre o Backtest Engine (pacote entregue, seções 1-31) e os
serviços reais deste repositório (Sprints 2 e 5). Nenhuma lógica do engine é
alterada aqui — só tradução de tipos e composição das chamadas causais que
`BacktestEngine`/`BacktestRunner` já fazem.

Ver INTEGRACAO_CLAUDE_CODE.md, passo 3 e a seção "Regras que não podem ser
violadas na integração".
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Sequence

from app.data.types import Candle as DomainCandle
from app.data.types import Timeframe
from app.indicators.registry import IndicatorRegistry, result_key
from app.market.snapshot import build_snapshot
from app.repositories.candle_repository import CandleRepository as RealCandleRepository
from app.strategies.base import Strategy
from app.strategies.context import StrategyContext


class CandleRepositoryAdapter:
    """Satisfaz o Protocol `CandleRepository` de `runner.py` usando o
    repositório real do Data Engine (Sprint 2).

    Devolve os candles de domínio (`app.data.types.Candle`) sem conversão de
    tipo. `get_domain` já filtra por `timestamp BETWEEN start AND end` no SQL,
    então nunca vaza nada além do período pedido (seção 24 da spec original;
    ver INTEGRACAO_CLAUDE_CODE.md "Período").

    Decisão deliberada: NÃO converter os preços `Decimal` para `float` aqui.
    Esses mesmos candles são passados por `StrategyEvaluatorAdapter` para
    `build_snapshot`/`IndicatorRegistry` (Sprints 3-4), que assumem preços
    `Decimal` em alguns pontos (ex.: `support_resistance._build_zone` soma com
    `Decimal(0)`) — convertê-los para float aqui quebraria esse código com
    `TypeError: unsupported operand type(s) for +: 'decimal.Decimal' and
    'float'` (erro real, encontrado durante o smoke run desta integração). O
    próprio Backtest Engine (outcome.py/simulator.py) só compara entry_price
    com exit_price entre si — nunca mistura com float — então Decimal
    funciona sem alteração nenhuma no engine.
    """

    def __init__(self, repository: RealCandleRepository):
        self._repository = repository

    def get_candles(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> Sequence[DomainCandle]:
        tf = Timeframe(timeframe)
        return self._repository.get_domain(symbol, tf, start, end)


class _SignalWithRegime:
    """Wrapper fino em volta de um `Signal` real (Sprint 5, frozen dataclass).

    Duas divergências de forma entre o `Signal` real e o que `engine.py` (um
    dos 13 módulos entregues, não modificado) espera — ambas encontradas
    quebrando o smoke run desta integração:

    1. Regime: `_extract_regime` tenta `signal.regime`, depois
       `signal.conditions.get("regime")`. Nosso Signal não tem `.regime` e
       usa `conditions: list[str]` (não dict) — a segunda tentativa quebrava
       com `AttributeError: 'list' object has no attribute 'get'`, e mesmo
       sem quebrar o resultado seria sempre UNKNOWN, esvaziando o bucket
       `by_regime` das métricas.

    2. Conditions: `TradeRecord.conditions` é montado com
       `dict(signal.conditions)`, que exige pares (chave, valor) — uma lista
       de strings (`["regime_compatible", ...]`) quebra com
       `ValueError: dictionary update sequence element #0 has length 17; 2 is
       required`.

    Em vez de alterar `engine.py`, expomos `.regime` (vindo do MarketSnapshot
    já calculado por este adapter) e reescrevemos `.conditions` como
    `{nome_da_condição: True}` — a lista real já é "as condições que foram
    satisfeitas", então virar um dict de flags é uma tradução fiel, não uma
    invenção de dado. Todo o resto delega para o Signal real.
    """

    def __init__(self, signal: Any, regime: Any):
        object.__setattr__(self, "_signal", signal)
        object.__setattr__(self, "regime", regime)
        object.__setattr__(self, "conditions", {name: True for name in (signal.conditions or [])})

    def __getattr__(self, name: str) -> Any:
        return getattr(self._signal, name)


class StrategyEvaluatorAdapter:
    """Satisfaz o Protocol `StrategyService` de `engine.py`
    (`evaluate(candles, parameters) -> Signal | None`) usando uma `Strategy`
    real do Strategy Engine (Sprint 5).

    Uma instância desta classe está sempre ligada a UMA estratégia já
    configurada (via `StrategyRegistry.create(nome, **parametros)`) — o
    `BacktestRunner` nunca escolhe a estratégia por chamada, então o
    `parameters` recebido em `evaluate()` é ignorado aqui (os parâmetros já
    foram aplicados na construção da `Strategy`).

    Ponto crítico de causalidade: `candles` é exatamente `candles[:i+1]` que o
    `BacktestEngine` já recortou antes de chamar `evaluate()`. Este adapter
    NUNCA busca dados adicionais (nem do banco, nem de mais candles) — o
    `MarketSnapshot` e os indicadores são recalculados do zero a cada chamada,
    só com o que foi passado. Buscar mais candles aqui reintroduziria
    vazamento de futuro, exatamente o que a spec original proíbe.
    """

    def __init__(self, strategy: Strategy, symbol: str, timeframe: str):
        self._strategy = strategy
        self._symbol = symbol
        self._timeframe = Timeframe(timeframe)

    def evaluate(self, candles: Sequence[Any], parameters: dict) -> Optional[Any]:
        if not candles:
            return None

        candles = list(candles)
        snapshot = build_snapshot(candles, symbol=self._symbol, timeframe=self._timeframe)

        indicators = {}
        for spec in self._strategy.required_indicators():
            indicator = IndicatorRegistry.create(spec.name, **spec.parameters)
            result = indicator.calculate(candles)
            indicators[result_key(result)] = result

        context = StrategyContext(
            symbol=self._symbol,
            timeframe=self._timeframe,
            timestamp=candles[-1].timestamp,
            market_snapshot=snapshot,
            candles=candles,
            indicators=indicators,
        )

        evaluation = self._strategy.evaluate(context)
        if evaluation.signal is None:
            return None
        return _SignalWithRegime(evaluation.signal, snapshot.regime)
