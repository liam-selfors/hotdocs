import json
import pathlib
import textwrap

import provenance_tracker


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_component(repo_root, slug, comp_id=None):
    comp_id = comp_id or "comp-{}".format(slug)
    content = textwrap.dedent(
        """\
        ---
        id: {comp_id}
        title: {title}
        status: draft
        owners: [team-x]
        sealed: true
        source_path: fake/{slug}/
        ---
        A fixture component.
        """
    ).format(comp_id=comp_id, title=slug.title(), slug=slug)
    _write_file(repo_root / "specs" / "components" / slug / "component.md", content)


_PROVENANCE_CHECKER_SRC = '''
import json
import pathlib

_DIR = pathlib.Path(__file__).parent
_CONFIG = json.loads((_DIR / "_fake_config.json").read_text())
_LOG = _DIR / "_calls.log"


def _log(event, **kw):
    with open(_LOG, "a") as f:
        f.write(json.dumps({"event": event, **kw}) + "\\n")


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


class _Key:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    cfg = _CONFIG["provenance_key"]
    return _Key(cfg["spec_bundle_hash"], cfg["gate_versions"])


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(
        "check_provenance",
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        gate_versions=gate_versions,
    )
    return _CONFIG["results"][component_id]


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
    return _CONFIG["results"][component_id]
'''

_IMPACT_ANALYZER_SRC = '''
import json
import pathlib

_DIR = pathlib.Path(__file__).parent
_CONFIG = json.loads((_DIR / "_fake_config.json").read_text())


def compute_blast_radius(changed_ids, repo_root):
    return _CONFIG["blast_radius"]
'''

_COMPONENT_GATE_RUNNER_SRC = '''
import pathlib

_LOG = pathlib.Path(__file__).parent / "_invocations.log"


def __getattr__(name):
    def _tracked(*args, **kwargs):
        with open(_LOG, "a") as f:
            f.write(name + "\\n")
        return None
    return _tracked
'''


def _write_provenance_checker(repo_root, config):
    mod_dir = repo_root / "gen" / "provenance-checker"
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "provenance_checker.py").write_text(_PROVENANCE_CHECKER_SRC)
    (mod_dir / "_fake_config.json").write_text(json.dumps(config))


def _write_impact_analyzer(repo_root, config):
    mod_dir = repo_root / "gen" / "impact-analyzer"
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "impact_analyzer.py").write_text(_IMPACT_ANALYZER_SRC)
    (mod_dir / "_fake_config.json").write_text(json.dumps(config))


def _write_component_gate_runner(repo_root):
    mod_dir = repo_root / "gen" / "component-gate-runner"
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "component_gate_runner.py").write_text(_COMPONENT_GATE_RUNNER_SRC)


def _gate_runner_log(repo_root):
    return repo_root / "gen" / "component-gate-runner" / "_invocations.log"


def _calls_log(repo_root):
    return repo_root / "gen" / "provenance-checker" / "_calls.log"


def _passing_result(component_id):
    return {
        "hit": True,
        "verification_report": {
            "component_id": component_id,
            "criteria": [],
            "requirement_results": {},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": "pass",
        },
        "license_scan": {
            "component_id": component_id,
            "gate_version": "license_scanner@1.0.0",
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
            "gate_version": "secret_scanner@1.0.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }


def test_blast_radius_scope_hit_and_miss(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    results = {
        "comp-beta": _passing_result("comp-beta"),
        "comp-gamma": {
            "hit": False,
            "verification_report": None,
            "license_scan": None,
            "secret_scan": None,
        },
    }
    config = {
        "provenance_key": {
            "spec_bundle_hash": "sha256:aaaa",
            "gate_versions": {"compiler": "c@1"},
        },
        "results": results,
        "blast_radius": {
            "impacted": [
                {"component_id": "comp-beta", "reason": "direct", "via": None},
                {
                    "component_id": "comp-gamma",
                    "reason": "transitive-interface",
                    "via": "comp-beta",
                },
            ],
            "precondition_error": None,
        },
    }
    _write_provenance_checker(repo_root, config)
    _write_impact_analyzer(repo_root, config)
    _write_component_gate_runner(repo_root)

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-alpha"])

    scope = _field(report, "scope")
    components = _field(report, "components")
    not_ready_reasons = _field(report, "not_ready_reasons")

    assert scope == "blast-radius"
    assert set(components.keys()) == {"comp-beta", "comp-gamma"}
    assert any("comp-gamma" in r for r in not_ready_reasons)
    assert not _gate_runner_log(repo_root).exists()


def test_whole_corpus_checks_every_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component(repo_root, "delta")
    _write_component(repo_root, "epsilon")

    results = {
        "comp-delta": _passing_result("comp-delta"),
        "comp-epsilon": _passing_result("comp-epsilon"),
    }
    config = {
        "provenance_key": {
            "spec_bundle_hash": "sha256:bbbb",
            "gate_versions": {"compiler": "c@1"},
        },
        "results": results,
        "blast_radius": {"impacted": [], "precondition_error": None},
    }
    _write_provenance_checker(repo_root, config)
    _write_component_gate_runner(repo_root)

    report = provenance_tracker.check_readiness(repo_root, changed_ids=None)

    scope = _field(report, "scope")
    components = _field(report, "components")

    assert scope == "whole-corpus"
    assert set(components.keys()) == {"comp-delta", "comp-epsilon"}

    log_path = _calls_log(repo_root)
    assert log_path.exists()
    checked_ids = set()
    for line in log_path.read_text().splitlines():
        entry = json.loads(line)
        if entry["event"] == "current_sealed_key":
            checked_ids.add(entry["component_id"])
    assert checked_ids == {"comp-delta", "comp-epsilon"}
    assert not _gate_runner_log(repo_root).exists()


def test_verification_failure_reason(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component(repo_root, "foo")

    result = _passing_result("comp-foo")
    result["verification_report"]["requirement_results"] = {
        "R-FOO-001": "pass",
        "R-FOO-002": "fail",
    }
    result["verification_report"]["overall"] = "fail"

    config = {
        "provenance_key": {
            "spec_bundle_hash": "sha256:cccc",
            "gate_versions": {"compiler": "c@1"},
        },
        "results": {"comp-foo": result},
        "blast_radius": {"impacted": [], "precondition_error": None},
    }
    _write_provenance_checker(repo_root, config)
    _write_component_gate_runner(repo_root)

    report = provenance_tracker.check_readiness(repo_root, changed_ids=None)

    not_ready_reasons = _field(report, "not_ready_reasons")
    matching = [r for r in not_ready_reasons if "comp-foo" in r]
    assert matching
    entry = matching[0]
    assert "verification" in entry
    assert "R-FOO-002" in entry
    assert not _gate_runner_log(repo_root).exists()


def test_license_scan_blocked_reason(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component(repo_root, "bar")

    result = _passing_result("comp-bar")
    result["license_scan"]["similarity_score"] = 0.9
    result["license_scan"]["blocked"] = True
    result["license_scan"]["matches"] = [
        {
            "reference_id": "ref-1",
            "license_family": "gpl-3.0",
            "risk_tier": "high",
            "score": 0.9,
        }
    ]
    result["license_scan"]["notified"] = True

    config = {
        "provenance_key": {
            "spec_bundle_hash": "sha256:dddd",
            "gate_versions": {"compiler": "c@1"},
        },
        "results": {"comp-bar": result},
        "blast_radius": {"impacted": [], "precondition_error": None},
    }
    _write_provenance_checker(repo_root, config)
    _write_component_gate_runner(repo_root)

    report = provenance_tracker.check_readiness(repo_root, changed_ids=None)

    not_ready_reasons = _field(report, "not_ready_reasons")
    matching = [r for r in not_ready_reasons if "comp-bar" in r]
    assert matching
    assert "license_scan" in matching[0]
    assert not _gate_runner_log(repo_root).exists()


def test_provenance_key_passed_through_unchanged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component(repo_root, "one")
    _write_component(repo_root, "two")

    results = {
        "comp-one": _passing_result("comp-one"),
        "comp-two": _passing_result("comp-two"),
    }
    config = {
        "provenance_key": {
            "spec_bundle_hash": "sha256:k1",
            "gate_versions": {"verifier": "v@1"},
        },
        "results": results,
        "blast_radius": {"impacted": [], "precondition_error": None},
    }
    _write_provenance_checker(repo_root, config)
    _write_component_gate_runner(repo_root)

    provenance_tracker.check_readiness(repo_root, changed_ids=None)

    log_path = _calls_log(repo_root)
    assert log_path.exists()
    checked = False
    for line in log_path.read_text().splitlines():
        entry = json.loads(line)
        if entry["event"] == "check_provenance":
            checked = True
            assert entry["spec_bundle_hash"] == "sha256:k1"
            assert entry["gate_versions"] == {"verifier": "v@1"}
    assert checked