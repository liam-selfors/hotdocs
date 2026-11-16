import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "provenance-tracker-ui"))
import provenance_tracker_ui  # noqa: E402,F401
