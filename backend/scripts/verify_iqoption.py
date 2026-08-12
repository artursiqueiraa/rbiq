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
    parser.add_argument(
        "--instrument", choices=["binary", "digital"], default="binary",
        help="binary usa buy() (opção clássica); digital usa buy_digital_spot() "
             "(pode ser a única disponível — IQ Option vem descontinuando binário "
             "clássico em várias contas/regiões)",
    )
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

    # get_currency() é só um código (ex.: "USD") — seguro imprimir inteiro.
    currency_fn = getattr(api, "get_currency", None)
    if callable(currency_fn):
        try:
            print(f"  get_currency() -> {currency_fn()}")
        except Exception as e:
            print(f"  get_currency() falhou: {e}")

    # get_balances()/get_profile_ansyc() devolvem o perfil bruto da conta:
    # nome, endereço, telefone, data de nascimento, KYC, e um campo "skey"
    # que parece um token de sessão. NUNCA imprimir esse payload inteiro —
    # só um resumo redigido (saldo por moeda/tipo), sem PII nem tokens.
    balances_fn = getattr(api, "get_balances", None)
    if callable(balances_fn):
        try:
            balances = balances_fn().get("msg", [])
            print("  saldos por moeda (resumo redigido):")
            for b in balances:
                print(f"    id={b.get('id')} type={b.get('type')} "
                      f"currency={b.get('currency')} amount={b.get('amount')}")
        except Exception as e:
            print(f"  get_balances() falhou: {e}")

    if not args.probe_order:
        print("\nOK. Conexão + conta demo + saldo confirmados (read-only).")
        print("Rode com --probe-order para inspecionar o retorno de uma ordem demo.")
        return

    print(f"\n== 3. ordem DEMO mínima, instrumento={args.instrument} (dinheiro fake) ==")

    if args.instrument == "digital":
        print(f"buy_digital_spot(active={args.symbol!r}, amount={args.amount}, "
              f"action='call', duration={args.duration})")
        # VERIFICAR: no fork instalado, buy_digital_spot() faz um busy-wait
        # (`while ...: pass`) SEM timeout próprio enquanto aguarda o id da
        # ordem — se a corretora nunca confirmar (ex.: ativo fechado), essa
        # chamada pode travar indefinidamente, ANTES de qualquer lógica de
        # await_result/poll_timeout_s do nosso lado sequer começar. Isso é
        # uma limitação real do fork, não do nosso adapter — documentar como
        # achado conhecido antes de confiar nisso em produção.
        ok, order_id = api.buy_digital_spot(args.symbol, args.amount, "call", args.duration)
    else:
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
            if args.instrument == "digital":
                # VERIFICAR: método/retorno específico de opção digital
                result, profit = api.check_win_digital_v2(int(order_id))
            else:
                # VERIFICAR: método/retorno de resultado no seu fork
                result, profit = api.check_win_v4(int(order_id))
        except Exception as e:
            print(f"  check_win indisponível/erro: {e} — tentando check_win_v3")
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
