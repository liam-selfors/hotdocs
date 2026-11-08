import json

import pytest

import provenance_checker


def _write_manifest(repo_root):
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "spec_bundle_hash": "sha256:0a1b",
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": {"license_scanner": "1"},
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
            "gate_version": "license_scanner@4.0.0-no-reference-corpus",
            "evaluated": False,
            "reason": "no-reference-corpus",
            "similarity_score": None,
            "block_threshold": None,
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
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest))


@pytest.fixture
def repo_root(tmp_path):
    _write_manifest(tmp_path)
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

    exit_code = provenance_checker.main(argv)

    assert exit_code == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["hit"] is True


def test_miss_returns_zero_and_text_contains_miss(repo_root, capsys):
    argv = [
        "check",
        "comp-foo",
        "--spec-bundle-hash",
        "sha256:ffff",
        "--gate-versions",
        '{"license_scanner": "1"}',
        "--repo-root",
        str(repo_root),
        "--format",
        "text",
    ]

    exit_code = provenance_checker.main(argv)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "miss" in captured.out


def _missing_spec_bundle_hash(repo_root):
    return [
        "check",
        "comp-foo",
        '--gate-versions={"license_scanner": "1"}',
        f"--repo-root={repo_root}",
        "--format=json",
    ]


def _spec_bundle_hash_without_prefix(repo_root):
    return [
        "check",
        "comp-foo",
        "--spec-bundle-hash=0a1b",
        '--gate-versions={"license_scanner": "1"}',
        f"--repo-root={repo_root}",
        "--format=json",
    ]


def _gate_versions_not_an_object(repo_root):
    return [
        "check",
        "comp-foo",
        "--spec-bundle-hash=sha256:0a1b",
        "--gate-versions",
        "[1]",
        f"--repo-root={repo_root}",
        "--format=json",
    ]


def _invalid_format(repo_root):
    return [
        "check",
        "comp-foo",
        "--spec-bundle-hash=sha256:0a1b",
        '--gate-versions={"license_scanner": "1"}',
        f"--repo-root={repo_root}",
        "--format=bogus",
    ]


def _unknown_argument(repo_root):
    return [
        "check",
        "comp-foo",
        "--spec-bundle-hash=sha256:0a1b",
        '--gate-versions={"license_scanner": "1"}',
        f"--repo-root={repo_root}",
        "--unknown-flag=1",
    ]


def _repo_root_last_with_no_value(repo_root):
    return [
        "check",
        "comp-foo",
        "--spec-bundle-hash=sha256:0a1b",
        '--gate-versions={"license_scanner": "1"}',
        "--repo-root",
    ]


@pytest.mark.parametrize(
    "argv_builder",
    [
        _missing_spec_bundle_hash,
        _spec_bundle_hash_without_prefix,
        _gate_versions_not_an_object,
        _invalid_format,
        _unknown_argument,
        _repo_root_last_with_no_value,
    ],
)
def test_usage_errors_return_two(repo_root, argv_builder):
    argv = argv_builder(repo_root)

    exit_code = provenance_checker.main(argv)

    assert exit_code == 2