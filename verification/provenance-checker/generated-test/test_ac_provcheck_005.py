import json
import os
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SPEC_BUNDLE_HASH = "sha256:" + "ab" * 32

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}

VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        {
            "id": "AC-FOO-002",
            "covers": "R-FOO-002",
            "kind": "llm-judge",
            "result": "pass",
            "rationale": "Meets the requirement.",
        },
    ],
    "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "overall": "pass",
}

LICENSE_SCAN = {
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
}

SECRET_SCAN = {
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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root: Path) -> None:
    # Minimal spec corpus for comp-foo, with an llm-judge acceptance criterion,
    # consistent with the manifest's verification_report.
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
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — `foo` MUST be documented clearly.\n",
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
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the foo documentation\n"
        "When a reviewer reads it\n"
        "Then it explains that foo doubles its input\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    manifest = {
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": dict(GATE_VERSIONS),
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": VERIFICATION_REPORT,
        "license_scan": LICENSE_SCAN,
        "secret_scan": SECRET_SCAN,
    }
    text = json.dumps(manifest, indent=2)
    _write(repo_root / "gen" / "foo" / ".provenance.json", text)
    _write(repo_root / "verification" / "foo" / ".provenance.json", text)


def test_ac_provcheck_005_llm_judge_hit_when_trust_judge_true(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    # Precondition: the manifest really carries an llm-judge-kind criterion.
    on_disk = json.loads((repo_root / "gen" / "foo" / ".provenance.json").read_text())
    assert on_disk["spec_bundle_hash"] == SPEC_BUNDLE_HASH
    assert any(c["kind"] == "llm-judge" for c in on_disk["verification_report"]["criteria"])

    # monkeypatch removes/restores the variable after the test.
    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "true")
    assert os.environ["VAR_TRUST_JUDGE_PROVENANCE"] == "true"

    result = provenance_checker.check_provenance(
        "comp-foo", SPEC_BUNDLE_HASH, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is True