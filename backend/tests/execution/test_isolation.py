"""
Isolamento entre Backtest Engine (Sprint 6) e Live Execution Engine (Sprint 7).

Regra: `app.backtest` NUNCA importa `app.execution`. O único ponto de contato
entre os dois mundos é consumir um `Signal` por duck-typing — nenhum módulo
de um lado referencia tipos/tabelas do outro.
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


def test_backtest_never_imports_execution():
    backtest_dir = APP_DIR / "backtest"
    for py_file in backtest_dir.glob("*.py"):
        modules = _imported_top_level_modules(py_file)
        offending = {m for m in modules if m == "app.execution" or m.startswith("app.execution.")}
        assert not offending, f"{py_file} importa app.execution: {offending}"


def test_execution_never_imports_backtest():
    execution_dir = APP_DIR / "execution"
    for py_file in execution_dir.glob("*.py"):
        modules = _imported_top_level_modules(py_file)
        offending = {m for m in modules if m == "app.backtest" or m.startswith("app.backtest.")}
        assert not offending, f"{py_file} importa app.backtest: {offending}"


def test_execution_record_and_backtest_result_are_distinct_types():
    from app.backtest import BacktestResult
    from app.execution import ExecutionRecord

    assert ExecutionRecord is not BacktestResult
    assert {f.name for f in __import__("dataclasses").fields(ExecutionRecord)} != {
        f.name for f in __import__("dataclasses").fields(BacktestResult)
    }
