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

Depois de conectar, o padrão é uma varredura AUTOMÁTICA (`scripts/_screen.py`
— mesma lógica de `screen_pairs.py`, Sprint 7 seção 8.11) que testa TODAS as
estratégias em cada par aberto agora via backtest real contra candles
recentes, e sugere a(s) melhor(es) combinação(ões) par+estratégia por
expectancy/taxa de acerto MEDIDA — cada par escolhido pode acabar rodando com
uma estratégia diferente, a que teve melhor resultado nele. Quem preferir uma
única estratégia fixa para todos os pares (ou digitar pares à mão) pode
recusar a varredura automática.

`min_confidence` é repassado a cada estratégia — cada `Signal` já carrega um
`confidence` (Sprint 5, `app/strategies/base.py::decide_direction`),
calculado a partir de quantas condições técnicas bateram; um sinal só é
gerado se cruzar esse mínimo. IMPORTANTE: isso é uma pontuação baseada em
regras, não uma taxa de acerto histórica medida — a varredura acima É a
medição real.

Uso (a partir de backend/, com o ambiente uv já sincronizado):
    uv run python scripts/run_live_bot.py

Ctrl+C encerra a qualquer momento, de forma limpa — inclusive durante os
prompts de configuração, não só depois que o loop já começou.
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
from scripts._screen import rank_by_expectancy, scan_pairs


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


def ask_strategy_name() -> str:
    """Re-pergunta em loop em vez de derrubar a sessão inteira num typo —
    email, senha e a conexão já feita não deveriam se perder por causa de
    um nome de estratégia digitado errado."""
    print("\nEstratégias disponíveis:", ", ".join(StrategyRegistry.names()))
    while True:
        strategy_name = ask("Estratégia", StrategyRegistry.names()[0])
        if strategy_name in StrategyRegistry.names():
            return strategy_name
        print(f"  estratégia desconhecida: {strategy_name!r} — tente de novo.")


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


def _dedupe_by_symbol(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Mantém só a primeira ocorrência de cada paridade (a de melhor
    expectancy, já que a lista de entrada vem ordenada) — evita duas
    estratégias competindo pelo mesmo par ao mesmo tempo só porque as duas
    apareceram bem ranqueadas."""
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for symbol, strategy_name in pairs:
        if symbol not in seen:
            seen.add(symbol)
            result.append((symbol, strategy_name))
    return result


def ask_manual_pairs(strategy_name: str) -> list[tuple[str, str]]:
    """Entrada manual — cada paridade digitada roda com a MESMA estratégia
    (fornecida pelo chamador)."""
    symbols_raw = ask("Paridades a operar, separadas por vírgula (ex.: USDCAD-OTC,EURUSD-OTC)")
    symbols = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()]
    if not symbols:
        sys.exit("Informe ao menos uma paridade.")
    return _dedupe_by_symbol([(symbol, strategy_name) for symbol in symbols])


def scan_and_choose(
    gateway: IQOptionGateway,
    strategy_names: list[str],
    min_confidence: float,
    label: str,
) -> list[tuple[str, str]]:
    """Varre os pares abertos agora, roda um backtest real de cada
    estratégia em `strategy_names` em cada par, e deixa o operador escolher
    as combinações par+estratégia por expectancy/taxa de acerto MEDIDA. Cai
    de volta para escolha manual (estratégia + pares) se a varredura for
    recusada, falhar, ou não achar nada com trades suficientes."""
    try:
        open_symbols = gateway.list_open_symbols(InstrumentType.BINARY)
    except BrokerConnectionError as exc:
        print(f"Falha ao listar paridades abertas: {exc} — entrada manual.")
        return ask_manual_pairs(ask_strategy_name())
    if not open_symbols:
        print("Nenhuma paridade aberta encontrada agora — entrada manual.")
        return ask_manual_pairs(ask_strategy_name())

    print(f"{len(open_symbols)} paridades abertas agora (ordenadas por payout, maior primeiro).")
    top_n = ask_int(f"Quantas das top paridades por payout varrer (disponíveis: {len(open_symbols)})", 15)
    top_n = max(1, min(top_n, len(open_symbols)))
    candidates = open_symbols[:top_n]

    candle_count = ask_int("Quantos candles M1 de histórico por paridade (máx. ~1000; mais = mais lento)", 500)
    min_trades = ask_int("Mínimo de trades para uma combinação contar (filtra amostras pequenas demais)", 10)

    total_runs = len(candidates) * len(strategy_names)
    print(
        f"\nVai rodar {total_runs} backtests reais ({len(candidates)} paridades x "
        f"{len(strategy_names)} estratégia(s) — {label}). Pode levar um pouco — Ctrl+C "
        "interrompe e usa o que já foi calculado até ali.\n"
    )
    results = scan_pairs(gateway, strategy_names, candidates, min_confidence, candle_count)
    ranked = rank_by_expectancy(results, min_trades)

    if not ranked:
        print(f"\nNenhuma combinação teve pelo menos {min_trades} trades nesse recorte — entrada manual.")
        return ask_manual_pairs(ask_strategy_name())

    print(f"\n=== MELHORES COMBINAÇÕES ({label}, ordenadas por expectancy) ===")
    for rank, r in enumerate(ranked[:10], start=1):
        print(f"{rank:2d}. {r.line()}")
    print(
        "\nATENÇÃO: medição sobre um recorte curto e recente de histórico — não é garantia "
        "de resultado ao vivo, nem afirmação de lucratividade.\n"
    )

    default_top = min(3, len({r.symbol for r in ranked}))
    choice = ask(
        f"Quais operar? Números da lista acima separados por vírgula, ou Enter para as "
        f"{default_top} melhores paridades",
        "",
    )
    if not choice:
        return _dedupe_by_symbol([(r.symbol, r.strategy) for r in ranked])[:default_top]

    chosen: list[tuple[str, str]] = []
    for token in choice.split(","):
        token = token.strip()
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(ranked):
                chosen.append((ranked[idx].symbol, ranked[idx].strategy))
    if not chosen:
        print("Nenhum número válido reconhecido — usando as melhores por padrão.")
        return _dedupe_by_symbol([(r.symbol, r.strategy) for r in ranked])[:default_top]
    return _dedupe_by_symbol(chosen)


def ask_pairs(gateway: IQOptionGateway, min_confidence: float) -> list[tuple[str, str]]:
    """Ponto de entrada da escolha de pares: por padrão varre TODAS as
    estratégias e sugere a melhor combinação par+estratégia — o operador
    não precisa escolher a estratégia antes. Quem preferir uma única
    estratégia fixa para todos os pares (só filtrando quais pares usar
    nela, ou digitando os pares à mão) pode recusar."""
    do_full_scan = ask(
        "Testar TODAS as estratégias nos pares abertos e sugerir a(s) melhor(es) combinação(ões)? (S/n)",
        "S",
    )
    if do_full_scan.lower() in ("s", "sim", "y", "yes"):
        return scan_and_choose(gateway, StrategyRegistry.names(), min_confidence, "todas as estratégias")

    strategy_name = ask_strategy_name()
    do_single_scan = ask(f"Varrer pares abertos e sugerir os melhores para {strategy_name}? (S/n)", "S")
    if do_single_scan.lower() not in ("s", "sim", "y", "yes"):
        return ask_manual_pairs(strategy_name)
    return scan_and_choose(gateway, [strategy_name], min_confidence, strategy_name)


def main() -> None:
    print("=== IQO Strategy Lab — loop de trading ao vivo (conta DEMO) ===\n")
    print("Suas credenciais NÃO são salvas em disco — só usadas nesta sessão.\n")

    email = ask("Email IQ Option")
    password = getpass.getpass("Senha IQ Option (não aparece na tela): ")
    if not email or not password:
        sys.exit("Email e senha são obrigatórios.")

    min_confidence = ask_float(
        "Confiança mínima para entrar (0.0 a 1.0 — mais alto = mais seletivo, menos entradas)", 0.75
    )
    min_confidence = min(max(min_confidence, 0.0), 1.0)  # nunca fora de [0, 1]

    print("\nConectando...")
    gateway = IQOptionGateway(Credentials(email=email, password=password), practice_by_default=True)
    try:
        gateway.connect()
    except TwoFactorAuthRequired as exc:
        sys.exit(f"Conta exige 2FA — resolva fora deste fluxo antes de operar.\n{exc}")
    except BrokerConnectionError as exc:
        sys.exit(f"Falha ao conectar: {exc}")
    print(f"Conectado. Conta: {gateway.current_account_type().value} | saldo: {gateway.get_balance():.2f}\n")

    pairs = ask_pairs(gateway, min_confidence)

    stake = ask_float("Stake fixo por ordem", 1.0)
    expiry_minutes = ask_int("Expiração (minutos)", 1)
    poll_interval_s = ask_float("Intervalo entre checagens de candle novo (segundos)", 15.0)

    # poll_timeout_s (ExecutionConfig) é o teto de espera pela RESOLUÇÃO da
    # ordem, não a checagem de candle novo acima — precisa ser folgado o
    # bastante em relação à expiração, senão estoura ANTES da própria opção
    # fechar. Achado real: com o default fixo de 60s (config.py) e expiração
    # de 1 min, o timeout ficava exatamente no limite do tempo que a ordem
    # já leva pra resolver — qualquer latência da corretora estourava
    # ("Timeout aguardando resolução..."), e para expirações maiores que 1
    # min o timeout de 60s garantiria falha sempre. Escalado com folga aqui.
    poll_timeout_s = expiry_minutes * 60 + 30

    config = ExecutionConfig(
        account_type=AccountType.PRACTICE,  # sempre PRACTICE — sem opção de REAL neste script
        fixed_stake=stake,
        instrument=InstrumentType.BINARY,  # DIGITAL não confirma nesta lib (ver relatório, seção 8.3-8.5)
        expiry_minutes=expiry_minutes,
        poll_timeout_s=poll_timeout_s,
    )

    print("\nResumo:")
    print(f"  confiança mínima : {min_confidence:.2f} (sinais mais fracos que isso são ignorados)")
    print("  pares e estratégias:")
    for symbol, strategy_name in pairs:
        print(f"    {symbol:14s} -> {strategy_name}")
    print(f"  stake            : {stake} por ordem, conta PRACTICE (demo)")
    print(f"  expiração        : {expiry_minutes} min (espera até {poll_timeout_s:.0f}s pela resolução de cada ordem)")
    print(f"  intervalo        : a cada {poll_interval_s}s")
    confirm = ask("\nConfirma o início do loop? (s/N)", "N")
    if confirm.lower() not in ("s", "sim", "y", "yes"):
        print("Cancelado.")
        return

    guard = ExecutionGuard(config)
    repository = InMemoryExecutionRepository()
    executor = LiveExecutor(broker=gateway, guard=guard, repository=repository, config=config)
    stats = SessionStats()

    loops = [
        LiveTradingLoop(
            candle_source=gateway,
            executor=executor,
            strategy=StrategyRegistry.create(strategy_name, min_confidence=min_confidence),
            symbol=symbol,
            timeframe=Timeframe.M1,
            poll_interval_s=poll_interval_s,
            on_signal=lambda evaluation, sym=symbol: print_signal(sym, evaluation),
            on_record=lambda record, sym=symbol: print_record(sym, record, stats),
            on_error=lambda exc, sym=symbol: print(f"[erro] {sym}: {exc}"),
        )
        for symbol, strategy_name in pairs
    ]

    stop_event = threading.Event()
    stopping_announced = threading.Event()

    def _handle_sigint(signum, frame):
        # Só avisa uma vez: se uma ordem está em `await_result`, o processo
        # fica bloqueado até ela resolver ou até poll_timeout_s estourar —
        # nenhum Ctrl+C repetido acelera isso (o handler só seta uma flag,
        # não interrompe a chamada em andamento), então repetir a mensagem
        # a cada tecla só confundia, parecendo que nada estava acontecendo.
        if not stopping_announced.is_set():
            stopping_announced.set()
            print(
                f"\nParando (Ctrl+C)... se houver uma ordem em andamento, espera até "
                f"{poll_timeout_s:.0f}s por ela antes de encerrar — não precisa apertar de novo."
            )
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_sigint)

    symbols_label = ", ".join(symbol for symbol, _ in pairs)
    print(f"Operando {symbols_label} — Ctrl+C para parar.\n")
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
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelado (Ctrl+C).")
        sys.exit(0)
