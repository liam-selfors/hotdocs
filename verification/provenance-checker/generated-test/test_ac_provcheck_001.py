# hotdocs-criterion: sha256:03147777f6d908bff63f2716b4ffcb80c1577f70ddc0fa4589104513fde371ca
import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_plain(value):
    if value is None or isinstance(value, (dict, list, str, int, float, bool)):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return value


SPEC_HASH = "sha256:" + "ab12" * 16

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.1.0",
    "verifier": "verifier-orchestrator@2.2.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}

VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
    "interface_drift": False,
    "mutation_score": 0.87,
    "mutation_error": None,
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** \u2014 a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    write(
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
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    write(
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
    write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")


def build_manifest():
    return {
        "spec_bundle_hash": SPEC_HASH,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": dict(GATE_VERSIONS),
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": json.loads(json.dumps(VERIFICATION_REPORT)),
        "license_scan": json.loads(json.dumps(LICENSE_SCAN)),
        "secret_scan": json.loads(json.dumps(SECRET_SCAN)),
    }


def test_hash_match_without_llm_judge_is_verbatim_hit(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    manifest = build_manifest()
    text = json.dumps(manifest, indent=2)
    write(repo_root / "gen" / "foo" / ".provenance.json", text)
    write(repo_root / "verification" / "foo" / ".provenance.json", text)

    # No llm-judge criteria: the hit must be honored unconditionally,
    # even with the trust variable explicitly false.
    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "false")
    monkeypatch.chdir(repo_root)

    result = provenance_checker.check_provenance(
        "comp-foo", SPEC_HASH, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is True

    committed = json.loads((repo_root / "gen" / "foo" / ".provenance.json").read_text(encoding="utf-8"))

    assert as_plain(field(result, "verification_report")) == committed["verification_report"]
    assert as_plain(field(result, "license_scan")) == committed["license_scan"]
    assert as_plain(field(result, "secret_scan")) == committed["secret_scan"]

    # The committed manifest is untouched by the check.
    assert committed == manifest