# hotdocs-criterion: sha256:08c16780d171af72a0986a4470da16dff5997e78006e45ce4339d003e32d827c
import json
import os
from pathlib import Path

import provenance_checker


ENV_NAME = "VAR_TRUST_JUDGE_PROVENANCE"

SPEC_BUNDLE_HASH = "sha256:" + "ab12" * 16

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.1.0",
    "verifier": "verifier-orchestrator@2.2.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
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
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
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


def _manifest():
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "llm-judge",
                "result": "pass",
                "rationale": "The implementation doubles its input.",
            }
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "overall": "pass",
    }
    license_scan = {
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
    }
    secret_scan = {
        "scope": "full",
        "gate_version": GATE_VERSIONS["secret_scanner"],
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    return {
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": dict(GATE_VERSIONS),
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


def test_llm_judge_criterion_without_trust_is_a_miss(tmp_path):
    repo_root = Path(tmp_path)
    _build_corpus(repo_root)

    manifest_text = json.dumps(_manifest(), indent=2)
    _write(repo_root / "gen" / "foo" / ".provenance.json", manifest_text)
    _write(repo_root / "verification" / "foo" / ".provenance.json", manifest_text)

    os.environ[ENV_NAME] = "false"
    try:
        result = provenance_checker.check_provenance(
            "comp-foo", SPEC_BUNDLE_HASH, dict(GATE_VERSIONS), repo_root
        )
    finally:
        os.environ.pop(ENV_NAME, None)

    assert field(result, "hit") is False
    # A definitive miss carries no partial or best-guess values.
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None