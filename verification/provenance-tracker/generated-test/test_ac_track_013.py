import json
from pathlib import Path

import provenance_tracker


EM_DASH = "\u2014"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SEALED_HIT = {
    "hit": True,
    "sealed": True,
    "reason": None,
    "verification_report": {"overall": "pass"},
    "license_scan": None,
    "secret_scan": None,
    "owners": ["team-a"],
    "source_hash": "sha256:" + "0" * 64,
    "written_at": "2026-11-02T00:00:00Z",
}

SEALED_MISS_SOURCE_CHANGED = {
    "hit": False,
    "sealed": True,
    "reason": "source_changed",
    "verification_report": None,
    "license_scan": None,
    "secret_scan": None,
    "owners": None,
    "source_hash": None,
    "written_at": None,
}

PLAIN_HIT = {
    "hit": True,
    "verification_report": {
        "component_id": "comp-plain",
        "criteria": [
            {
                "id": "AC-PLAIN-001",
                "covers": "R-PLAIN-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-PLAIN-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "overall": "pass",
    },
    "license_scan": {
        "component_id": "comp-plain",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.1,
        "block_threshold": 0.70,
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

PLAIN_KEY = {
    "spec_bundle_hash": "sha256:" + "ab" * 32,
    "gate_versions": {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
        "secret_scanner": "secret_scanner@0.0.0",
    },
}


PROVENANCE_CHECKER_SRC = '''
import json
from pathlib import Path

_CONFIG = __CONFIG__
_LOG = __LOG__


def _log(name, **args):
    rec = {"name": name, "args": args}
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str) + "\\n")


def _cfg():
    with open(_CONFIG, encoding="utf-8") as fh:
        return json.load(fh)


class _Attrs:
    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


class SealedKey(_Attrs):
    def __init__(self, owners, source_path, source_hash, verifier_version):
        self.owners = owners
        self.source_path = source_path
        self.source_hash = source_hash
        self.verifier_version = verifier_version


class ProvenanceKey(_Attrs):
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id, repo_root=repo_root)
    if component_id == "comp-seal":
        return SealedKey(
            owners=["team-a"],
            source_path="legacy/seal/",
            source_hash="sha256:" + "0" * 64,
            verifier_version="verifier-orchestrator@2.0.0",
        )
    return None


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id, repo_root=repo_root)
    return _cfg()["sealed_result"]


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id, repo_root=repo_root)
    key = _cfg()["plain_key"]
    return ProvenanceKey(key["spec_bundle_hash"], dict(key["gate_versions"]))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(
        "check_provenance",
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        gate_versions=dict(gate_versions),
        repo_root=repo_root,
    )
    return _cfg()["plain_result"]
'''


GATE_RUNNER_SRC = '''
import json

_LOG = __LOG__

with open(_LOG, "a", encoding="utf-8") as _fh:
    _fh.write(json.dumps({"name": "component_gate_runner_loaded"}) + "\\n")


def run_component_gates(*args, **kwargs):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"name": "run_component_gates"}, default=str) + "\\n")
    raise RuntimeError("component-gate-runner must never be called")
'''


CAPABILITY_VERIFIER_SRC = '''
import json

_LOG = __LOG__

GATE_VERSION = "capability_scenario_verifier@2.0.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


def _log(name, **args):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"name": name, "args": args}, default=str) + "\\n")


def check_capability_provenance(capability_id, repo_root):
    _log("check_capability_provenance", capability_id=capability_id)
    return {
        "hit": True,
        "capability_scenario_report": {capability_id: {"overall": "pass", "scenarios": []}},
    }


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    _log("run_capability_gates", capability_id=capability_id)
    return {
        "hit": True,
        "capability_scenario_report": {capability_id: {"overall": "pass", "scenarios": []}},
    }


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    _log("run_capability_scenarios")
    return {}
'''


SECRET_SCANNER_SRC = '''
import json

_LOG = __LOG__

FLAGGED = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": True,
    "matches": [
        {"rule_id": "AWS Access Key", "risk_tier": "high", "file": "legacy/seal/config.py", "line": 3}
    ],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


def gate_version(repo_root=None):
    return "secret_scanner@0.0.0"


def _flagged(*args, **kwargs):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"name": "secret_scanner_call"}) + "\\n")
    return dict(FLAGGED)


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return _flagged
'''


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(tmp_path: Path, sealed_result, flagged_secret_scan=False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "invocations.log"
    log_path.write_text("", encoding="utf-8")
    config_path = tmp_path / "fake_config.json"
    config_path.write_text(
        json.dumps(
            {
                "sealed_result": sealed_result,
                "plain_result": PLAIN_HIT,
                "plain_key": PLAIN_KEY,
            }
        ),
        encoding="utf-8",
    )

    # comp-seal: sealed component
    _write(
        repo_root / "specs" / "components" / "seal" / "component.md",
        "---\n"
        "id: comp-seal\n"
        "title: Seal\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/seal/\n"
        "depends_on: []\n"
        "---\n\n"
        "# Seal\n\nA sealed fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "seal" / "requirements" / "R-SEAL-001.md",
        "# R-SEAL-001\n\n**R-SEAL-001** — MUST exist.\n",
    )
    _write(
        repo_root / "specs" / "components" / "seal" / "acceptance" / "AC-SEAL-001.md",
        "# AC-SEAL-001\n\nCovers: R-SEAL-001\nKind: compiled\n",
    )
    _write(repo_root / "legacy" / "seal" / "seal.py", "VALUE = 1\n")

    # comp-plain: generated (not sealed) component
    _write(
        repo_root / "specs" / "components" / "plain" / "component.md",
        "---\n"
        "id: comp-plain\n"
        "title: Plain\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "realizes: []\n"
        "depends_on: []\n"
        "---\n\n"
        "# Plain\n\nA generated fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "plain" / "requirements" / "R-PLAIN-001.md",
        "# R-PLAIN-001\n\n**R-PLAIN-001** — MUST exist.\n",
    )
    _write(
        repo_root / "specs" / "components" / "plain" / "acceptance" / "AC-PLAIN-001.md",
        "# AC-PLAIN-001\n\nCovers: R-PLAIN-001\nKind: compiled\n",
    )
    _write(repo_root / "gen" / "plain" / "plain.py", "VALUE = 2\n")

    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        PROVENANCE_CHECKER_SRC.replace("__CONFIG__", repr(str(config_path))).replace(
            "__LOG__", repr(str(log_path))
        ),
    )
    _write(
        repo_root / "gen" / "component-gate-runner" / "component_gate_runner.py",
        GATE_RUNNER_SRC.replace("__LOG__", repr(str(log_path))),
    )
    _write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        CAPABILITY_VERIFIER_SRC.replace("__LOG__", repr(str(log_path))),
    )
    if flagged_secret_scan:
        _write(
            repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
            SECRET_SCANNER_SRC.replace("__LOG__", repr(str(log_path))),
        )
    return repo_root, log_path


def _read_log(log_path: Path):
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _ids_for(records, name):
    return [r["args"]["component_id"] for r in records if r["name"] == name]


def _assert_gate_runner_never_loaded(records):
    names = {r["name"] for r in records}
    assert "component_gate_runner_loaded" not in names
    assert "run_component_gates" not in names


def test_sealed_and_plain_routed_by_current_sealed_key(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, SEALED_HIT)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is True

    records = _read_log(log_path)
    assert set(_ids_for(records, "check_sealed_provenance")) == {"comp-seal"}
    assert set(_ids_for(records, "check_provenance")) == {"comp-plain"}
    assert set(_ids_for(records, "current_provenance_key")) == {"comp-plain"}

    # spec_bundle_hash and gate_versions passed through unchanged
    for r in records:
        if r["name"] == "check_provenance":
            assert r["args"]["spec_bundle_hash"] == PLAIN_KEY["spec_bundle_hash"]
            assert r["args"]["gate_versions"] == PLAIN_KEY["gate_versions"]

    components = field(report, "components")
    assert components["comp-seal"] == SEALED_HIT

    _assert_gate_runner_never_loaded(records)


def test_sealed_miss_reports_reason(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, SEALED_MISS_SOURCE_CHANGED)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    seal_reasons = [r for r in reasons if "comp-seal" in r]
    expected = (
        "comp-seal: sealed provenance source_changed "
        + EM_DASH
        + " run hotdocs generate comp-seal"
    )
    assert seal_reasons == [expected]

    records = _read_log(log_path)
    assert set(_ids_for(records, "check_sealed_provenance")) == {"comp-seal"}
    _assert_gate_runner_never_loaded(records)


def test_sealed_readiness_ignores_flagged_repo_secret_scan(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, SEALED_HIT, flagged_secret_scan=True)

    report = provenance_tracker.check_readiness(repo_root)

    reasons = list(field(report, "not_ready_reasons"))
    assert [r for r in reasons if "comp-seal" in r] == []

    components = field(report, "components")
    assert components["comp-seal"] == SEALED_HIT
    assert field(components["comp-seal"], "hit") is True

    records = _read_log(log_path)
    assert set(_ids_for(records, "check_sealed_provenance")) == {"comp-seal"}
    _assert_gate_runner_never_loaded(records)