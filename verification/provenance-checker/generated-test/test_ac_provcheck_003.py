"""AC-PROVCHECK-003: an absent gen/<slug>/.provenance.json is a definitive miss.

Given gen/foo/.provenance.json does not exist
When check_provenance is called for comp-foo with any spec_bundle_hash
Then the result's hit is false
"""

import json
from pathlib import Path

import pytest

import provenance_checker


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
}

HASHES = [
    "sha256:" + "0" * 64,
    "sha256:" + "0123456789abcdef" * 4,
    "sha256:abc",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: true
source_path: legacy/foo/
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
"""


def _write_fixture(repo_root: Path) -> None:
    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n"
    )
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True, exist_ok=True)
    (comp / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp / "interface").mkdir(parents=True, exist_ok=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n"
    )
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo(x: int) -> int\n```\n"
    )
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n")


def _matching_manifest(spec_bundle_hash: str) -> dict:
    return {
        "spec_bundle_hash": spec_bundle_hash,
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
                    "kind": "generated-test",
                    "result": "pass",
                }
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": "pass",
        },
        "license_scan": {
            "component_id": "comp-foo",
            "gate_version": GATE_VERSIONS["license_scanner"],
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
            "gate_version": GATE_VERSIONS["secret_scanner"],
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }


def _assert_definitive_miss(result):
    assert field(result, "hit") is False
    # A miss is never partial: nothing from any manifest is carried.
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)


@pytest.mark.parametrize("spec_bundle_hash", HASHES)
def test_no_gen_directory_is_miss(tmp_path, spec_bundle_hash):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)
    assert not (repo_root / "gen" / "foo" / ".provenance.json").exists()

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, dict(GATE_VERSIONS), repo_root
    )

    _assert_definitive_miss(result)


@pytest.mark.parametrize("spec_bundle_hash", HASHES)
def test_gen_directory_without_manifest_is_miss(tmp_path, spec_bundle_hash):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)
    gen_foo = repo_root / "gen" / "foo"
    gen_foo.mkdir(parents=True)
    (gen_foo / "foo.py").write_text("def foo(x):\n    return 2 * x\n")
    assert not (gen_foo / ".provenance.json").exists()

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, dict(GATE_VERSIONS), repo_root
    )

    _assert_definitive_miss(result)


@pytest.mark.parametrize("spec_bundle_hash", HASHES)
def test_matching_manifests_elsewhere_do_not_substitute(tmp_path, spec_bundle_hash):
    """Only gen/foo/.provenance.json counts; matching manifests at other
    locations (verification/foo/, or a wrongly unstripped gen/comp-foo/)
    must not turn the absent one into a hit."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)
    (repo_root / "gen" / "foo").mkdir(parents=True)
    manifest = json.dumps(_matching_manifest(spec_bundle_hash), indent=2)
    for decoy_dir in (
        repo_root / "verification" / "foo",
        repo_root / "gen" / "comp-foo",
    ):
        decoy_dir.mkdir(parents=True, exist_ok=True)
        (decoy_dir / ".provenance.json").write_text(manifest)
    assert not (repo_root / "gen" / "foo" / ".provenance.json").exists()

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, dict(GATE_VERSIONS), repo_root
    )

    _assert_definitive_miss(result)