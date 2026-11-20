# hotdocs-criterion: sha256:e22810d5672bd5993213903c848c1eb6d55562738f3f1b564adf98f7227770ce
import json
import urllib.request
from pathlib import Path

import pytest

import secret_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_cache_manager_source():
    # A flat-module stand-in for cache-manager that always misses, so the
    # scan under test is always a fresh, full scan of the fixture repo.
    lines = [
        "import dataclasses",
        "import datetime",
        "",
        "",
        "@dataclasses.dataclass",
        "class CacheKey:",
        "    spec_bundle_hash: object",
        "    gate_inputs_hash: object",
        "    gate_version: object",
        "    model_pin: object",
        "",
        "",
        "@dataclasses.dataclass",
        "class CachedResult:",
        "    gate_type: object",
        "    payload: object",
        "    stored_at: object",
        "",
        "",
        "class Miss:",
        "    def __eq__(self, other):",
        "        return isinstance(other, Miss)",
        "",
        "    def __hash__(self):",
        "        return 0",
        "",
        "",
        "class SchemaValidationError(ValueError):",
        "    pass",
        "",
        "",
        "def get(cache_key, *, repo_root=None):",
        "    return Miss()",
        "",
        "",
        "def put(cache_key, result, *, repo_root=None):",
        "    return None",
        "",
        "",
        "def now_iso():",
        "    now = datetime.datetime.now(datetime.timezone.utc)",
        "    return now.strftime(" + repr("%Y-%m-%dT%H:%M:%SZ") + ")",
        "",
        "",
        "def stats(*, repo_root=None):",
        "    return {" + repr("entry_count") + ": 0}",
        "",
        "",
        "def main(argv=None):",
        "    return 0",
        "",
    ]
    return "\n".join(lines)


def _planted_aws_key():
    # Built at runtime so this test file itself carries no detectable literal.
    return "AK" + "IA" + "IOSF" + "ODNN" + "7EXA" + "MPLE"


@pytest.fixture
def flagged_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(_fake_cache_manager_source())

    (repo_root / "config.py").write_text(
        "aws_access_key_id = " + repr(_planted_aws_key()) + "\n"
    )

    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise AssertionError("no webhook is configured; urlopen must not be called")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    return repo_root


def test_full_scan_with_match_is_flagged(flagged_repo):
    result = secret_scanner.scan(flagged_repo)

    assert field(result, "scope") == "full"
    matches = field(result, "matches")
    assert len(matches) >= 1
    assert any(field(m, "file") == "config.py" for m in matches)
    assert field(result, "flagged") is True

    as_dict = result.to_dict()
    assert as_dict["flagged"] is True
    assert len(as_dict["matches"]) >= 1


def test_full_scan_with_match_reports_merge_blocked(flagged_repo, capsys):
    code = secret_scanner.main(["--repo-root", str(flagged_repo), "--format=json"])
    out = capsys.readouterr().out

    # Exit 1 is the CLI's "flagged, merge blocked" report.
    assert code == 1
    doc = json.loads(out)
    assert doc["scope"] == "full"
    assert doc["flagged"] is True
    assert len(doc["matches"]) >= 1
    assert any(m["file"] == "config.py" for m in doc["matches"])


def test_full_scan_text_format_reports_flagged(flagged_repo, capsys):
    code = secret_scanner.main(["secret-scan", "--repo-root=" + str(flagged_repo)])
    out = capsys.readouterr().out

    assert code == 1
    assert "FLAGGED" in out