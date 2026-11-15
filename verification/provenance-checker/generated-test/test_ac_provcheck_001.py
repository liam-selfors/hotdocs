import copy
import json
from pathlib import Path

import pytest

import provenance_checker


H = "sha256:" + "ab" * 32

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
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
    "interface_drift": False,
    "mutation_score": 0.87,
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_plain(value):
    if value is None or isinstance(value, (dict, list, str, int, float, bool)):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    import dataclasses

    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    return value


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


ASSEMBLER_FAKE = '''import dataclasses


@dataclasses.dataclass
class SpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    dependency_context: dict = dataclasses.field(default_factory=dict)
    dependency_usage: dict = dataclasses.field(default_factory=dict)
    vars: dict = dataclasses.field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def assemble(component_id, repo_root, mode="cold"):
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="''' + H + '''",
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    raise NotImplementedError
'''

COMPILER_FAKE = 'GATE_VERSION = "criterion-compiler@1.0.0"\n'
TEST_AUTHOR_FAKE = 'GATE_VERSION = "generated_test@1.0.0"\n'
VERIFIER_FAKE = 'GATE_VERSION = "verifier-orchestrator@2.0.0"\n'
LICENSE_FAKE = (
    "def gate_version(repo_root):\n"
    "    return \"license_scanner@4.0.0-no-reference-corpus\"\n"
)
SECRET_FAKE = (
    "def gate_version(repo_root):\n"
    "    return \"secret_scanner@3.1.0+detect-secrets.1.5.0\"\n"
)

COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
"""


def _build_repo(repo_root: Path) -> dict:
    # Minimal spec corpus for comp-foo (no llm-judge criteria at all).
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** \u2014 a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n",
    )
    _write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # Stand-in dependencies, so any current-key derivation agrees with H.
    _write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", ASSEMBLER_FAKE)
    _write(repo_root / "gen" / "criterion-compiler" / "criterion_compiler.py", COMPILER_FAKE)
    _write(repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py", COMPILER_FAKE)
    _write(repo_root / "gen" / "test-author" / "test_author.py", TEST_AUTHOR_FAKE)
    _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", VERIFIER_FAKE)
    _write(repo_root / "gen" / "license-scanner" / "license_scanner.py", LICENSE_FAKE)
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", SECRET_FAKE)

    manifest = {
        "spec_bundle_hash": H,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": dict(GATE_VERSIONS),
        "provenance_hit": False,
        "generated_at": "2026-11-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": copy.deepcopy(VERIFICATION_REPORT),
        "license_scan": copy.deepcopy(LICENSE_SCAN),
        "secret_scan": copy.deepcopy(SECRET_SCAN),
    }
    text = json.dumps(manifest, indent=2)
    _write(repo_root / "gen" / "foo" / ".provenance.json", text)
    _write(repo_root / "verification" / "foo" / ".provenance.json", text)
    _write(repo_root / "gen" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")
    return manifest


@pytest.mark.parametrize("trust_var", [None, "false", "true"])
def test_hash_match_without_llm_judge_is_verbatim_hit(tmp_path, monkeypatch, trust_var):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    manifest = _build_repo(repo_root)

    # The variable governs only llm-judge criteria; with none present the
    # hit is honored unconditionally, whatever it resolves to.
    if trust_var is None:
        monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    else:
        monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", trust_var)
    monkeypatch.chdir(repo_root)

    # Sanity: the committed manifest truly has no llm-judge-kind criteria.
    assert all(c["kind"] != "llm-judge" for c in manifest["verification_report"]["criteria"])

    result = provenance_checker.check_provenance(
        "comp-foo", H, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is True

    committed = json.loads(
        (repo_root / "gen" / "foo" / ".provenance.json").read_text(encoding="utf-8")
    )
    assert as_plain(field(result, "verification_report")) == committed["verification_report"]
    assert as_plain(field(result, "license_scan")) == committed["license_scan"]
    assert as_plain(field(result, "secret_scan")) == committed["secret_scan"]

    # Verbatim, never recomputed or summarized: exactly the original values.
    assert as_plain(field(result, "verification_report")) == VERIFICATION_REPORT
    assert as_plain(field(result, "license_scan")) == LICENSE_SCAN
    assert as_plain(field(result, "secret_scan")) == SECRET_SCAN