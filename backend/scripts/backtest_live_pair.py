"""
backtest_live_pair.py — puxa histórico REAL da IQ Option para um par e roda
o Backtest Engine (Sprint 6) contra ele, causal e determinístico, ANTES de
arriscar dinheiro ao vivo nesse par/estratégia com `run_live_bot.py`.

Motivação: `min_confidence` (Strategy Engine) é uma pontuação baseada em
regras, não uma taxa de acerto medida. Isto aqui É uma medição — contra
dados reais desse par específico, não uma amostra genérica.

Interativo, mesmo padrão de segurança de `run_live_bot.py`: credenciais só
na sessão, nunca em `.env`/argumento de linha de comando. Só lê dados
(candles + payout) — nunca coloca ordem nenhuma, real ou demo.

Limitação conhecida: uma única chamada de `get_candles` devolve no máximo
~1000 candles (confirmado na fork instalada) — em M1, isso é ~16h de
histórico. Para mais que isso seria necessário paginar com `endtime`
decrescente, não implementado aqui.

Uso (a partir de backend/, com o ambiente uv já sincronizado):
    uv run python scripts/backtest_live_pair.py
"""

from __future__ import annotations

import getpass
import sys

sys.path.insert(0, ".")

from app.backtest import BacktestConfig, BacktestRunner, StrategyEvaluatorAdapter, summary_text
from app.data.types import Timeframe
from app.execution.broker import BrokerConnectionError
from app.execution.config import Credentials
from app.execution.iqoption import IQOptionGateway, TwoFactorAuthRequired
from app.strategies.registry import StrategyRegistry
from scripts._backtest_repo import InMemoryCandleRepository
from scripts._cli_helpers import ask, ask_float, ask_int, safe_print


def main() -> None:
    safe_print("=== IQO Strategy Lab — backtest de checagem contra histórico real ===\n")
    safe_print("Suas credenciais NÃO são salvas em disco — só usadas nesta sessão.\n")

    email = ask("Email IQ Option")
    password = getpass.getpass("Senha IQ Option (não aparece na tela): ")
    if not email or not password:
        sys.exit("Email e senha são obrigatórios.")

    safe_print("\nEstratégias disponíveis: " + ", ".join(StrategyRegistry.names()))
    strategy_name = ask("Estratégia", StrategyRegistry.names()[0])

    min_confidence = ask_float("Confiança mínima para entrar (0.0 a 1.0)", 0.75)
    min_confidence = min(max(min_confidence, 0.0), 1.0)

    try:
        StrategyRegistry.create(strategy_name, min_confidence=min_confidence)  # só valida
    except ValueError as exc:
        sys.exit(str(exc))

    symbol = ask("Paridade (ex.: USDCAD-OTC)").strip().upper()
    if not symbol:
        sys.exit("Informe uma paridade.")

    candle_count = ask_int("Quantos candles M1 de histórico buscar (máx. ~1000 por chamada)", 1000)
    stake = ask_float("Stake por ordem simulada", 1.0)
    expiry_candles = ask_int("Expiração em candles (1 = fecha no candle seguinte)", 1)

    safe_print("\nConectando...")
    gateway = IQOptionGateway(Credentials(email=email, password=password), practice_by_default=True)
    try:
        gateway.connect()
    except TwoFactorAuthRequired as exc:
        sys.exit(f"Conta exige 2FA — resolva fora deste fluxo antes de operar.\n{exc}")
    except BrokerConnectionError as exc:
        sys.exit(f"Falha ao conectar: {exc}")
    safe_print(f"Conectado. Conta: {gateway.current_account_type().value}\n")

    safe_print(f"Buscando até {candle_count} candles M1 de {symbol}...")
    try:
        candles = list(gateway.get_recent_candles(symbol, Timeframe.M1, candle_count))
    except BrokerConnectionError as exc:
        sys.exit(f"Falha ao buscar candles: {exc}")

    if len(candles) < 50:
        sys.exit(
            f"Só {len(candles)} candles disponíveis para {symbol} — insuficiente para um backtest "
            "que signifique alguma coisa. Confira se o símbolo está correto (sufixo -OTC?)."
        )
    safe_print(f"{len(candles)} candles obtidos: {candles[0].timestamp} até {candles[-1].timestamp}\n")

    payout = gateway.get_payout(symbol)
    if payout is None:
        safe_print(f"Não consegui o payout real de {symbol} — usando 0.80 como aproximação.")
        payout = 0.80
    else:
        safe_print(f"Payout real de {symbol}: {payout:.0%}")

    repository = InMemoryCandleRepository(candles)
    strategy = StrategyRegistry.create(strategy_name, min_confidence=min_confidence)
    strategy_service = StrategyEvaluatorAdapter(strategy, symbol, "M1")

    config = BacktestConfig(
        symbol=symbol,
        timeframe="M1",
        start=candles[0].timestamp,
        end=candles[-1].timestamp,
        strategy=strategy_name,
        initial_balance=1000.0,
        stake=stake,
        payout=payout,
        expiry_candles=expiry_candles,
    )

    safe_print("\nRodando backtest (causal, determinístico)...\n")
    runner = BacktestRunner(repository, strategy_service)
    result = runner.run(config)

    safe_print(summary_text(result))
    safe_print(
        "\nATENÇÃO: isto é uma medição sobre um recorte curto e recente de histórico "
        f"(~{len(candles)} candles M1, ≈{len(candles) / 60:.1f}h) — NÃO é uma afirmação de que "
        "a estratégia é lucrativa, nem uma previsão do que vai acontecer ao vivo. Mercado passado "
        "não garante mercado futuro. Trate como um filtro de sanidade antes de operar ao vivo, "
        "não como uma garantia."
    )


if __name__ == "__main__":
    main()
