import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "secret-scanner"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "cache-manager"))
import secret_scanner  # noqa: E402


def write_pattern_db(repo_root: Path, rules: list) -> Path:
    path = repo_root / "patterns.json"
    path.write_text(json.dumps({"version": "1.0.0", "rules": rules}), encoding="utf-8")
    return path


AWS_RULE = {"rule_id": "aws-access-key-id", "risk_tier": "high", "pattern": r"AKIA[0-9A-Z]{16}"}
GENERIC_RULE = {"rule_id": "generic-token", "risk_tier": "medium", "pattern": r"tok_[A-Za-z0-9]{10}"}


def write_file(root: Path, rel: str, content: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_SECRET_PATTERNS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    (tmp_path / "specs").mkdir()
    (tmp_path / "gen").mkdir()
    (tmp_path / "verification").mkdir()
    return tmp_path
