import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "component-gate-runner"))
import component_gate_runner  # noqa: E402,F401
