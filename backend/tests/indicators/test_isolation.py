import ast
from pathlib import Path

FORBIDDEN_PREFIXES = ("app.strategies", "app.signals", "app.backtest", "app.paper", "app.execution")

INDICATORS_DIR = Path(__file__).resolve().parents[2] / "app" / "indicators"


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_indicators_engine_never_imports_strategy_or_execution_layers():
    """The whole point of this Sprint's boundary: Indicators can be calculated
    without ever knowing a strategy, signal, backtest, paper-trading, or
    execution module exists. This test parses every .py file under
    app/indicators/ (not just runs it) so it fails the moment an import is
    added, even before that module is ever exercised at runtime."""
    violations: list[str] = []

    for path in INDICATORS_DIR.rglob("*.py"):
        modules = _imported_modules(path.read_text(encoding="utf-8"))
        for module in modules:
            if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_PREFIXES):
                violations.append(f"{path.relative_to(INDICATORS_DIR)} imports {module!r}")

    assert not violations, "Indicators Engine isolation violated:\n" + "\n".join(violations)
