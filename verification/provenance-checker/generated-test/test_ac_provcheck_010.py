# hotdocs-criterion: sha256:9942d02b0cc19237551decb505b717f6070182326f8d1265b2296b5f1ab0c287
import json
from pathlib import Path

import pytest

import provenance_checker


GATE_VERSIONS = {"license_scanner": "1"}
GATE_VERSIONS_ARG = json.dumps(GATE_VERSIONS)


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
            }
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
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
        "spec_bundle_hash": "sha256:0a1b",
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
    root = tmp_path / "repo"
    manifest_text = json.dumps(_manifest(), indent=2)
    for sub in ("gen", "verification"):
        d = root / sub / "foo"
        d.mkdir(parents=True, exist_ok=True)
        (d / ".provenance.json").write_text(manifest_text, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return root


def run_main(argv):
    try:
        return provenance_checker.main(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code


def test_json_hit_equals_form(repo_root, capsys):
    capsys.readouterr()
    code = run_main(
        [
            "check",
            "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions=" + GATE_VERSIONS_ARG,
            "--repo-root=" + str(repo_root),
            "--format=json",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert field(data, "hit") is True


def test_text_miss_next_argument_form(repo_root, capsys):
    capsys.readouterr()
    code = run_main(
        [
            "check",
            "comp-foo",
            "--spec-bundle-hash",
            "sha256:ffff",
            "--gate-versions",
            GATE_VERSIONS_ARG,
            "--repo-root",
            str(repo_root),
            "--format",
            "text",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "miss" in out


def _usage_error_argvs(root):
    r = str(root)
    return {
        "missing-spec-bundle-hash": [
            "check",
            "comp-foo",
            "--gate-versions=" + GATE_VERSIONS_ARG,
            "--repo-root=" + r,
            "--format=json",
        ],
        "hash-without-prefix": [
            "check",
            "comp-foo",
            "--spec-bundle-hash=0a1b",
            "--gate-versions=" + GATE_VERSIONS_ARG,
            "--repo-root=" + r,
            "--format=json",
        ],
        "gate-versions-not-object": [
            "check",
            "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions",
            "[1]",
            "--repo-root=" + r,
            "--format=json",
        ],
        "bogus-format": [
            "check",
            "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions=" + GATE_VERSIONS_ARG,
            "--repo-root=" + r,
            "--format=bogus",
        ],
        "unknown-argument": [
            "check",
            "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions=" + GATE_VERSIONS_ARG,
            "--repo-root=" + r,
            "--format=json",
            "--bogus-flag",
        ],
        "repo-root-last-no-value": [
            "check",
            "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions=" + GATE_VERSIONS_ARG,
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
def test_usage_errors_return_2(repo_root, case):
    argv = _usage_error_argvs(repo_root)[case]
    assert run_main(argv) == 2