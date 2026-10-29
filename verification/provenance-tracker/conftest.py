import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "provenance-tracker"))
import provenance_tracker  # noqa: E402,F401
