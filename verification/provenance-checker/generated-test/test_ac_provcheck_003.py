# hotdocs-criterion: sha256:16473e0504854a6e3d53b498c3695c66ec774b590f048dc3b15275c0086f5d5a
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_corpus(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        + "\n"
        + "- **Foo** \u2014 a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "depends_on: []\n"
        + "---\n"
        + "\n"
        + "# Foo\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "Foo doubles a number.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        + "\n"
        + "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        + "\n"
        + "Covers: R-FOO-001\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given x = 2\n"
        + "When foo(x) is called\n"
        + "Then it returns 4\n"
        + "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        + "\n"
        + "```\n"
        + "foo(x: int) -> int\n"
        + "```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n" + "\n" + "None.\n")


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.1.0",
    "verifier": "verifier-orchestrator@2.2.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}

HASHES = [
    "sha256:" + "0" * 64,
    "sha256:" + "0123456789abcdef" * 4,
    "sha256:deadbeef",
]


def _assert_miss(result):
    assert field(result, "hit") is False
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None


@pytest.mark.parametrize("spec_bundle_hash", HASHES)
def test_missing_manifest_with_gen_dir_is_miss(tmp_path, monkeypatch, spec_bundle_hash):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    (repo_root / "gen" / "foo").mkdir(parents=True)
    assert not (repo_root / "gen" / "foo" / ".provenance.json").exists()

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, dict(GATE_VERSIONS), repo_root
    )
    _assert_miss(result)


@pytest.mark.parametrize("spec_bundle_hash", HASHES)
def test_missing_manifest_without_gen_dir_is_miss(tmp_path, monkeypatch, spec_bundle_hash):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    assert not (repo_root / "gen" / "foo" / ".provenance.json").exists()

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, dict(GATE_VERSIONS), repo_root
    )
    _assert_miss(result)


def test_missing_manifest_is_miss_even_with_other_component_manifest(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    (repo_root / "gen" / "foo").mkdir(parents=True)
    # A manifest elsewhere (verification/foo/) must not count as gen/foo's.
    import json

    spec_bundle_hash = "sha256:" + "a" * 64
    manifest = {
        "spec_bundle_hash": spec_bundle_hash,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": dict(GATE_VERSIONS),
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": {"component_id": "comp-foo", "criteria": [], "overall": "pass"},
        "license_scan": {"component_id": "comp-foo", "blocked": False},
        "secret_scan": {"scope": "full", "flagged": False},
    }
    _write(repo_root / "verification" / "foo" / ".provenance.json", json.dumps(manifest))
    assert not (repo_root / "gen" / "foo" / ".provenance.json").exists()

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, dict(GATE_VERSIONS), repo_root
    )
    _assert_miss(result)