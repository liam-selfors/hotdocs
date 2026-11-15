import json
from pathlib import Path

import pytest

import provenance_checker


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}

SPEC_BUNDLE_HASHES = [
    "sha256:" + "0" * 64,
    "sha256:" + "0123456789abcdef" * 4,
    "sha256:abc",
    "sha256:" + "f" * 64,
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")


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
            "component_id": "comp-bar",
            "criteria": [],
            "requirement_results": {},
            "interface_drift": False,
            "mutation_score": None,
            "overall": "pass",
        },
        "license_scan": {
            "component_id": "comp-bar",
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
    # A miss is never partial: no manifest-derived field is populated.
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None


@pytest.mark.parametrize("spec_bundle_hash", SPEC_BUNDLE_HASHES)
@pytest.mark.parametrize("gen_dir_exists", [False, True])
def test_missing_provenance_manifest_is_a_miss(
    tmp_path, monkeypatch, spec_bundle_hash, gen_dir_exists
):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    gen_foo = repo_root / "gen" / "foo"
    if gen_dir_exists:
        gen_foo.mkdir(parents=True)
        # Unrelated file present, but no manifest.
        _write(gen_foo / "foo.py", "def foo(x):\n    return 2 * x\n")

    manifest_path = gen_foo / ".provenance.json"
    assert not manifest_path.exists()

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, dict(GATE_VERSIONS), repo_root
    )

    _assert_definitive_miss(result)
    # Read-only: the checker must not create the manifest.
    assert not manifest_path.exists()


@pytest.mark.parametrize("spec_bundle_hash", SPEC_BUNDLE_HASHES)
def test_missing_manifest_is_a_miss_even_when_other_components_have_matching_ones(
    tmp_path, monkeypatch, spec_bundle_hash
):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    # Another component's manifest matches the supplied hash and gate versions
    # exactly; it must not be consulted for comp-foo.
    _write(
        repo_root / "gen" / "bar" / ".provenance.json",
        json.dumps(_matching_manifest(spec_bundle_hash), indent=2),
    )

    assert not (repo_root / "gen" / "foo" / ".provenance.json").exists()

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, dict(GATE_VERSIONS), repo_root
    )

    _assert_definitive_miss(result)