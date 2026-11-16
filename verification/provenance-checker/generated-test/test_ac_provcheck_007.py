import json
import os
from pathlib import Path

import pytest

import provenance_checker


H = "sha256:" + "a" * 64
H_OTHER = "sha256:" + "b" * 64

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
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "overall": "pass",
}

LICENSE_SCAN = {
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

SECRET_SCAN = {
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


FAKE_ASSEMBLER = '''
import json
import os


class _Bundle:
    _FIELDS = (
        "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
        "dependency_interfaces", "dependency_context", "dependency_usage",
        "vars", "glossary", "hint_code",
    )

    def __init__(self, **kw):
        for k in self._FIELDS:
            setattr(self, k, kw.get(k))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return list(self._FIELDS)


def _log(entry):
    path = os.environ.get("PROVCHECK_FAKE_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\\n")


def assemble(component_id, repo_root, mode="cold"):
    _log({"call": "assemble", "component_id": component_id, "mode": mode})
    return _Bundle(
        component_id=component_id,
        spec_bundle_hash=os.environ.get("PROVCHECK_FAKE_HASH", ""),
        spec="",
        interface="",
        constraints="",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log({"call": "assemble_criterion", "component_id": component_id})
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "",
        "criterion_text": "",
        "requirement_text": "",
        "interface": "",
        "glossary": "",
        "dependency_interfaces": {},
    }
'''


def _const_module(value):
    return "GATE_VERSION = %r\n" % (value,)


def _fn_module(value):
    return (
        "def gate_version(repo_root):\n"
        "    return %r\n" % (value,)
    )


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()

    # Fake dependencies, so any attempt to compute a key internally is observable
    # (and returns a value different from what the caller supplies).
    _write(root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", FAKE_ASSEMBLER)
    _write(root / "gen" / "criterion-compiler" / "criterion_compiler.py",
           _const_module(GATE_VERSIONS["compiler"]))
    _write(root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
           _const_module(GATE_VERSIONS["compiler"]))
    _write(root / "gen" / "test-author" / "test_author.py",
           _const_module(GATE_VERSIONS["generated_test"]))
    _write(root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
           _const_module(GATE_VERSIONS["verifier"]))
    _write(root / "gen" / "license-scanner" / "license_scanner.py",
           _fn_module(GATE_VERSIONS["license_scanner"]))
    _write(root / "gen" / "secret-scanner" / "secret_scanner.py",
           _fn_module(GATE_VERSIONS["secret_scanner"]))

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
        "verification_report": VERIFICATION_REPORT,
        "license_scan": LICENSE_SCAN,
        "secret_scan": SECRET_SCAN,
    }
    manifest_text = json.dumps(manifest, indent=2)
    _write(root / "gen" / "foo" / ".provenance.json", manifest_text)
    _write(root / "verification" / "foo" / ".provenance.json", manifest_text)

    log = tmp_path / "fake-invocations.log"
    monkeypatch.setenv("PROVCHECK_FAKE_LOG", str(log))
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    return root, log, manifest_text


def _assert_assembler_never_called(log: Path):
    if log.exists():
        content = log.read_text(encoding="utf-8").strip()
        assert content == "", (
            "check_provenance computed a spec_bundle_hash itself via "
            "spec-bundle-assembler: %s" % content
        )


def test_caller_supplied_hash_matching_manifest_is_hit_even_if_own_computation_differs(repo, monkeypatch):
    root, log, _ = repo
    # If the component computed its own hash, it would get H_OTHER and miss.
    monkeypatch.setenv("PROVCHECK_FAKE_HASH", H_OTHER)

    result = provenance_checker.check_provenance("comp-foo", H, dict(GATE_VERSIONS), root)

    assert field(result, "hit") is True
    assert field(result, "verification_report") == VERIFICATION_REPORT
    _assert_assembler_never_called(log)


def test_caller_supplied_hash_differing_from_manifest_is_miss_even_if_own_computation_matches(repo, monkeypatch):
    root, log, _ = repo
    # If the component computed its own hash, it would get H (the manifest's) and hit.
    monkeypatch.setenv("PROVCHECK_FAKE_HASH", H)

    result = provenance_checker.check_provenance("comp-foo", H_OTHER, dict(GATE_VERSIONS), root)

    assert field(result, "hit") is False
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    _assert_assembler_never_called(log)


def test_comparison_is_against_manifest_field_and_manifest_untouched(repo, monkeypatch):
    root, log, manifest_text = repo
    monkeypatch.setenv("PROVCHECK_FAKE_HASH", H_OTHER)

    hit = provenance_checker.check_provenance("comp-foo", H, dict(GATE_VERSIONS), root)
    miss = provenance_checker.check_provenance("comp-foo", H_OTHER, dict(GATE_VERSIONS), root)

    assert field(hit, "hit") is True
    assert field(miss, "hit") is False

    # Changing the manifest's own spec_bundle_hash field flips the outcome for the
    # same caller-supplied hash: the comparison reads the manifest's field.
    manifest = json.loads(manifest_text)
    manifest["spec_bundle_hash"] = H_OTHER
    (root / "gen" / "foo" / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")

    now_hit = provenance_checker.check_provenance("comp-foo", H_OTHER, dict(GATE_VERSIONS), root)
    now_miss = provenance_checker.check_provenance("comp-foo", H, dict(GATE_VERSIONS), root)
    assert field(now_hit, "hit") is True
    assert field(now_miss, "hit") is False

    _assert_assembler_never_called(log)