import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "hotdocs-cli"))
import hotdocs_cli  # noqa: E402,F401
