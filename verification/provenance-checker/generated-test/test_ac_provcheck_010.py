import json

import pytest

import provenance_checker


VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.92,
    "overall": "pass",
}

LICENSE_SCAN = {
    "component_id": "comp-foo",
    "gate_version": "license_scanner@4.0.3",
    "evaluated": True,
    "reason": None,
    "similarity_score": 0.0,
    "block_threshold": 0.70,
    "blocked": False,
    "matches": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

PROVENANCE_MANIFEST = {
    "spec_bundle_hash": "sha256:0a1b",
    "model_pin": "claude-sonnet-5",
    "prompt_version": "v1",
    "retry_feedback": None,
    "pipeline_version": "v1",
    "gate_versions": {"license_scanner": "1"},
    "provenance_hit": False,
    "generated_at": "2026-01-01T00:00:00Z",
    "verification_run_id": "run-123",
    "verification_report": VERIFICATION_REPORT,
    "license_scan": LICENSE_SCAN,
    "secret_scan": SECRET_SCAN,
}


@pytest.fixture
def repo_root(tmp_path):
    gen_dir = tmp_path / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    (gen_dir / ".provenance.json").write_text(json.dumps(PROVENANCE_MANIFEST))
    return tmp_path


def test_hit_returns_zero_and_json_hit_true(repo_root, capsys):
    argv = [
        "check",
        "comp-foo",
        "--spec-bundle-hash=sha256:0a1b",
        '--gate-versions={"license_scanner": "1"}',
        f"--repo-root={repo_root}",
        "--format=json",
    ]

    rc = provenance_checker.main(argv)

    assert rc == 0
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result["hit"] is True


def test_miss_returns_zero_and_text_contains_miss(repo_root, capsys):
    argv = [
        "check",
        "comp-foo",
        "--spec-bundle-hash", "sha256:ffff",
        "--gate-versions", '{"license_scanner": "1"}',
        "--repo-root", str(repo_root),
        "--format", "text",
    ]

    rc = provenance_checker.main(argv)

    assert rc == 0
    out = capsys.readouterr().out
    assert "miss" in out


@pytest.mark.parametrize(
    "argv_suffix",
    [
        # missing --spec-bundle-hash
        [
            "--gate-versions", '{"license_scanner": "1"}',
        ],
        # --spec-bundle-hash with no sha256: prefix
        [
            "--spec-bundle-hash=0a1b",
            "--gate-versions", '{"license_scanner": "1"}',
        ],
        # --gate-versions not a JSON object of strings
        [
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions", "[1]",
        ],
        # invalid --format
        [
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions", '{"license_scanner": "1"}',
            "--format=bogus",
        ],
        # unknown argument
        [
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions", '{"license_scanner": "1"}',
            "--totally-unknown-flag",
        ],
    ],
    ids=[
        "missing-spec-bundle-hash",
        "spec-bundle-hash-no-prefix",
        "gate-versions-not-object",
        "invalid-format",
        "unknown-argument",
    ],
)
def test_usage_errors_return_two(repo_root, argv_suffix):
    argv = ["check", "comp-foo"] + argv_suffix + ["--repo-root", str(repo_root)]

    rc = provenance_checker.main(argv)

    assert rc == 2


def test_repo_root_last_with_no_value_returns_two(repo_root):
    argv = [
        "check",
        "comp-foo",
        "--spec-bundle-hash=sha256:0a1b",
        "--gate-versions", '{"license_scanner": "1"}',
        "--repo-root",
    ]

    rc = provenance_checker.main(argv)

    assert rc == 2