"""
verify_iqoption.py — verificação da IQ Option em conta DEMO (PRACTICE), via
o próprio `IQOptionGateway` de produção (app/execution/iqoption.py).

Ao contrário de uma versão anterior deste script (que chamava a lib
`iqoptionapi` diretamente), este roda através do gateway real — o mesmo
código que o `LiveExecutor` usaria — para que a validação manual cubra o
caminho de verdade, incluindo as proteções já aprendidas na prática:

  - `_call_with_timeout`: `buy_digital_spot()` e `check_win_digital_v2()`
    têm busy-waits internos SEM timeout no fork instalado (confirmado:
    travou 85s+ contra uma conta real) — sem essa proteção, este script
    travaria indefinidamente com `--probe-order --instrument digital`.
  - roteamento correto de resultado por instrumento: `await_result` só
    resolve digital via `check_win_digital_v2` (não `check_win_v4`, que é
    só para binário) — sem isso, uma ordem digital nunca resolveria.
  - `IQOptionGateway.connect()` nunca imprime perfil/KYC/token — só
    conecta e lê saldo.

O que este script faz, em ordem:
  1. credenciais vêm do AMBIENTE (`Credentials.from_env()`, nunca do código)
  2. conecta (2FA vira erro explícito, nunca é resolvido automaticamente)
  3. confirma conta PRACTICE e lê saldo (resumo redigido, sem PII)
  4. (só com --probe-order) coloca UMA ordem demo mínima via
     `IQOptionGateway.place_order` + `await_result`, e imprime o resultado

Uso (a partir de backend/, com o ambiente uv já sincronizado):
    export IQOPTION_EMAIL="seu_email"
    export IQOPTION_PASSWORD="sua_senha"

    uv run python scripts/verify_iqoption.py                                  # read-only
    uv run python scripts/verify_iqoption.py --probe-order                    # 1 ordem digital demo
    uv run python scripts/verify_iqoption.py --probe-order --instrument binary --symbol EURUSD

NUNCA rode isto apontando para conta REAL. É ferramenta de validação em demo
— `account_type` fica em PRACTICE em todo o script, sem exceção.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")  # permite `uv run python scripts/verify_iqoption.py` a partir de backend/

from app.execution.broker import BrokerConnectionError, BrokerRejectionError
from app.execution.config import Credentials
from app.execution.iqoption import IQOptionGateway, TwoFactorAuthRequired
from app.execution.types import AccountType, ExecutionStatus, InstrumentType, OrderDirection, OrderRequest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--probe-order", action="store_true",
        help="coloca UMA ordem demo mínima e aguarda a resolução",
    )
    parser.add_argument("--symbol", default="BTCUSD")
    parser.add_argument("--amount", type=float, default=1.0)
    parser.add_argument("--duration", type=int, default=1, help="minutos")
    parser.add_argument("--action", default="call", choices=["call", "put"])
    parser.add_argument(
        "--instrument", choices=["binary", "digital"], default="digital",
        help="default digital: contas recentes costumam recusar binário clássico "
             "('the asset is not available at the moment')",
    )
    args = parser.parse_args()

    try:
        credentials = Credentials.from_env()
    except RuntimeError as exc:
        sys.exit(str(exc))

    gateway = IQOptionGateway(credentials, practice_by_default=True)

    print("== 1. conectando ==")
    try:
        gateway.connect()
    except TwoFactorAuthRequired as exc:
        sys.exit(f"Conta exige 2FA — resolva fora do fluxo automático antes de operar.\n{exc}")
    except BrokerConnectionError as exc:
        sys.exit(f"Falha ao conectar: {exc}")
    print("conectado.")

    print("\n== 2. conta PRACTICE + saldo (redigido, sem perfil/KYC/token) ==")
    account_type = gateway.current_account_type()
    if account_type is not AccountType.PRACTICE:
        sys.exit(f"ERRO: gateway não está em PRACTICE (está em {account_type.value}); abortando.")
    balance_before = gateway.get_balance()
    print(f"conta ativa: {account_type.value} | saldo demo: {balance_before:.2f}")

    if not args.probe_order:
        print("\nOK (read-only). Rode com --probe-order para ver uma ordem no gráfico.")
        return

    instrument = InstrumentType.DIGITAL if args.instrument == "digital" else InstrumentType.BINARY
    direction = OrderDirection.CALL if args.action == "call" else OrderDirection.PUT

    request = OrderRequest(
        symbol=args.symbol,
        direction=direction,
        stake=args.amount,
        expiry_minutes=args.duration,
        instrument=instrument,
        account_type=AccountType.PRACTICE,
        signal_timestamp=datetime.now(timezone.utc),
    )

    print(f"\n== 3. ordem DEMO — instrumento={instrument.value}, {args.symbol} "
          f"{direction.value} — olhe a plataforma agora ==")
    try:
        broker_order_id = gateway.place_order(request)
    except BrokerRejectionError as exc:
        sys.exit(f"Corretora rejeitou a ordem demo: {exc}\n"
                 f"(confira se {args.symbol} está aberto agora e disponível como {instrument.value})")
    except BrokerConnectionError as exc:
        sys.exit(f"Chamada à corretora falhou/travou: {exc}")

    print(f"ordem ENVIADA (broker_order_id={broker_order_id!r}) — deve aparecer no gráfico. "
          "aguardando expiração...")

    poll_timeout_s = args.duration * 60 + 60
    result = gateway.await_result(broker_order_id, poll_interval_s=1.0, poll_timeout_s=poll_timeout_s)

    if result.status is ExecutionStatus.ERROR:
        print(f"\nNÃO RESOLVIDO dentro de {poll_timeout_s}s: {result.error}")
    else:
        print(f"\nRESOLVIDO -> status={result.status.value} profit={result.profit}")
        print("  ATENÇÃO: confira se esse 'profit' inclui ou não o stake — "
              "isso muda a reconciliação com o backtest (seção 23 da Sprint 6).")

    balance_after = gateway.get_balance()
    print(f"\nsaldo demo: antes={balance_before:.2f} depois={balance_after:.2f} "
          f"(delta={balance_after - balance_before:+.2f})")


if __name__ == "__main__":
    main()
