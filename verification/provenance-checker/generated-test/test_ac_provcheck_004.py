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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _plant_fake_dependencies(repo_root: Path) -> None:
    # spec-bundle-assembler: assemble() returns a SpecBundle-shaped object
    # (attribute and read-only mapping access) whose spec_bundle_hash is H.
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        '''from dataclasses import dataclass, field as dc_field


@dataclass
class SpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dc_field(default_factory=dict)
    dependency_context: dict = dc_field(default_factory=dict)
    dependency_usage: dict = dc_field(default_factory=dict)
    vars: dict = dc_field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return list(self.__dataclass_fields__.keys())


@dataclass
class CriterionBundle:
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = dc_field(default_factory=dict)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def assemble(component_id, repo_root, mode="cold"):
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="''' + H + '''",
        spec="",
        interface="",
        constraints="",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="",
        criterion_text="",
        requirement_text="",
        interface="",
        glossary="",
    )
''',
    )

    compiler_src = 'GATE_VERSION = "criterion-compiler@1.0.0"\n'
    # Sealed criterion-compiler lives at its source_path; also plant under gen/
    # in case a loader looks there.
    _write(repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py", compiler_src)
    _write(repo_root / "gen" / "criterion-compiler" / "criterion_compiler.py", compiler_src)

    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        'GATE_VERSION = "generated_test@1.0.0"\n'
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    raise RuntimeError('not used in this test')\n",
    )
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        'GATE_VERSION = "verifier-orchestrator@2.0.0"\n'
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    raise RuntimeError('not used in this test')\n",
    )
    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        "def gate_version(repo_root):\n"
        '    return "license_scanner@4.0.0-no-reference-corpus"\n'
        "\n"
        "def scan(component_id, repo_root):\n"
        "    raise RuntimeError('not used in this test')\n",
    )
    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        "def gate_version(repo_root):\n"
        '    return "secret_scanner@3.1.0+detect-secrets.1.5.0"\n'
        "\n"
        "def scan(repo_root):\n"
        "    raise RuntimeError('not used in this test')\n",
    )


def _write_component(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
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
                    "kind": "compiled",
                    "result": "pass",
                },
                {
                    "id": "AC-FOO-002",
                    "covers": "R-FOO-002",
                    "kind": "llm-judge",
                    "result": "pass",
                    "rationale": "The implementation satisfies the criterion.",
                },
            ],
            "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
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


def test_ac_provcheck_004_llm_judge_manifest_is_miss_when_trust_disabled(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _plant_fake_dependencies(repo_root)
    _write_component(repo_root)

    manifest_path = repo_root / "gen" / "foo" / ".provenance.json"
    _write(manifest_path, json.dumps(_manifest(), indent=2))

    # VAR-TRUST-JUDGE-PROVENANCE is false; monkeypatch removes it afterwards.
    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "false")

    result = provenance_checker.check_provenance(
        "comp-foo", H, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is False

    # A miss is definitive: nothing from the manifest is carried over.
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None