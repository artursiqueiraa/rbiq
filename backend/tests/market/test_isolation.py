import ast
from pathlib import Path

FORBIDDEN_PREFIXES = ("app.strategies", "app.signals", "app.backtest", "app.paper", "app.execution")

MARKET_DIR = Path(__file__).resolve().parents[2] / "app" / "market"


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_market_engine_never_imports_strategy_or_execution_layers():
    """Same static-analysis approach as the Indicators Engine's isolation test
    (Sprint 3): parses every .py file under app/market/ rather than trying to
    exercise it at runtime, since none of the forbidden packages exist yet for
    a runtime import to fail against."""
    violations: list[str] = []

    for path in MARKET_DIR.rglob("*.py"):
        modules = _imported_modules(path.read_text(encoding="utf-8"))
        for module in modules:
            if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_PREFIXES):
                violations.append(f"{path.relative_to(MARKET_DIR)} imports {module!r}")

    assert not violations, "Market Engine isolation violated:\n" + "\n".join(violations)
