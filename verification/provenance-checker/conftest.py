import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "provenance-checker"))
import provenance_checker  # noqa: E402


# Since D344/D345 every unsealed component's current assets value starts
# with the implicit python entry; a planted fake adapter keeps it fixed.
FAKE_PYTHON_ADAPTER = (
    "KIND = 'python'\n"
    "def guidance():\n    return {'generator': '', 'test_author': ''}\n"
    "def provision(repo_root):\n"
    "    return {'ok': True, 'reason': '', 'versions': {'python': '3.12.4', 'packages': 'sha256:' + 'a' * 64},"
    " 'lockfile_sha256': None, 'interpreter': '/fake/python'}\n"
)


def python_entry(repo_root: Path) -> dict:
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    return {"kind": "python", "path": ".", "definition_sha256": None,
            "adapter_sha256": "sha256:" + hashlib.sha256(adapter.read_bytes()).hexdigest(),
            "versions": {"python": "3.12.4", "packages": "sha256:" + "a" * 64}, "lockfile_sha256": None}


def write_manifest(repo_root: Path, bare_slug: str, **fields) -> Path:
    """Writes gen/<bare_slug>/.provenance.json with sensible defaults,
    overridable via fields; `assets` defaults to the current value."""
    manifest = {
        "spec_bundle_hash": "H",
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {"flagged": False},
        "secret_scan": {"flagged": False},
        "assets": [python_entry(repo_root)],
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
    adapter = tmp_path / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")
    return tmp_path
