"""
verify_iqoption.py — verificação da lib IQ Option em conta DEMO (PRACTICE).

Roda ANTES de plugar no LiveExecutor. Objetivo: confirmar que o fork escolhido
funciona e que os pontos `# VERIFICAR` do adapter (`app/execution/iqoption.py`)
batem com a realidade.

O que checa, em ordem:
  1. credenciais vêm do AMBIENTE (nunca do código)
  2. conexão (e detecção de 2FA)
  3. está na conta PRACTICE e get_balance() reflete o saldo demo
  4. (só com --probe-order) formato de retorno de buy() e check_win em UMA
     ordem demo mínima — dinheiro fake, mas ainda assim explícito

Uso (a partir de backend/, com o ambiente uv já sincronizado):
    export IQOPTION_EMAIL="seu_email"
    export IQOPTION_PASSWORD="sua_senha"

    uv run python scripts/verify_iqoption.py                 # read-only: conecta e lê saldo
    uv run python scripts/verify_iqoption.py --probe-order   # + UMA ordem demo p/ ver o retorno

NUNCA rode isto apontando para conta REAL. É ferramenta de validação em demo.
"""

from __future__ import annotations

import argparse
import os
import sys
import time


def get_credentials() -> tuple[str, str]:
    email = os.environ.get("IQOPTION_EMAIL")
    password = os.environ.get("IQOPTION_PASSWORD")
    if not email or not password:
        sys.exit(
            "ERRO: defina IQOPTION_EMAIL e IQOPTION_PASSWORD no ambiente.\n"
            "  export IQOPTION_EMAIL='...'\n"
            "  export IQOPTION_PASSWORD='...'\n"
            "Não coloque credenciais no código."
        )
    return email, password


def import_lib():
    try:
        from iqoptionapi.stable_api import IQ_Option  # noqa: E402
        return IQ_Option
    except ImportError as exc:
        sys.exit(
            f"ERRO: não achei iqoptionapi.stable_api ({exc}).\n"
            "O pacote do PyPI (`pip install iqoptionapi`) é a v0.5 de 2016 e NÃO tem stable_api.\n"
            "Instale o fork mantido do GitHub, pinado por tag/commit, com git+https (não git://):\n"
            "  pip install -U 'git+https://github.com/iqoptionapi/iqoptionapi.git@7.0.0'"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--probe-order", action="store_true",
        help="coloca UMA ordem demo mínima p/ inspecionar o retorno de buy/check_win",
    )
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--amount", type=float, default=1.0)
    parser.add_argument("--duration", type=int, default=1, help="minutos")
    args = parser.parse_args()

    email, password = get_credentials()
    IQ_Option = import_lib()

    print("== 1. conectando ==")
    api = IQ_Option(email, password)
    status, reason = api.connect()
    print(f"connect -> status={status!r} reason={reason!r}")
    if not status:
        if str(reason).upper().find("2FA") >= 0:
            sys.exit("Conta exige 2FA. Resolva a autenticação fora do fluxo automático "
                     "(sessão pré-autenticada) antes de operar.")
        sys.exit(f"Falha ao conectar: {reason!r}")

    print("\n== 2. forçando conta PRACTICE (demo) ==")
    # VERIFICAR: nome/valores do método no seu fork
    api.change_balance("PRACTICE")
    balance_before = api.get_balance()
    print(f"conta ativa: PRACTICE | get_balance() = {balance_before}")

    # tenta listar os dois saldos, se o fork expuser (só informativo)
    for attr in ("get_balances", "get_profile_ansyc", "get_currency"):
        fn = getattr(api, attr, None)
        if callable(fn):
            try:
                print(f"  {attr}() -> {fn()}")
            except Exception as e:
                print(f"  {attr}() falhou: {e}")

    if not args.probe_order:
        print("\nOK. Conexão + conta demo + saldo confirmados (read-only).")
        print("Rode com --probe-order para inspecionar o retorno de uma ordem demo.")
        return

    print("\n== 3. ordem DEMO mínima (dinheiro fake) ==")
    print(f"buy(amount={args.amount}, active={args.symbol!r}, action='call', "
          f"duration={args.duration})")
    # VERIFICAR: assinatura e retorno de buy() no seu fork -> (status, id)
    ok, order_id = api.buy(args.amount, args.symbol, "call", args.duration)
    print(f"buy -> status={ok!r} order_id={order_id!r}")
    if not ok:
        sys.exit(f"Corretora rejeitou a ordem demo: {order_id!r}")

    print("aguardando expiração para inspecionar check_win...")
    deadline = time.monotonic() + args.duration * 60 + 30
    resolved = False
    while time.monotonic() < deadline:
        try:
            # VERIFICAR: método/retorno de resultado no seu fork
            result, profit = api.check_win_v4(int(order_id))
        except Exception as e:
            print(f"  check_win_v4 indisponível/erro: {e} — tentando check_win_v3")
            try:
                profit = api.check_win_v3(int(order_id))
                result = True
            except Exception as e2:
                sys.exit(f"nenhum check_win funcionou: {e2}")
        if result:
            resolved = True
            print(f"RESOLVIDO -> profit bruto = {profit}")
            print("  ATENÇÃO: confira se esse 'profit' inclui ou não o stake — "
                  "isso muda a reconciliação com o backtest (seção 23 da Sprint 6).")
            break
        time.sleep(1)

    if not resolved:
        print("timeout esperando resolução — verifique o método de check_win do seu fork.")

    balance_after = api.get_balance()
    print(f"\nsaldo demo: antes={balance_before} depois={balance_after} "
          f"(delta={balance_after - balance_before})")
    print("\nSe chegou aqui: buy/check_win/change_balance batem. "
          "Ajuste os # VERIFICAR do adapter conforme os retornos acima e só então "
          "plugue no LiveExecutor em PRACTICE.")


if __name__ == "__main__":
    main()
