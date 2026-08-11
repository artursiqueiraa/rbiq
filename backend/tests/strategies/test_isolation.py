import ast
from pathlib import Path

FORBIDDEN_MODULE_PREFIXES = ("app.execution", "app.broker", "app.iqoption", "app.paper", "app.paper_trading")

# service.py is the one file allowed to know `Session` exists (a type hint for
# "a database session was handed to me") — but even it must never import
# query-building symbols and issue SQL itself. Everything else in the package
# must not mention sqlalchemy at all.
ALLOWED_SQLALCHEMY_IMPORTS = {"service.py": {"sqlalchemy.orm"}}

STRATEGIES_DIR = Path(__file__).resolve().parents[2] / "app" / "strategies"


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_strategy_engine_never_imports_execution_or_broker_layers():
    """Same static-analysis approach as the Indicators/Market Engines
    (Sprints 3-4): parses every .py file under app/strategies/ rather than
    exercising it at runtime, since none of these packages exist yet for a
    runtime import to fail against."""
    violations: list[str] = []

    for path in STRATEGIES_DIR.rglob("*.py"):
        modules = _imported_modules(path.read_text(encoding="utf-8"))
        for module in modules:
            if any(module == prefix or module.startswith(prefix + ".") for prefix in FORBIDDEN_MODULE_PREFIXES):
                violations.append(f"{path.relative_to(STRATEGIES_DIR)} imports {module!r}")

    assert not violations, "Strategy Engine isolation violated:\n" + "\n".join(violations)


def test_strategy_engine_never_queries_sql_directly():
    """Section 60: strategies must not access PostgreSQL directly. All DB
    access goes through CandleRepository/MarketService, imported as whole
    modules — never `sqlalchemy.select`, `sqlalchemy.text`, or similar
    query-building imports inside app/strategies/ itself."""
    violations: list[str] = []

    for path in STRATEGIES_DIR.rglob("*.py"):
        modules = _imported_modules(path.read_text(encoding="utf-8"))
        allowed = ALLOWED_SQLALCHEMY_IMPORTS.get(path.name, set())
        for module in modules:
            if module == "sqlalchemy" or module.startswith("sqlalchemy."):
                if module not in allowed:
                    violations.append(f"{path.relative_to(STRATEGIES_DIR)} imports {module!r}")

    assert not violations, "Strategy Engine issues SQL directly:\n" + "\n".join(violations)
