import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}

STORED_HASH = "sha256:" + "a" * 64
OTHER_HASH = "sha256:" + "b" * 64


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
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
        "# R-FOO-001\n\n**R-FOO-001** — `double_it(x)` MUST return `2 * x`.\n",
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
        "When double_it(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble_it(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def _manifest() -> dict:
    return {
        "spec_bundle_hash": STORED_HASH,
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


def test_ac_provcheck_002_hash_mismatch_is_definitive_miss(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    manifest_text = json.dumps(_manifest(), indent=2)
    _write(repo_root / "gen" / "foo" / ".provenance.json", manifest_text)
    _write(repo_root / "verification" / "foo" / ".provenance.json", manifest_text)
    assert (repo_root / "gen" / "foo" / ".provenance.json").is_file()

    result = provenance_checker.check_provenance(
        "comp-foo", OTHER_HASH, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is False
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None