# hotdocs-criterion: sha256:d0acff4882d39012d0a88bccea12263cec1cf6cc5d7dc7f4279cb47ed8deda6f
import json
import os
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


MANIFEST_HASH = "sha256:" + "a1" * 32
ASSEMBLER_HASH = "sha256:" + "b2" * 32
OTHER_HASH = "sha256:" + "c3" * 32

CALLER_GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.1.0",
    "verifier": "verifier-orchestrator@2.2.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}

VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
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


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_prelude():
    return (
        "import os\n"
        "def _log(line):\n"
        "    p = os.environ.get('PROVCHECK_AC007_LOG')\n"
        "    if p:\n"
        "        with open(p, 'a', encoding='utf-8') as fh:\n"
        "            fh.write(line + '\\n')\n"
    )


def _write_fakes(repo_root):
    gen = repo_root / "gen"
    _write(
        gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        _log_prelude()
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        + "    _log('assemble ' + str(component_id))\n"
        + "    return {\n"
        + "        'component_id': component_id,\n"
        + "        'spec_bundle_hash': " + repr(ASSEMBLER_HASH) + ",\n"
        + "        'spec': '',\n"
        + "        'interface': '',\n"
        + "        'constraints': '',\n"
        + "        'dependency_interfaces': {},\n"
        + "        'dependency_context': {},\n"
        + "        'dependency_usage': {},\n"
        + "        'vars': {},\n"
        + "        'glossary': '',\n"
        + "        'hint_code': None,\n"
        + "    }\n"
        + "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        + "    _log('assemble_criterion ' + str(component_id))\n"
        + "    return {\n"
        + "        'component_id': component_id,\n"
        + "        'criterion_id': criterion_id,\n"
        + "        'covers': '',\n"
        + "        'criterion_text': '',\n"
        + "        'requirement_text': '',\n"
        + "        'interface': '',\n"
        + "        'glossary': '',\n"
        + "        'dependency_interfaces': {},\n"
        + "    }\n",
    )
    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "GATE_VERSION = " + repr("criterion-compiler@9.9.9") + "\n",
    )
    _write(
        gen / "test-author" / "test_author.py",
        "GATE_VERSION = " + repr("generated_test@9.9.9") + "\n",
    )
    _write(
        gen / "verifier-orchestrator" / "verifier_orchestrator.py",
        "GATE_VERSION = " + repr("verifier-orchestrator@9.9.9") + "\n",
    )
    _write(
        gen / "license-scanner" / "license_scanner.py",
        _log_prelude()
        + "def gate_version(repo_root):\n"
        + "    _log('license_scanner.gate_version')\n"
        + "    return " + repr("license_scanner@4.0.9+ffffffffffff") + "\n",
    )
    _write(
        gen / "secret-scanner" / "secret_scanner.py",
        _log_prelude()
        + "def gate_version(repo_root):\n"
        + "    _log('secret_scanner.gate_version')\n"
        + "    return " + repr("secret_scanner@9.9.9+detect-secrets.1.5.0") + "\n",
    )


def _write_manifest(repo_root):
    manifest = {
        "spec_bundle_hash": MANIFEST_HASH,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": dict(CALLER_GATE_VERSIONS),
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": VERIFICATION_REPORT,
        "license_scan": LICENSE_SCAN,
        "secret_scan": SECRET_SCAN,
    }
    _write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest, indent=2))


def test_comparison_uses_caller_supplied_hash_never_its_own(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("PROVCHECK_AC007_LOG", str(log_path))
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)

    _write_fakes(repo_root)
    _write_manifest(repo_root)

    # Caller supplies exactly the manifest's hash H: a hit, even though any
    # self-computed hash (the fake assembler's) would differ from H.
    hit_result = provenance_checker.check_provenance(
        "comp-foo", MANIFEST_HASH, dict(CALLER_GATE_VERSIONS), repo_root
    )
    assert field(hit_result, "hit") is True
    assert field(hit_result, "verification_report") == VERIFICATION_REPORT
    assert field(hit_result, "license_scan") == LICENSE_SCAN
    assert field(hit_result, "secret_scan") == SECRET_SCAN

    # Caller supplies the hash a self-computation would produce: still a miss,
    # because only the manifest's own field is compared against.
    assembler_result = provenance_checker.check_provenance(
        "comp-foo", ASSEMBLER_HASH, dict(CALLER_GATE_VERSIONS), repo_root
    )
    assert field(assembler_result, "hit") is False
    assert field(assembler_result, "verification_report") is None
    assert field(assembler_result, "license_scan") is None
    assert field(assembler_result, "secret_scan") is None

    # Any other caller-supplied hash differing from H: a miss.
    other_result = provenance_checker.check_provenance(
        "comp-foo", OTHER_HASH, dict(CALLER_GATE_VERSIONS), repo_root
    )
    assert field(other_result, "hit") is False
    assert field(other_result, "verification_report") is None
    assert field(other_result, "license_scan") is None
    assert field(other_result, "secret_scan") is None

    # check_provenance never computed a hash or gate version of its own.
    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert calls == []

    # The manifest was left untouched.
    on_disk = json.loads((repo_root / "gen" / "foo" / ".provenance.json").read_text(encoding="utf-8"))
    assert on_disk["spec_bundle_hash"] == MANIFEST_HASH