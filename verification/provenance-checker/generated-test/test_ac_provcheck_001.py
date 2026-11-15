import json
import copy
from pathlib import Path

import pytest

import provenance_checker


H = "sha256:" + "0123456789abcdef" * 4

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_plain(value):
    if value is None or isinstance(value, (dict, list, str, int, float, bool)):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return value


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    _write(
        repo_root / "specs" / "product" / "P-FOO.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Foo capability\n"
        "\n"
        "Doubling numbers.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-FOO]\n"
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


def _write_fake_dependencies(repo_root: Path) -> None:
    gen = repo_root / "gen"
    _write(
        gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "from dataclasses import dataclass, field, fields\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class SpecBundle:\n"
        "    component_id: str\n"
        "    spec_bundle_hash: str\n"
        "    spec: str\n"
        "    interface: str\n"
        "    constraints: str\n"
        "    dependency_interfaces: dict = field(default_factory=dict)\n"
        "    dependency_context: dict = field(default_factory=dict)\n"
        "    dependency_usage: dict = field(default_factory=dict)\n"
        "    vars: dict = field(default_factory=dict)\n"
        "    glossary: str = \"\"\n"
        "    hint_code: object = None\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        if key not in {f.name for f in fields(self)}:\n"
        "            raise KeyError(key)\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        try:\n"
        "            return self[key]\n"
        "        except KeyError:\n"
        "            return default\n"
        "\n"
        "    def keys(self):\n"
        "        return [f.name for f in fields(self)]\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CriterionBundle:\n"
        "    component_id: str\n"
        "    criterion_id: str\n"
        "    covers: str\n"
        "    criterion_text: str\n"
        "    requirement_text: str\n"
        "    interface: str\n"
        "    glossary: str\n"
        "    dependency_interfaces: dict = field(default_factory=dict)\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key, default)\n"
        "\n"
        "\n"
        f"_HASH = {H!r}\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode=\"cold\"):\n"
        "    return SpecBundle(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash=_HASH,\n"
        "        spec=\"Foo doubles a number.\",\n"
        "        interface=\"foo(x: int) -> int\",\n"
        "        constraints=\"None.\",\n"
        "        glossary=\"- **Foo** — a test term.\",\n"
        "        hint_code=None,\n"
        "    )\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return CriterionBundle(\n"
        "        component_id=component_id,\n"
        "        criterion_id=criterion_id,\n"
        "        covers=\"R-FOO-001\",\n"
        "        criterion_text=\"\",\n"
        "        requirement_text=\"\",\n"
        "        interface=\"\",\n"
        "        glossary=\"\",\n"
        "    )\n",
    )
    compiler_src = 'GATE_VERSION = "criterion-compiler@1.0.0"\n'
    _write(gen / "criterion-compiler" / "criterion_compiler.py", compiler_src)
    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        compiler_src,
    )
    _write(
        gen / "test-author" / "test_author.py",
        'GATE_VERSION = "generated_test@1.0.0"\n',
    )
    _write(
        gen / "verifier-orchestrator" / "verifier_orchestrator.py",
        'GATE_VERSION = "verifier-orchestrator@2.0.0"\n',
    )
    _write(
        gen / "license-scanner" / "license_scanner.py",
        "def gate_version(repo_root):\n"
        '    return "license_scanner@4.0.0-no-reference-corpus"\n',
    )
    _write(
        gen / "secret-scanner" / "secret_scanner.py",
        "def gate_version(repo_root):\n"
        '    return "secret_scanner@3.1.0+detect-secrets.1.5.0"\n',
    )


def _manifest() -> dict:
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "generated-test",
                "result": "pass",
                "test_authoring": {
                    "model": "claude-sonnet-5",
                    "seed": 0,
                    "prompt_version": "v1",
                    "cache_hit": False,
                },
            },
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {
                    "message": "result.foo equals 5 failed",
                    "expected": 5,
                    "actual": 3,
                },
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.87,
        "overall": "fail",
    }
    license_scan = {
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
        "cache_hit": True,
    }
    secret_scan = {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": True,
        "matches": [
            {
                "rule_id": "AWS Access Key",
                "risk_tier": "high",
                "file": "gen/foo/config.py",
                "line": 12,
            }
        ],
        "allowed": [
            {"rule_id": "Hex High Entropy String", "file": "verification/foo/test_x.py", "line": 3}
        ],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    return {
        "spec_bundle_hash": H,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": dict(GATE_VERSIONS),
        "provenance_hit": False,
        "generated_at": "2026-11-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


def test_ac_provcheck_001_hash_match_without_llm_judge_is_verbatim_hit(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_corpus(repo_root)
    _write_fake_dependencies(repo_root)

    manifest = _manifest()
    # No llm-judge-kind criterion anywhere in the committed report.
    assert all(c["kind"] != "llm-judge" for c in manifest["verification_report"]["criteria"])
    committed = copy.deepcopy(manifest)

    text = json.dumps(manifest, indent=2, sort_keys=True)
    _write(repo_root / "gen" / "foo" / ".provenance.json", text)
    _write(repo_root / "verification" / "foo" / ".provenance.json", text)

    # The trust variable only governs llm-judge criteria; with none present,
    # a hash match is honored unconditionally, even when it is false.
    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "false")
    monkeypatch.chdir(repo_root)

    result = provenance_checker.check_provenance(
        "comp-foo", H, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is True
    assert as_plain(field(result, "verification_report")) == committed["verification_report"]
    assert as_plain(field(result, "license_scan")) == committed["license_scan"]
    assert as_plain(field(result, "secret_scan")) == committed["secret_scan"]

    # The committed manifest itself is untouched by the check.
    on_disk = json.loads((repo_root / "gen" / "foo" / ".provenance.json").read_text(encoding="utf-8"))
    assert on_disk == committed