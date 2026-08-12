"""
Isolamento entre Backtest Engine (Sprint 6) e o loop de trading ao vivo
(`app.live`, seção 8.6 do relatório da Sprint 7).

Regra: `app.live` reimplementa a lógica de avaliação de estratégia (a mesma
receita de `app/backtest/adapters.py::StrategyEvaluatorAdapter`) em vez de
importar de `app.backtest` — para não criar um terceiro ponto de
acoplamento entre `app.backtest` e `app.execution`, que já são isolados um
do outro (ver tests/execution/test_isolation.py). `app.backtest`, por sua
vez, nunca deveria saber que `app.live` existe.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"


def _imported_top_level_modules(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0] + "." + alias.name.split(".")[1] if "." in alias.name else alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_live_never_imports_backtest():
    live_dir = APP_DIR / "live"
    for py_file in live_dir.glob("*.py"):
        modules = _imported_top_level_modules(py_file)
        offending = {m for m in modules if m == "app.backtest" or m.startswith("app.backtest.")}
        assert not offending, f"{py_file} importa app.backtest: {offending}"


def test_backtest_never_imports_live():
    backtest_dir = APP_DIR / "backtest"
    for py_file in backtest_dir.glob("*.py"):
        modules = _imported_top_level_modules(py_file)
        offending = {m for m in modules if m == "app.live" or m.startswith("app.live.")}
        assert not offending, f"{py_file} importa app.live: {offending}"
