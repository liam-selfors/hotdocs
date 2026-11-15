import json
from pathlib import Path

import pytest

import provenance_checker


SPEC_HASH = "sha256:0a1b"
GATE_VERSIONS = {"license_scanner": "1"}
GATE_VERSIONS_JSON = json.dumps(GATE_VERSIONS)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "generated-test",
                "result": "pass",
            },
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "compiled",
                "result": "pass",
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }


def _license_scan():
    return {
        "component_id": "comp-foo",
        "gate_version": "1",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _manifest():
    return {
        "spec_bundle_hash": SPEC_HASH,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": dict(GATE_VERSIONS),
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": _verification_report(),
        "license_scan": _license_scan(),
        "secret_scan": _secret_scan(),
    }


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    text = json.dumps(_manifest(), indent=2)
    for base in ("gen", "verification"):
        d = root / base / "foo"
        d.mkdir(parents=True)
        (d / ".provenance.json").write_text(text, encoding="utf-8")
    monkeypatch.chdir(root)
    return root


def _run(argv):
    try:
        return provenance_checker.main(argv)
    except SystemExit as exc:  # exit code via SystemExit is still the exit code
        return exc.code


def test_equals_form_json_reports_hit(repo_root, capsys):
    capsys.readouterr()
    rc = _run(
        [
            "check",
            "comp-foo",
            f"--spec-bundle-hash={SPEC_HASH}",
            f"--gate-versions={GATE_VERSIONS_JSON}",
            f"--repo-root={repo_root}",
            "--format=json",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert field(data, "hit") is True


def test_separate_value_form_text_reports_miss(repo_root, capsys):
    capsys.readouterr()
    rc = _run(
        [
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
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "miss" in out


def _usage_cases(root):
    r = str(root)
    return {
        "missing-spec-bundle-hash": [
            "check",
            "comp-foo",
            f"--gate-versions={GATE_VERSIONS_JSON}",
            f"--repo-root={r}",
            "--format=json",
        ],
        "hash-without-prefix": [
            "check",
            "comp-foo",
            "--spec-bundle-hash=0a1b",
            f"--gate-versions={GATE_VERSIONS_JSON}",
            f"--repo-root={r}",
            "--format=json",
        ],
        "gate-versions-not-object": [
            "check",
            "comp-foo",
            f"--spec-bundle-hash={SPEC_HASH}",
            "--gate-versions",
            "[1]",
            f"--repo-root={r}",
            "--format=json",
        ],
        "bogus-format": [
            "check",
            "comp-foo",
            f"--spec-bundle-hash={SPEC_HASH}",
            f"--gate-versions={GATE_VERSIONS_JSON}",
            f"--repo-root={r}",
            "--format=bogus",
        ],
        "unknown-argument": [
            "check",
            "comp-foo",
            f"--spec-bundle-hash={SPEC_HASH}",
            f"--gate-versions={GATE_VERSIONS_JSON}",
            f"--repo-root={r}",
            "--format=json",
            "--no-such-flag",
        ],
        "repo-root-last-no-value": [
            "check",
            "comp-foo",
            f"--spec-bundle-hash={SPEC_HASH}",
            f"--gate-versions={GATE_VERSIONS_JSON}",
            "--format=json",
            "--repo-root",
        ],
    }


@pytest.mark.parametrize(
    "case",
    [
        "missing-spec-bundle-hash",
        "hash-without-prefix",
        "gate-versions-not-object",
        "bogus-format",
        "unknown-argument",
        "repo-root-last-no-value",
    ],
)
def test_usage_errors_return_2(repo_root, capsys, case):
    argv = _usage_cases(repo_root)[case]
    rc = _run(argv)
    capsys.readouterr()
    assert rc == 2