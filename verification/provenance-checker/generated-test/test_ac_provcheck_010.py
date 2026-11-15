import json
from pathlib import Path

import pytest

import provenance_checker


GATE_VERSIONS = {"license_scanner": "1"}
GATE_VERSIONS_JSON = json.dumps(GATE_VERSIONS)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _manifest():
    return {
        "spec_bundle_hash": "sha256:0a1b",
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": dict(GATE_VERSIONS),
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": {
            "component_id": "comp-foo",
            "criteria": [
                {
                    "id": "AC-FOO-001",
                    "covers": "R-FOO-001",
                    "kind": "compiled",
                    "result": "pass",
                }
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.92,
            "overall": "pass",
        },
        "license_scan": {
            "component_id": "comp-foo",
            "gate_version": "1",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.0,
            "block_threshold": 0.70,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    text = json.dumps(_manifest(), indent=2)
    for sub in ("gen", "verification"):
        d = root / sub / "foo"
        d.mkdir(parents=True)
        (d / ".provenance.json").write_text(text, encoding="utf-8")
    monkeypatch.chdir(root)
    return root


def _run(argv):
    try:
        rc = provenance_checker.main(argv)
    except SystemExit as exc:
        code = exc.code
        rc = code if isinstance(code, int) else (0 if code is None else 1)
    return rc


def test_json_hit_returns_0(repo_root, capsys):
    capsys.readouterr()
    rc = _run([
        "check",
        "comp-foo",
        "--spec-bundle-hash=sha256:0a1b",
        "--gate-versions=" + GATE_VERSIONS_JSON,
        "--repo-root=" + str(repo_root),
        "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert field(data, "hit") is True


def test_text_miss_returns_0(repo_root, capsys):
    capsys.readouterr()
    rc = _run([
        "check",
        "comp-foo",
        "--spec-bundle-hash",
        "sha256:ffff",
        "--gate-versions",
        GATE_VERSIONS_JSON,
        "--repo-root",
        str(repo_root),
        "--format",
        "text",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "miss" in out


def _usage_cases(root):
    r = str(root)
    gv = "--gate-versions=" + GATE_VERSIONS_JSON
    return {
        "missing_spec_bundle_hash": [
            "check", "comp-foo", gv, "--repo-root=" + r, "--format=json",
        ],
        "hash_without_prefix": [
            "check", "comp-foo", "--spec-bundle-hash=0a1b", gv,
            "--repo-root=" + r, "--format=json",
        ],
        "gate_versions_not_object": [
            "check", "comp-foo", "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions", "[1]", "--repo-root=" + r, "--format=json",
        ],
        "bogus_format": [
            "check", "comp-foo", "--spec-bundle-hash=sha256:0a1b", gv,
            "--repo-root=" + r, "--format=bogus",
        ],
        "unknown_argument": [
            "check", "comp-foo", "--spec-bundle-hash=sha256:0a1b", gv,
            "--repo-root=" + r, "--format=json", "--no-such-flag=1",
        ],
        "repo_root_last_without_value": [
            "check", "comp-foo", "--spec-bundle-hash=sha256:0a1b", gv,
            "--format=json", "--repo-root",
        ],
    }


@pytest.mark.parametrize(
    "case",
    [
        "missing_spec_bundle_hash",
        "hash_without_prefix",
        "gate_versions_not_object",
        "bogus_format",
        "unknown_argument",
        "repo_root_last_without_value",
    ],
)
def test_usage_errors_return_2(repo_root, case, capsys):
    argv = _usage_cases(repo_root)[case]
    rc = _run(argv)
    capsys.readouterr()
    assert rc == 2, f"{case}: expected exit 2, got {rc!r}"