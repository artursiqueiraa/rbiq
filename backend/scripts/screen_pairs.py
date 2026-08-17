"""
screen_pairs.py — varre os pares REALMENTE abertos agora na IQ Option
(`IQOptionGateway.list_open_symbols`), testa cada estratégia do Strategy
Engine (Sprint 5) contra cada um via Backtest Engine (Sprint 6) contra
candles reais, e mostra um ranking: melhor combinação par+estratégia por
taxa de acerto MEDIDA — não a pontuação de confiança em tempo real
(`min_confidence`), que só filtra entradas, nunca mede histórico.

Pode demorar minutos: cada combinação (par x estratégia) é um backtest real
contra candles reais buscados da IQ Option, um por par (reaproveitado entre
todas as estratégias testadas nesse par). Ctrl+C a qualquer momento mostra
o ranking parcial já calculado até ali, em vez de perder tudo.

Interativo, mesmo padrão de segurança dos outros scripts: credenciais só na
sessão, nunca em `.env`/argumento de linha de comando. Só lê dados — nunca
coloca ordem nenhuma, real ou demo.

Uso (a partir de backend/, com o ambiente uv já sincronizado):
    uv run python scripts/screen_pairs.py
"""

from __future__ import annotations

import getpass
import sys

sys.path.insert(0, ".")

from app.execution.broker import BrokerConnectionError
from app.execution.config import Credentials
from app.execution.iqoption import IQOptionGateway, TwoFactorAuthRequired
from app.execution.types import InstrumentType
from app.strategies.registry import StrategyRegistry
from scripts._cli_helpers import ask, ask_float, ask_int, safe_print
from scripts._screen import rank_by_expectancy, scan_pairs


def main() -> None:
    safe_print("=== IQO Strategy Lab — screener de paridades e estratégias ===\n")
    safe_print("Suas credenciais NÃO são salvas em disco — só usadas nesta sessão.\n")

    email = ask("Email IQ Option")
    password = getpass.getpass("Senha IQ Option (não aparece na tela): ")
    if not email or not password:
        sys.exit("Email e senha são obrigatórios.")

    safe_print("\nConectando...")
    gateway = IQOptionGateway(Credentials(email=email, password=password), practice_by_default=True)
    try:
        gateway.connect()
    except TwoFactorAuthRequired as exc:
        sys.exit(f"Conta exige 2FA — resolva fora deste fluxo antes de operar.\n{exc}")
    except BrokerConnectionError as exc:
        sys.exit(f"Falha ao conectar: {exc}")
    safe_print(f"Conectado. Conta: {gateway.current_account_type().value}\n")

    safe_print("Buscando paridades abertas agora...")
    try:
        open_symbols = gateway.list_open_symbols(InstrumentType.BINARY)
    except BrokerConnectionError as exc:
        sys.exit(f"Falha ao listar paridades: {exc}")
    if not open_symbols:
        sys.exit("Nenhuma paridade aberta encontrada agora.")
    safe_print(f"{len(open_symbols)} paridades abertas agora (ordenadas por payout, maior primeiro).\n")

    top_n = ask_int(f"Quantas das top paridades por payout varrer (disponíveis: {len(open_symbols)})", 15)
    top_n = max(1, min(top_n, len(open_symbols)))
    candidates = open_symbols[:top_n]

    all_strategy_names = StrategyRegistry.names()
    safe_print("\nEstratégias disponíveis: " + ", ".join(all_strategy_names))
    strategies_raw = ask("Quais testar (Enter = todas, ou separadas por vírgula)", "")
    if strategies_raw:
        strategy_names = [s.strip() for s in strategies_raw.split(",") if s.strip()]
        unknown = [s for s in strategy_names if s not in all_strategy_names]
        if unknown:
            sys.exit(f"Estratégia(s) desconhecida(s): {unknown}")
    else:
        strategy_names = all_strategy_names

    min_confidence = ask_float("Confiança mínima para entrar em cada estratégia (0.0 a 1.0)", 0.75)
    min_confidence = min(max(min_confidence, 0.0), 1.0)

    candle_count = ask_int("Quantos candles M1 de histórico por paridade (máx. ~1000; mais = mais lento)", 500)
    min_trades = ask_int("Mínimo de trades para um resultado contar (filtra amostras pequenas demais)", 10)

    total_runs = len(candidates) * len(strategy_names)
    safe_print(
        f"\nVai rodar {len(candidates)} paridades x {len(strategy_names)} estratégias = "
        f"{total_runs} backtests. Pode levar alguns minutos — Ctrl+C a qualquer momento "
        "mostra o ranking parcial já calculado até ali, não perde o que já rodou.\n"
    )

    results = scan_pairs(gateway, strategy_names, candidates, min_confidence, candle_count)
    significant = rank_by_expectancy(results, min_trades)

    safe_print(f"\n=== RANKING (ordenado por expectancy, mínimo de {min_trades} trades) ===\n")
    if not significant:
        safe_print(
            f"Nenhuma combinação teve pelo menos {min_trades} trades — histórico curto demais "
            "ou estratégias pouco seletivas para esse escopo. Tente mais candles por paridade, "
            "menos paridades, ou um min_confidence menor."
        )
    else:
        for rank, r in enumerate(significant[:10], start=1):
            safe_print(f"{rank:2d}. {r.line()}")

    safe_print(
        "\nATENÇÃO: cada resultado é uma medição sobre um recorte curto e recente de histórico "
        "— NÃO é uma afirmação de que a combinação é lucrativa, nem uma previsão do que vai "
        "acontecer ao vivo. Mercado passado não garante mercado futuro. Trate como um ponto de "
        "partida para investigar mais, não como uma garantia."
    )


if __name__ == "__main__":
    main()
