import json

import provenance_tracker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# component-gate-runner is never written to disk anywhere in this file.
# R-TRACK-009 forbids check_readiness from ever calling it; since every
# dependency in this corpus is resolved by loading
# <repo_root>/gen/<slug>/<module>.py at the point of use, a correct
# implementation that (incorrectly) tried to call it would fail with a
# missing-module error, failing the test. Its absence is the proof.

IMPACT_ANALYZER_SRC = '''
import json
from pathlib import Path


def compute_blast_radius(changed_ids, repo_root):
    repo_root = Path(repo_root)
    with open(repo_root / "ia_calls.log", "a") as f:
        f.write(json.dumps({"changed_ids": list(changed_ids)}) + "\\n")
    with open(repo_root / "ia_config.json") as f:
        return json.load(f)
'''

PROVENANCE_CHECKER_SRC = '''
import json
from pathlib import Path


class _ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


class _SealedKey:
    def __init__(self, owners, source_path, source_hash, verifier_version):
        self.owners = owners
        self.source_path = source_path
        self.source_hash = source_hash
        self.verifier_version = verifier_version


def _config(repo_root):
    with open(Path(repo_root) / "pc_config.json") as f:
        return json.load(f)


def _log(repo_root, record):
    with open(Path(repo_root) / "pc_calls.log", "a") as f:
        f.write(json.dumps(record) + "\\n")


def current_sealed_key(component_id, repo_root):
    _log(repo_root, {"fn": "current_sealed_key", "component_id": component_id})
    cfg = _config(repo_root)
    sealed = cfg.get("sealed", {}).get(component_id)
    if sealed is None:
        return None
    return _SealedKey(**sealed)


def current_provenance_key(component_id, repo_root):
    _log(repo_root, {"fn": "current_provenance_key", "component_id": component_id})
    cfg = _config(repo_root)
    pk = cfg["provenance_key"]
    return _ProvenanceKey(pk["spec_bundle_hash"], pk["gate_versions"])


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(repo_root, {
        "fn": "check_provenance",
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": gate_versions,
    })
    cfg = _config(repo_root)
    return cfg["results"][component_id]


def check_sealed_provenance(component_id, repo_root):
    _log(repo_root, {"fn": "check_sealed_provenance", "component_id": component_id})
    cfg = _config(repo_root)
    return cfg["sealed_results"][component_id]
'''


def _write_dependency(repo_root, slug, module_name, source):
    mod_dir = repo_root / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / f"{module_name}.py").write_text(source)


def _write_component(repo_root, slug, component_id):
    comp_dir = repo_root / "specs" / "components" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        f"id: {component_id}\n"
        f"title: {component_id}\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "realizes: []\n"
        "---\n\n"
        f"# {component_id}\n\nFixture component.\n"
    )
    gen_dir = repo_root / "gen" / slug
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "placeholder.txt").write_text("fixture generated code\n")


def _write_pc_config(repo_root, results, provenance_key, sealed=None, sealed_results=None):
    config = {
        "sealed": sealed or {},
        "provenance_key": provenance_key,
        "results": results,
        "sealed_results": sealed_results or {},
    }
    (repo_root / "pc_config.json").write_text(json.dumps(config))


def _write_ia_config(repo_root, impacted):
    config = {"impacted": impacted, "precondition_error": None}
    (repo_root / "ia_config.json").write_text(json.dumps(config))


def _passing_report(component_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }


def _clean_license(component_id):
    return {
        "component_id": component_id,
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
    }


def _clean_secret():
    return {
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


def test_blast_radius_hit_and_miss(tmp_path):
    repo_root = tmp_path
    _write_dependency(repo_root, "impact-analyzer", "impact_analyzer", IMPACT_ANALYZER_SRC)
    _write_dependency(repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SRC)
    _write_component(repo_root, "foo", "comp-foo")
    _write_component(repo_root, "bar", "comp-bar")

    _write_ia_config(repo_root, [
        {"component_id": "comp-foo", "reason": "direct", "via": None},
        {"component_id": "comp-bar", "reason": "transitive-interface", "via": "comp-foo"},
    ])

    foo_result = {
        "hit": True,
        "verification_report": _passing_report("comp-foo"),
        "license_scan": _clean_license("comp-foo"),
        "secret_scan": _clean_secret(),
    }
    bar_result = {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
    _write_pc_config(
        repo_root,
        results={"comp-foo": foo_result, "comp-bar": bar_result},
        provenance_key={"spec_bundle_hash": "sha256:abc123", "gate_versions": {"verifier": "v@1"}},
    )

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-changed"])

    assert _get(report, "scope") == "blast-radius"
    components = _get(report, "components")
    assert set(components.keys()) == {"comp-foo", "comp-bar"}
    assert _get(components["comp-foo"], "hit") is True
    assert _get(components["comp-bar"], "hit") is False

    reasons = _get(report, "not_ready_reasons")
    assert any("comp-bar" in reason for reason in reasons), reasons

    ia_calls = (repo_root / "ia_calls.log").read_text().strip().splitlines()
    assert json.loads(ia_calls[0])["changed_ids"] == ["comp-changed"]


def test_whole_corpus_scope(tmp_path):
    repo_root = tmp_path
    _write_dependency(repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SRC)
    _write_component(repo_root, "alpha", "comp-alpha")
    _write_component(repo_root, "beta", "comp-beta")

    alpha_result = {
        "hit": True,
        "verification_report": _passing_report("comp-alpha"),
        "license_scan": _clean_license("comp-alpha"),
        "secret_scan": _clean_secret(),
    }
    beta_result = {
        "hit": True,
        "verification_report": _passing_report("comp-beta"),
        "license_scan": _clean_license("comp-beta"),
        "secret_scan": _clean_secret(),
    }
    _write_pc_config(
        repo_root,
        results={"comp-alpha": alpha_result, "comp-beta": beta_result},
        provenance_key={"spec_bundle_hash": "sha256:def456", "gate_versions": {"verifier": "v@1"}},
    )

    # No impact-analyzer module is written to disk at all: given no
    # changed_ids, D98 requires it never be loaded, so any attempt to
    # load it here would raise and fail this test.
    report = provenance_tracker.check_readiness(repo_root)

    assert _get(report, "scope") == "whole-corpus"

    calls_log_path = repo_root / "pc_calls.log"
    assert calls_log_path.exists()
    checked_ids = set()
    for line in calls_log_path.read_text().strip().splitlines():
        record = json.loads(line)
        if "component_id" in record:
            checked_ids.add(record["component_id"])
    assert checked_ids == {"comp-alpha", "comp-beta"}


def test_failing_verification_report(tmp_path):
    repo_root = tmp_path
    _write_dependency(repo_root, "impact-analyzer", "impact_analyzer", IMPACT_ANALYZER_SRC)
    _write_dependency(repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SRC)
    _write_component(repo_root, "target", "comp-target")

    _write_ia_config(repo_root, [
        {"component_id": "comp-target", "reason": "direct", "via": None},
    ])

    failing_report = {
        "component_id": "comp-target",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {"message": "x failed", "expected": 1, "actual": 2},
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.5,
        "overall": "fail",
    }
    target_result = {
        "hit": True,
        "verification_report": failing_report,
        "license_scan": _clean_license("comp-target"),
        "secret_scan": _clean_secret(),
    }
    _write_pc_config(
        repo_root,
        results={"comp-target": target_result},
        provenance_key={"spec_bundle_hash": "sha256:ghi789", "gate_versions": {"verifier": "v@1"}},
    )

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-changed"])

    reasons = _get(report, "not_ready_reasons")
    matching = [
        r for r in reasons
        if "comp-target" in r and "verification" in r and "R-FOO-002" in r
    ]
    assert matching, reasons


def test_blocked_license_scan(tmp_path):
    repo_root = tmp_path
    _write_dependency(repo_root, "impact-analyzer", "impact_analyzer", IMPACT_ANALYZER_SRC)
    _write_dependency(repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SRC)
    _write_component(repo_root, "target2", "comp-target2")

    _write_ia_config(repo_root, [
        {"component_id": "comp-target2", "reason": "direct", "via": None},
    ])

    blocked_license = {
        "component_id": "comp-target2",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.9,
        "block_threshold": 0.70,
        "blocked": True,
        "matches": [
            {"reference_id": "ref-123", "license_family": "gpl-3.0", "risk_tier": "high", "score": 0.9},
        ],
        "notified": True,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    target_result = {
        "hit": True,
        "verification_report": _passing_report("comp-target2"),
        "license_scan": blocked_license,
        "secret_scan": _clean_secret(),
    }
    _write_pc_config(
        repo_root,
        results={"comp-target2": target_result},
        provenance_key={"spec_bundle_hash": "sha256:jkl012", "gate_versions": {"verifier": "v@1"}},
    )

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-changed"])

    reasons = _get(report, "not_ready_reasons")
    matching = [r for r in reasons if "comp-target2" in r and "license_scan" in r]
    assert matching, reasons


def test_provenance_key_forwarded_unchanged(tmp_path):
    repo_root = tmp_path
    _write_dependency(repo_root, "impact-analyzer", "impact_analyzer", IMPACT_ANALYZER_SRC)
    _write_dependency(repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SRC)
    _write_component(repo_root, "a", "comp-a")
    _write_component(repo_root, "b", "comp-b")

    _write_ia_config(repo_root, [
        {"component_id": "comp-a", "reason": "direct", "via": None},
        {"component_id": "comp-b", "reason": "transitive-interface", "via": "comp-a"},
    ])

    a_result = {
        "hit": True,
        "verification_report": _passing_report("comp-a"),
        "license_scan": _clean_license("comp-a"),
        "secret_scan": _clean_secret(),
    }
    b_result = {
        "hit": True,
        "verification_report": _passing_report("comp-b"),
        "license_scan": _clean_license("comp-b"),
        "secret_scan": _clean_secret(),
    }
    _write_pc_config(
        repo_root,
        results={"comp-a": a_result, "comp-b": b_result},
        provenance_key={"spec_bundle_hash": "sha256:k1", "gate_versions": {"verifier": "v@1"}},
    )

    provenance_tracker.check_readiness(repo_root, changed_ids=["comp-changed"])

    calls = [
        json.loads(line)
        for line in (repo_root / "pc_calls.log").read_text().strip().splitlines()
    ]
    check_provenance_calls = [c for c in calls if c["fn"] == "check_provenance"]
    assert len(check_provenance_calls) == 2
    for call in check_provenance_calls:
        assert call["spec_bundle_hash"] == "sha256:k1"
        assert call["gate_versions"] == {"verifier": "v@1"}