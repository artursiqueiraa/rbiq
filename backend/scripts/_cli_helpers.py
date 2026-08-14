"""Helpers compartilhados pelos scripts interativos (run_live_bot.py,
backtest_live_pair.py, screen_pairs.py). Extraído depois do terceiro uso
duplicado — não antes."""

from __future__ import annotations

import sys


def safe_print(text: str = "") -> None:
    """`print()` normal, mas nunca quebra num console Windows com codepage
    cp1252 (achado real: `summary_text()` do Backtest Engine usa `→`, que
    não existe em cp1252 — já documentado desde a Sprint 6). Em vez de
    deixar o script morrer bem no resultado final, troca os caracteres que
    o console não sabe exibir por `?` e segue."""
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "ascii"
        print(text.encode(encoding, errors="replace").decode(encoding))


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or (default or "")


def ask_float(prompt: str, default: float) -> float:
    raw = ask(prompt, str(default))
    try:
        return float(raw)
    except ValueError:
        safe_print(f"  valor inválido, usando {default}")
        return default


def ask_int(prompt: str, default: int) -> int:
    raw = ask(prompt, str(default))
    try:
        return int(raw)
    except ValueError:
        safe_print(f"  valor inválido, usando {default}")
        return default
