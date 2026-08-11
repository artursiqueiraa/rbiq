from pathlib import Path

# backend/tests/conftest.py -> project root is two levels up
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = PROJECT_ROOT / "data" / "raw" / "test"
