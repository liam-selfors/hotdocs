import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "provenance-checker"))
import provenance_checker  # noqa: E402


def write_manifest(repo_root: Path, bare_slug: str, **fields) -> Path:
    """Writes gen/<bare_slug>/.provenance.json with sensible defaults,
    overridable via fields."""
    manifest = {
        "spec_bundle_hash": "H",
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {"flagged": False},
        "secret_scan": {"flagged": False},
    }
    manifest.update(fields)
    comp_dir = repo_root / "gen" / bare_slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    path = comp_dir / ".provenance.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    return tmp_path
