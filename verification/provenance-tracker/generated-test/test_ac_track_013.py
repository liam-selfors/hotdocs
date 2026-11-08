import json
from pathlib import Path

import provenance_tracker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _component_md(component_id: str, sealed: bool, source_path: str = None) -> str:
    sealed_line = "true" if sealed else "false"
    extra = ("\nsource_path: " + source_path) if source_path else ""
    return (
        "---\n"
        "id: " + component_id + "\n"
        "title: Fixture " + component_id + "\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
        "sealed: " + sealed_line + extra + "\n"
        "---\n\n"
        "# Fixture " + component_id + "\n\n"
        "Synthetic fixture component for AC-TRACK-013.\n"
    )


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def _build_repo(tmp_path: Path, log_path: Path, sealed_check_result: dict, plain_provenance_result: dict) -> Path:
    repo_root = tmp_path / "repo"

    _write(
        repo_root / "specs" / "components" / "comp-seal" / "component.md",
        _component_md("comp-seal", sealed=True, source_path="fixture-source/comp-seal/"),
    )
    _write(
        repo_root / "specs" / "components" / "comp-plain" / "component.md",
        _component_md("comp-plain", sealed=False),
    )

    plain_key = {
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "gate_versions": {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    }

    fake_checker_src = '''
import json
from types import SimpleNamespace

LOG_PATH = %(log_path)r
SEALED_RESULT = %(sealed_result)r
PLAIN_RESULT = %(plain_result)r
PLAIN_KEY = %(plain_key)r


def _log(name, **kwargs):
    record = {"name": name, "args": kwargs}
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\\n")


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id, repo_root=str(repo_root))
    if component_id == "comp-seal":
        return SimpleNamespace(
            owners=["fixture-team"],
            source_path="fixture-source/comp-seal/",
            source_hash="sha256:" + "0" * 64,
            verifier_version="verifier-orchestrator@2.0.0",
        )
    return None


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id, repo_root=str(repo_root))
    return dict(SEALED_RESULT)


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id, repo_root=str(repo_root))
    return SimpleNamespace(
        spec_bundle_hash=PLAIN_KEY["spec_bundle_hash"],
        gate_versions=dict(PLAIN_KEY["gate_versions"]),
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(
        "check_provenance",
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        gate_versions=gate_versions,
        repo_root=str(repo_root),
    )
    return dict(PLAIN_RESULT)
''' % {
        "log_path": str(log_path),
        "sealed_result": sealed_check_result,
        "plain_result": plain_provenance_result,
        "plain_key": plain_key,
    }

    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", fake_checker_src)

    fake_gate_runner_src = '''
import json

LOG_PATH = %(log_path)r

with open(LOG_PATH, "a") as f:
    f.write(json.dumps({"name": "component_gate_runner_loaded", "args": {}}) + "\\n")


def run_component_gates(*args, **kwargs):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"name": "run_component_gates", "args": {}}) + "\\n")
    raise AssertionError("component-gate-runner must never be loaded or called by check_readiness")
''' % {"log_path": str(log_path)}

    _write(
        repo_root / "gen" / "component-gate-runner" / "component_gate_runner.py",
        fake_gate_runner_src,
    )

    return repo_root


def _passing_plain_result() -> dict:
    return {
        "hit": True,
        "verification_report": {
            "component_id": "comp-plain",
            "criteria": [],
            "requirement_results": {},
            "interface_drift": False,
            "mutation_score": 1.0,
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


def _passing_sealed_result() -> dict:
    return {
        "hit": True,
        "sealed": True,
        "reason": None,
        "verification_report": {"overall": "pass"},
        "license_scan": None,
        "secret_scan": None,
        "owners": ["fixture-team"],
        "source_hash": "sha256:" + "0" * 64,
        "written_at": "2026-11-02T00:00:00Z",
    }


def test_whole_corpus_sealed_and_plain_both_ready(tmp_path):
    log_path = tmp_path / "invocations.log"
    sealed_result = _passing_sealed_result()
    plain_result = _passing_plain_result()

    repo_root = _build_repo(tmp_path, log_path, sealed_result, plain_result)

    report = provenance_tracker.check_readiness(repo_root)

    assert _get(report, "ready") is True

    components = _get(report, "components")
    comp_seal_entry = _get(components, "comp-seal")
    for key, expected_value in sealed_result.items():
        assert _get(comp_seal_entry, key) == expected_value

    records = _read_log(log_path)

    sealed_calls = [r for r in records if r["name"] == "check_sealed_provenance"]
    assert len(sealed_calls) >= 1
    assert all(r["args"]["component_id"] == "comp-seal" for r in sealed_calls)

    provenance_calls = [r for r in records if r["name"] == "check_provenance"]
    assert len(provenance_calls) >= 1
    assert all(r["args"]["component_id"] == "comp-plain" for r in provenance_calls)

    key_calls = [r for r in records if r["name"] == "current_provenance_key"]
    assert len(key_calls) >= 1
    assert all(r["args"]["component_id"] == "comp-plain" for r in key_calls)

    gate_runner_records = [
        r for r in records if r["name"] in ("component_gate_runner_loaded", "run_component_gates")
    ]
    assert gate_runner_records == []


def test_sealed_miss_source_changed_is_not_ready(tmp_path):
    log_path = tmp_path / "invocations.log"
    sealed_result = {
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
    plain_result = _passing_plain_result()

    repo_root = _build_repo(tmp_path, log_path, sealed_result, plain_result)

    report = provenance_tracker.check_readiness(repo_root)

    assert _get(report, "ready") is False

    not_ready_reasons = _get(report, "not_ready_reasons")
    assert len(not_ready_reasons) == 1
    assert not_ready_reasons[0] == (
        "comp-seal: sealed provenance source_changed — run hotdocs generate comp-seal"
    )

    records = _read_log(log_path)
    gate_runner_records = [
        r for r in records if r["name"] in ("component_gate_runner_loaded", "run_component_gates")
    ]
    assert gate_runner_records == []


def test_sealed_readiness_unaffected_by_flagged_secret_scan_elsewhere(tmp_path):
    log_path = tmp_path / "invocations.log"
    sealed_result = _passing_sealed_result()

    plain_result = _passing_plain_result()
    plain_result["secret_scan"] = {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": True,
        "matches": [
            {"rule_id": "AWS Access Key", "risk_tier": "high", "file": "gen/comp-plain/config.py", "line": 12}
        ],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }

    repo_root = _build_repo(tmp_path, log_path, sealed_result, plain_result)

    report = provenance_tracker.check_readiness(repo_root)

    components = _get(report, "components")
    comp_seal_entry = _get(components, "comp-seal")
    for key, expected_value in sealed_result.items():
        assert _get(comp_seal_entry, key) == expected_value

    records = _read_log(log_path)
    gate_runner_records = [
        r for r in records if r["name"] in ("component_gate_runner_loaded", "run_component_gates")
    ]
    assert gate_runner_records == []