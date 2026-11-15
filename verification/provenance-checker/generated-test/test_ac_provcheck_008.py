"""AC-PROVCHECK-008 (Covers: R-PROVCHECK-001).

Given gen/foo/.provenance.json exists with spec_bundle_hash H and
gate_versions {"license_scanner": "1.0.0"}, but the caller's current
gate_versions is {"license_scanner": "2.0.0"}
When check_provenance is called for comp-foo with spec_bundle_hash H
Then the result's hit is false, even though spec_bundle_hash matches
"""

import json
from pathlib import Path

import provenance_checker


H = "sha256:" + "ab" * 32


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_spec_corpus(repo_root: Path) -> None:
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


def _manifest(spec_bundle_hash: str, gate_versions: dict) -> dict:
    return {
        "spec_bundle_hash": spec_bundle_hash,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": gate_versions,
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


def test_gate_version_mismatch_is_miss_even_when_spec_bundle_hash_matches(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_spec_corpus(repo_root)

    manifest = _manifest(H, {"license_scanner": "1.0.0"})
    text = json.dumps(manifest, indent=2)
    _write(repo_root / "gen" / "foo" / ".provenance.json", text)
    _write(repo_root / "verification" / "foo" / ".provenance.json", text)

    result = provenance_checker.check_provenance(
        "comp-foo",
        H,
        {"license_scanner": "2.0.0"},
        repo_root,
    )

    # spec_bundle_hash matches the manifest exactly...
    on_disk = json.loads(
        (repo_root / "gen" / "foo" / ".provenance.json").read_text(encoding="utf-8")
    )
    assert on_disk["spec_bundle_hash"] == H

    # ...but the gate version differs, so this must be a miss.
    assert field(result, "hit") is False