import json
import os
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


H = "sha256:" + "a" * 64
OTHER_H = "sha256:" + "b" * 64
ASSEMBLER_H = "sha256:" + "c" * 64

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }


def _license_scan():
    return {
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


def _secret_scan():
    return {
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


def _write_manifest(repo_root: Path):
    manifest = {
        "spec_bundle_hash": H,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": dict(GATE_VERSIONS),
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": _verification_report(),
        "license_scan": _license_scan(),
        "secret_scan": _secret_scan(),
    }
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def _write_fake_assembler(repo_root: Path, log_path: Path):
    # A fake spec-bundle-assembler that records any invocation and returns
    # a hash different from the manifest's, so a target that computed its
    # own spec_bundle_hash would be detectable both via the log and via
    # a wrong hit/miss outcome.
    d = repo_root / "gen" / "spec-bundle-assembler"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "from dataclasses import dataclass, field\n"
        "\n"
        f"_LOG = {str(log_path)!r}\n"
        f"_HASH = {ASSEMBLER_H!r}\n"
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
        "    glossary: str = ''\n"
        "    hint_code: object = None\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key, default)\n"
        "\n"
        "def _log(name, payload):\n"
        "    with open(_LOG, 'a') as f:\n"
        "        f.write(json.dumps({'fn': name, 'args': payload}) + '\\n')\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', [str(component_id), str(repo_root), str(mode)])\n"
        "    return SpecBundle(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash=_HASH,\n"
        "        spec='', interface='', constraints='',\n"
        "    )\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', [str(component_id), str(criterion_id), str(repo_root)])\n"
        "    raise RuntimeError('not expected')\n"
    )
    (d / "spec_bundle_assembler.py").write_text(src)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "assembler_invocations.log"
    _write_manifest(repo_root)
    _write_fake_assembler(repo_root, log_path)
    return repo_root, log_path


def test_caller_supplied_hash_matching_manifest_is_a_hit(repo):
    repo_root, log_path = repo
    result = provenance_checker.check_provenance(
        "comp-foo", H, dict(GATE_VERSIONS), repo_root
    )
    assert field(result, "hit") is True
    # The target never computed a spec_bundle_hash of its own.
    assert not log_path.exists(), log_path.read_text() if log_path.exists() else ""


def test_caller_supplied_hash_differing_from_manifest_is_a_miss(repo):
    repo_root, log_path = repo
    result = provenance_checker.check_provenance(
        "comp-foo", OTHER_H, dict(GATE_VERSIONS), repo_root
    )
    assert field(result, "hit") is False
    assert not log_path.exists(), log_path.read_text() if log_path.exists() else ""


def test_comparison_is_against_manifest_field_not_a_computed_hash(repo):
    repo_root, log_path = repo
    # Supplying exactly what an assembler would compute must not produce a
    # hit: the comparison is against the manifest's own spec_bundle_hash (H).
    result = provenance_checker.check_provenance(
        "comp-foo", ASSEMBLER_H, dict(GATE_VERSIONS), repo_root
    )
    assert field(result, "hit") is False

    # And supplying H gives a hit even though any computed hash would be
    # ASSEMBLER_H: the caller-supplied value is used exactly.
    result2 = provenance_checker.check_provenance(
        "comp-foo", H, dict(GATE_VERSIONS), repo_root
    )
    assert field(result2, "hit") is True

    assert not log_path.exists(), log_path.read_text() if log_path.exists() else ""