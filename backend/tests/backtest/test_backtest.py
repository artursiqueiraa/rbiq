"""
Suíte de testes do Backtest Engine (Sprint 6).

Cobre as regras que a spec marca como críticas: causalidade (dados <= T),
resolução WIN/LOSS/DRAW por direção, P&L, expiry T+N, saldo insuficiente,
UNRESOLVED no fim da série, gaps e falha explícita em dados inválidos.

Rodar:
    pytest tests/test_backtest.py -v
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.backtest import (
    BacktestConfig,
    BacktestDataInvalid,
    BacktestRunner,
    SignalDirection,
    SimpleCandle,
    TradeOutcome,
    compute_pl,
    resolve_outcome,
    validate_candles,
)

UTC = timezone.utc
T0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)


# --------------------------------------------------------------------- helpers
def mk(prices, start=T0, step=60):
    """Candles M1 com open=high=low=close=price (simplifica a asserção de preço)."""
    return [
        SimpleCandle(start + timedelta(seconds=i * step), p, p, p, p)
        for i, p in enumerate(prices)
    ]


class Repo:
    """CandleRepository em memória."""
    def __init__(self, candles):
        self._c = candles

    def get_candles(self, symbol, timeframe, start, end):
        return self._c


class FixedDirection:
    """StrategyService que sempre devolve a mesma direção."""
    def __init__(self, direction):
        self._d = direction
        self.seen_lengths = []

    def evaluate(self, candles, parameters):
        self.seen_lengths.append(len(candles))
        return type("S", (), {"direction": self._d})()


class NeverSignal:
    def evaluate(self, candles, parameters):
        return None


def cfg(**kw):
    base = dict(
        symbol="EURUSD", timeframe="M1", start=T0, end=T0 + timedelta(hours=1),
        strategy="test", initial_balance=1000, stake=10, payout=0.80, expiry_candles=1,
    )
    base.update(kw)
    return BacktestConfig(**base)


# ------------------------------------------------------------------- outcome/pl
@pytest.mark.parametrize("direction,entry,exit_,expected", [
    (SignalDirection.CALL, 100, 101, TradeOutcome.WIN),
    (SignalDirection.CALL, 100, 99, TradeOutcome.LOSS),
    (SignalDirection.CALL, 100, 100, TradeOutcome.DRAW),
    (SignalDirection.PUT, 100, 99, TradeOutcome.WIN),
    (SignalDirection.PUT, 100, 101, TradeOutcome.LOSS),
    (SignalDirection.PUT, 100, 100, TradeOutcome.DRAW),
])
def test_resolve_outcome(direction, entry, exit_, expected):
    assert resolve_outcome(direction, entry, exit_) is expected


def test_pl_nao_devolve_stake():
    # seção 20: vitória de stake=10 payout=0.80 => +8, nunca +18
    assert compute_pl(TradeOutcome.WIN, 10, 0.80) == 8.0
    assert compute_pl(TradeOutcome.LOSS, 10, 0.80) == -10.0
    assert compute_pl(TradeOutcome.DRAW, 10, 0.80) == 0.0


# ---------------------------------------------------------------- causalidade
def test_estrategia_nunca_ve_o_futuro():
    strat = FixedDirection("CALL")
    candles = mk([100, 101, 102, 103, 104])
    BacktestRunner(Repo(candles), strat).run(cfg())
    # a visão causal cresce 1,2,3,4,5 — se visse o futuro seria constante no total
    assert strat.seen_lengths == [1, 2, 3, 4, 5]


def test_sem_sinal_nao_gera_trade():
    res = BacktestRunner(Repo(mk([100, 101, 102])), NeverSignal()).run(cfg())
    assert res.metrics["total_trades"] == 0


# ----------------------------------------------------------------- expiry T+N
def test_entrada_close_T_saida_close_T_mais_1():
    candles = mk([100, 101, 102])
    res = BacktestRunner(Repo(candles), FixedDirection("CALL")).run(cfg(expiry_candles=1))
    t = res.trades[0]
    assert t.entry_price == 100 and t.exit_price == 101   # close(T) -> close(T+1)
    assert t.entry_timestamp == candles[0].timestamp
    assert t.expiry_timestamp == candles[1].timestamp
    assert t.outcome is TradeOutcome.WIN
    assert t.profit_loss == 8.0


def test_expiry_n3_salta_tres_candles():
    candles = mk([100, 100.5, 100.7, 105, 106])
    res = BacktestRunner(Repo(candles), FixedDirection("CALL")).run(cfg(expiry_candles=3))
    t = res.trades[0]
    assert t.entry_price == 100 and t.exit_price == 105   # T -> T+3


def test_put_em_queda_vence():
    res = BacktestRunner(Repo(mk([100, 99, 98, 97])), FixedDirection("PUT")).run(cfg())
    assert res.metrics["wins"] == res.metrics["total_trades"] >= 1


# ------------------------------------------------------------- saldo e limites
def test_saldo_insuficiente_bloqueia_operacao():
    # perde tudo até saldo < stake
    res = BacktestRunner(Repo(mk([100, 99, 98, 97, 96, 95])),
                         FixedDirection("CALL")).run(cfg(initial_balance=25, stake=10))
    reasons = [s.reason.value for s in res.skipped]
    assert "INSUFFICIENT_BALANCE" in reasons


def test_sinal_sem_candle_futuro_fica_unresolved():
    # último candle não tem T+1 para expirar
    res = BacktestRunner(Repo(mk([100, 101, 102])), FixedDirection("CALL")).run(cfg())
    assert any(s.reason.value == "UNRESOLVED" for s in res.skipped)


# ------------------------------------------------------------- qualidade dados
def test_duplicata_falha_explicitamente():
    bad = [SimpleCandle(T0, 1, 1, 1, 1), SimpleCandle(T0, 1, 1, 1, 1)]
    with pytest.raises(BacktestDataInvalid):
        validate_candles(bad, "M1")


def test_ohlc_invalido_falha():
    ohlc = [SimpleCandle(T0, 10, 5, 8, 9)]  # high < open
    with pytest.raises(BacktestDataInvalid):
        validate_candles(ohlc, "M1")


def test_timestamp_naive_falha():
    naive = [SimpleCandle(datetime(2024, 1, 1), 1, 1, 1, 1)]
    with pytest.raises(BacktestDataInvalid):
        validate_candles(naive, "M1")


def test_gap_detectado_e_bloqueia_operacao():
    gapped = [
        SimpleCandle(T0, 100, 100, 100, 100),
        SimpleCandle(T0 + timedelta(seconds=60), 101, 101, 101, 101),
        SimpleCandle(T0 + timedelta(seconds=600), 102, 102, 102, 102),  # gap
        SimpleCandle(T0 + timedelta(seconds=660), 103, 103, 103, 103),
    ]
    assert validate_candles(gapped, "M1") == {1}
    res = BacktestRunner(Repo(gapped), FixedDirection("CALL")).run(cfg())
    assert "DATA_GAP" in [s.reason.value for s in res.skipped]


# ------------------------------------------------------------------- métricas
def test_metricas_basicas_coerentes():
    res = BacktestRunner(Repo(mk([100, 101, 102, 103, 104])),
                         FixedDirection("CALL")).run(cfg())
    m = res.metrics
    assert m["wins"] + m["losses"] + m["draws"] == m["total_trades"]
    assert m["win_rate"] == 1.0            # só vitórias
    assert m["profit_factor"] is None      # seção 37: sem perdas -> None, não infinito
    assert m["profit_loss"] == pytest.approx(m["wins"] * 8.0)


def test_config_rejeita_timestamp_naive():
    with pytest.raises(ValueError):
        BacktestConfig(symbol="X", timeframe="M1",
                       start=datetime(2024, 1, 1), end=datetime(2024, 1, 2),
                       strategy="s")


def test_config_rejeita_expiry_zero():
    with pytest.raises(ValueError):
        cfg(expiry_candles=0)
