import json

import provenance_tracker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


SEALED_KEY = {
    "owners": ["pipeline-team"],
    "source_path": "pipeline/seal/",
    "source_hash": "sha256:" + "0" * 64,
    "verifier_version": "verifier-orchestrator@2.0.0",
}

PROVENANCE_KEY = {
    "spec_bundle_hash": "sha256:" + "1" * 64,
    "gate_versions": {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
        "secret_scanner": "secret_scanner@0.0.0",
    },
}

PROVENANCE_RESULT_PASS = {
    "hit": True,
    "verification_report": {
        "component_id": "comp-plain",
        "criteria": [
            {"id": "AC-PLAIN-001", "covers": "R-PLAIN-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-PLAIN-001": "pass"},
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
        "block_threshold": 0.7,
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

SEALED_RESULT_HIT = {
    "hit": True,
    "sealed": True,
    "reason": None,
    "verification_report": {"overall": "pass"},
    "license_scan": None,
    "secret_scan": None,
}

SEALED_RESULT_MISS = {
    "hit": False,
    "sealed": True,
    "reason": "source_changed",
    "verification_report": None,
    "license_scan": None,
    "secret_scan": None,
}

SEALED_RESULT_HIT_WITH_FLAGGED_SECRET_SCAN = {
    "hit": True,
    "sealed": True,
    "reason": None,
    "verification_report": {"overall": "pass"},
    "license_scan": None,
    "secret_scan": {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": True,
        "matches": [
            {"rule_id": "AWS Access Key", "risk_tier": "high", "file": "pipeline/seal/config.py", "line": 12},
        ],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    },
}

_PROVENANCE_CHECKER_TEMPLATE = """
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOG_PATH = _REPO_ROOT / "invocations.log"


def _log(name, *args):
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps({"name": name, "args": list(args)}, default=str) + "\\n")


_SEALED_KEYS = __SEALED_KEYS__
_SEALED_RESULT = __SEALED_RESULT__
_PROVENANCE_KEY = __PROVENANCE_KEY__
_PROVENANCE_RESULT = __PROVENANCE_RESULT__


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id)
    return _SEALED_KEYS.get(component_id)


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id)
    return _SEALED_RESULT


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id)
    return _PROVENANCE_KEY


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id, spec_bundle_hash, gate_versions)
    return _PROVENANCE_RESULT
"""

_GATE_RUNNER_TEMPLATE = """
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOG_PATH = _REPO_ROOT / "invocations.log"

with open(_LOG_PATH, "a") as f:
    f.write(json.dumps({"name": "component_gate_runner_loaded", "args": []}) + "\\n")


def run_component_gates(*args, **kwargs):
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps({"name": "run_component_gates", "args": []}) + "\\n")
    raise RuntimeError("component-gate-runner must not be invoked by check_readiness")
"""


def _write_component(repo_root, slug, comp_id, sealed, source_path=None):
    comp_dir = repo_root / "specs" / "components" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = [
        "---",
        f"id: {comp_id}",
        f"title: {slug.title()}",
        "status: draft",
        "owners: [team-a]",
        f"sealed: {'true' if sealed else 'false'}",
    ]
    if source_path:
        frontmatter.append(f"source_path: {source_path}")
    frontmatter.append("---")
    body = ["", f"# {slug.title()}", "", "Fixture component for AC-TRACK-013."]
    (comp_dir / "component.md").write_text("\n".join(frontmatter + body) + "\n")


def _write_provenance_checker(repo_root, sealed_result):
    module_path = repo_root / "gen" / "provenance-checker" / "provenance_checker.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    source = _PROVENANCE_CHECKER_TEMPLATE
    source = source.replace("__SEALED_KEYS__", repr({"comp-seal": SEALED_KEY}))
    source = source.replace("__SEALED_RESULT__", repr(sealed_result))
    source = source.replace("__PROVENANCE_KEY__", repr(PROVENANCE_KEY))
    source = source.replace("__PROVENANCE_RESULT__", repr(PROVENANCE_RESULT_PASS))
    module_path.write_text(source)


def _write_gate_runner_fake(repo_root):
    module_path = repo_root / "gen" / "component-gate-runner" / "component_gate_runner.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(_GATE_RUNNER_TEMPLATE)


def _build_repo(tmp_path, sealed_result):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "invocations.log").write_text("")
    _write_component(repo_root, "seal", "comp-seal", sealed=True, source_path="pipeline/seal/")
    _write_component(repo_root, "plain", "comp-plain", sealed=False)
    _write_provenance_checker(repo_root, sealed_result)
    _write_gate_runner_fake(repo_root)
    return repo_root


def _read_log(repo_root):
    log_path = repo_root / "invocations.log"
    entries = []
    for line in log_path.read_text().splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def test_whole_corpus_sealed_and_plain_ready(tmp_path):
    repo_root = _build_repo(tmp_path, SEALED_RESULT_HIT)

    report = provenance_tracker.check_readiness(repo_root)

    assert _get(report, "ready") is True

    log = _read_log(repo_root)
    sealed_calls = {e["args"][0] for e in log if e["name"] == "check_sealed_provenance"}
    assert sealed_calls == {"comp-seal"}
    key_calls = {e["args"][0] for e in log if e["name"] == "current_provenance_key"}
    assert key_calls == {"comp-plain"}
    provenance_calls = {e["args"][0] for e in log if e["name"] == "check_provenance"}
    assert provenance_calls == {"comp-plain"}

    components = _get(report, "components")
    assert _get(components, "comp-seal") == SEALED_RESULT_HIT

    gate_runner_entries = [
        e for e in log if e["name"] in ("component_gate_runner_loaded", "run_component_gates")
    ]
    assert gate_runner_entries == []


def test_sealed_miss_reports_source_changed(tmp_path):
    repo_root = _build_repo(tmp_path, SEALED_RESULT_MISS)

    report = provenance_tracker.check_readiness(repo_root)

    assert _get(report, "ready") is False
    assert _get(report, "not_ready_reasons") == [
        "comp-seal: sealed provenance source_changed — run hotdocs generate comp-seal"
    ]


def test_sealed_readiness_ignores_flagged_secret_scan(tmp_path):
    repo_root = _build_repo(tmp_path, SEALED_RESULT_HIT_WITH_FLAGGED_SECRET_SCAN)

    report = provenance_tracker.check_readiness(repo_root)

    assert _get(report, "ready") is True
    assert _get(report, "not_ready_reasons") == []

    components = _get(report, "components")
    assert _get(components, "comp-seal") == SEALED_RESULT_HIT_WITH_FLAGGED_SECRET_SCAN