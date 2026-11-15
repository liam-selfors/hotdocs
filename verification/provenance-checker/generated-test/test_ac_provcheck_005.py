import json
from pathlib import Path

import provenance_checker


H = "sha256:" + "ab" * 32

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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

AC_001 = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

AC_002 = """# AC-FOO-002

Covers: R-FOO-002
Kind: llm-judge

```gherkin
Given the foo module
When its documentation is reviewed
Then it explains that foo doubles a number
```
"""


def _write_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — Foo's documentation MUST explain that it doubles a number.\n",
    )
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_001)
    _write(comp / "acceptance" / "AC-FOO-002.md", AC_002)
    _write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")


def _write_fake_dependencies(repo_root: Path) -> None:
    # Stand-ins consistent with the manifest, in case the checker consults
    # the current provenance key. Each matches its documented signature.
    assembler = '''import json
from dataclasses import dataclass, field as _field, fields as _fields


@dataclass
class SpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str = ""
    interface: str = ""
    constraints: str = ""
    dependency_interfaces: dict = _field(default_factory=dict)
    dependency_context: dict = _field(default_factory=dict)
    dependency_usage: dict = _field(default_factory=dict)
    vars: dict = _field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __getitem__(self, key):
        if key not in {f.name for f in _fields(self)}:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return [f.name for f in _fields(self)]


def assemble(component_id, repo_root, mode="cold"):
    return SpecBundle(component_id=component_id, spec_bundle_hash="%s")


def assemble_criterion(component_id, criterion_id, repo_root):
    raise NotImplementedError
''' % H
    _write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", assembler)

    compiler = 'GATE_VERSION = "criterion-compiler@1.0.0"\n'
    _write(repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py", compiler)
    _write(repo_root / "gen" / "criterion-compiler" / "criterion_compiler.py", compiler)
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        'GATE_VERSION = "generated_test@1.0.0"\n',
    )
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        'GATE_VERSION = "verifier-orchestrator@2.0.0"\n',
    )
    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        "def gate_version(repo_root):\n"
        "    return \"license_scanner@4.0.0-no-reference-corpus\"\n",
    )
    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        "def gate_version(repo_root):\n"
        "    return \"secret_scanner@0.0.0\"\n",
    )


def _manifest() -> dict:
    return {
        "spec_bundle_hash": H,
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
                },
                {
                    "id": "AC-FOO-002",
                    "covers": "R-FOO-002",
                    "kind": "llm-judge",
                    "result": "pass",
                    "rationale": "The documentation states that foo doubles a number.",
                },
            ],
            "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
            "interface_drift": False,
            "mutation_score": 0.9,
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
            "gate_version": "secret_scanner@0.0.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }


def test_ac_provcheck_005_llm_judge_hit_honored_when_trust_var_true(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_corpus(repo_root)
    _write_fake_dependencies(repo_root)

    manifest_text = json.dumps(_manifest(), indent=2)
    _write(repo_root / "gen" / "foo" / ".provenance.json", manifest_text)
    _write(repo_root / "verification" / "foo" / ".provenance.json", manifest_text)

    # monkeypatch removes the variable again after the test.
    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "true")

    result = provenance_checker.check_provenance(
        "comp-foo", H, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is True