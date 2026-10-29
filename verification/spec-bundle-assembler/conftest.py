import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "spec-bundle-assembler"))
import spec_bundle_assembler  # noqa: E402,F401
