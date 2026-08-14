"""
run_live_bot.py — loop de trading ao vivo: Data (candles reais da IQ Option)
-> Strategy Engine (Sprint 5) -> Live Execution Engine (Sprint 7).

Construído sob pedido explícito do usuário, DEPOIS de `IQOptionGateway` ter
sido validado ponta a ponta contra a conta real (ver docs/sprints/
SPRINT_7_REPORT.md, seção 8.5) — antes disso, um loop automático em cima de
`place_order` só produziria ordens recusadas.

Interativo de propósito: credenciais e paridades são digitadas quando o
script abre, nunca lidas de `.env` nem passadas por argumento de linha de
comando (senha não fica em texto plano em disco nem aparece em `ps`/histórico
de shell). Só opera em conta PRACTICE — não existe caminho neste script para
ligar REAL.

`min_confidence` (perguntado na inicialização, default 0.75) é repassado à
estratégia — cada `Signal` já carrega um `confidence` (Sprint 5,
`app/strategies/base.py::decide_direction`), calculado a partir de quantas
condições técnicas da estratégia bateram; um sinal só é gerado se cruzar
esse mínimo. IMPORTANTE: isso é uma pontuação baseada em regras, não uma
taxa de acerto histórica medida — para saber a taxa de acerto real de uma
estratégia num par específico, use o Backtest Engine (Sprint 6) contra
dados históricos daquele par antes de operar ao vivo.

Uso (a partir de backend/, com o ambiente uv já sincronizado):
    uv run python scripts/run_live_bot.py

Ctrl+C encerra o loop a qualquer momento, de forma limpa.
"""

from __future__ import annotations

import getpass
import signal
import sys
import threading

sys.path.insert(0, ".")

from app.data.types import Timeframe
from app.execution.broker import BrokerConnectionError
from app.execution.config import Credentials, ExecutionConfig
from app.execution.executor import LiveExecutor
from app.execution.guard import ExecutionGuard
from app.execution.iqoption import IQOptionGateway, TwoFactorAuthRequired
from app.execution.repository import InMemoryExecutionRepository
from app.execution.types import AccountType, ExecutionStatus, InstrumentType
from app.live.loop import LiveTradingLoop
from app.strategies.registry import StrategyRegistry


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or (default or "")


def ask_float(prompt: str, default: float) -> float:
    raw = ask(prompt, str(default))
    try:
        return float(raw)
    except ValueError:
        print(f"  valor inválido, usando {default}")
        return default


def ask_int(prompt: str, default: int) -> int:
    raw = ask(prompt, str(default))
    try:
        return int(raw)
    except ValueError:
        print(f"  valor inválido, usando {default}")
        return default


class SessionStats:
    """Contagem WON/LOST/TIE acumulada da sessão. `win_rate = wins /
    (wins + losses)` — TIE fica FORA do denominador, mesma convenção já
    usada pelo Backtest Engine (Sprint 6, seção 36 do relatório) — sem
    isso, um TIE contaria como "quase perda" e distorceria a taxa."""

    def __init__(self) -> None:
        self.won = 0
        self.lost = 0
        self.tie = 0

    def record(self, status: ExecutionStatus) -> None:
        if status is ExecutionStatus.WON:
            self.won += 1
        elif status is ExecutionStatus.LOST:
            self.lost += 1
        elif status is ExecutionStatus.TIE:
            self.tie += 1

    @property
    def resolved(self) -> int:
        return self.won + self.lost + self.tie

    @property
    def win_rate(self) -> float | None:
        denom = self.won + self.lost
        return (self.won / denom) if denom else None

    def summary(self) -> str:
        rate = self.win_rate
        rate_text = f"{rate:.1%}" if rate is not None else "—"
        return f"{rate_text} de acerto ({self.won}W {self.lost}L {self.tie}T, {self.resolved} resolvidas)"


def print_signal(symbol: str, evaluation) -> None:
    # Disparado ANTES da execução — o "porquê" da entrada, não só o
    # resultado. IMPORTANTE (repetido aqui de propósito): confidence é uma
    # pontuação baseada em regras (proporção de condições técnicas que
    # bateram), não uma taxa de acerto histórica medida.
    signal = evaluation.signal
    conditions = ", ".join(signal.conditions) if signal.conditions else "(nenhuma condição nomeada)"
    print(
        f"[sinal] {symbol}: {signal.direction.value} | confiança={signal.confidence:.2f} "
        f"({signal.strength.value}) | condições satisfeitas: {conditions}"
    )


def print_record(symbol: str, record, stats: SessionStats) -> None:
    ts = record.resolved_at.strftime("%H:%M:%S") if record.resolved_at else "--:--:--"
    if record.status is ExecutionStatus.REJECTED:
        print(f"[{ts}] {symbol}: REJEITADO — {record.reject_reason}")
        return
    if record.status is ExecutionStatus.ERROR:
        print(f"[{ts}] {symbol}: ERRO — {record.error}")
        return

    direction = record.request.direction.value if record.request else "?"
    print(f"[{ts}] {symbol}: {direction} -> {record.status.value} (profit={record.profit})")
    stats.record(record.status)
    if record.status in (ExecutionStatus.WON, ExecutionStatus.LOST, ExecutionStatus.TIE):
        print(f"         taxa de acerto da sessão: {stats.summary()}")


def main() -> None:
    print("=== IQO Strategy Lab — loop de trading ao vivo (conta DEMO) ===\n")
    print("Suas credenciais NÃO são salvas em disco — só usadas nesta sessão.\n")

    email = ask("Email IQ Option")
    password = getpass.getpass("Senha IQ Option (não aparece na tela): ")
    if not email or not password:
        sys.exit("Email e senha são obrigatórios.")

    print("\nEstratégias disponíveis:", ", ".join(StrategyRegistry.names()))
    strategy_name = ask("Estratégia", StrategyRegistry.names()[0])

    min_confidence = ask_float(
        "Confiança mínima para entrar (0.0 a 1.0 — mais alto = mais seletivo, menos entradas)", 0.75
    )
    min_confidence = min(max(min_confidence, 0.0), 1.0)  # nunca fora de [0, 1]

    try:
        StrategyRegistry.create(strategy_name, min_confidence=min_confidence)  # só valida os parâmetros
    except ValueError as exc:
        sys.exit(str(exc))

    symbols_raw = ask("Paridades a operar, separadas por vírgula (ex.: USDCAD-OTC,EURUSD-OTC)")
    symbols = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()]
    if not symbols:
        sys.exit("Informe ao menos uma paridade.")

    stake = ask_float("Stake fixo por ordem", 1.0)
    expiry_minutes = ask_int("Expiração (minutos)", 1)
    poll_interval_s = ask_float("Intervalo entre checagens de candle novo (segundos)", 15.0)

    config = ExecutionConfig(
        account_type=AccountType.PRACTICE,  # sempre PRACTICE — sem opção de REAL neste script
        fixed_stake=stake,
        instrument=InstrumentType.BINARY,  # DIGITAL não confirma nesta lib (ver relatório, seção 8.3-8.5)
        expiry_minutes=expiry_minutes,
    )

    print("\nResumo:")
    print(f"  estratégia       : {strategy_name}")
    print(f"  confiança mínima : {min_confidence:.2f} (sinais mais fracos que isso são ignorados)")
    print(f"  paridades        : {', '.join(symbols)}")
    print(f"  stake            : {stake} por ordem, conta PRACTICE (demo)")
    print(f"  expiração        : {expiry_minutes} min")
    print(f"  intervalo        : a cada {poll_interval_s}s")
    confirm = ask("\nConfirma o início do loop? (s/N)", "N")
    if confirm.lower() not in ("s", "sim", "y", "yes"):
        print("Cancelado.")
        return

    print("\nConectando...")
    gateway = IQOptionGateway(Credentials(email=email, password=password), practice_by_default=True)
    try:
        gateway.connect()
    except TwoFactorAuthRequired as exc:
        sys.exit(f"Conta exige 2FA — resolva fora deste fluxo antes de operar.\n{exc}")
    except BrokerConnectionError as exc:
        sys.exit(f"Falha ao conectar: {exc}")

    print(f"Conectado. Conta: {gateway.current_account_type().value} | saldo: {gateway.get_balance():.2f}\n")

    guard = ExecutionGuard(config)
    repository = InMemoryExecutionRepository()
    executor = LiveExecutor(broker=gateway, guard=guard, repository=repository, config=config)
    stats = SessionStats()

    loops = [
        LiveTradingLoop(
            candle_source=gateway,
            executor=executor,
            strategy=StrategyRegistry.create(strategy_name, min_confidence=min_confidence),  # instância própria por símbolo
            symbol=symbol,
            timeframe=Timeframe.M1,
            poll_interval_s=poll_interval_s,
            on_signal=lambda evaluation, sym=symbol: print_signal(sym, evaluation),
            on_record=lambda record, sym=symbol: print_record(sym, record, stats),
            on_error=lambda exc, sym=symbol: print(f"[erro] {sym}: {exc}"),
        )
        for symbol in symbols
    ]

    stop_event = threading.Event()

    def _handle_sigint(signum, frame):
        print("\nParando (Ctrl+C)...")
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_sigint)

    print(f"Operando {', '.join(symbols)} — Ctrl+C para parar.\n")
    while not stop_event.is_set():
        for loop in loops:
            if stop_event.is_set():
                break
            try:
                loop.run_once()
            except Exception as exc:
                print(f"[erro] {loop.symbol}: {exc}")
        stop_event.wait(poll_interval_s)

    print(f"\nParado. {len(repository.list_all())} ordens registradas nesta sessão.")
    print(f"Taxa de acerto final: {stats.summary()}")
    print(f"Saldo final: {gateway.get_balance():.2f}")


if __name__ == "__main__":
    main()
