import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "decision-drift-detector"))
import decision_drift_detector  # noqa: E402,F401
