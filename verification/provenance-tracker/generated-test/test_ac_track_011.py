# hotdocs-criterion: sha256:8bd7df06685d163ecb6d746030d5b93b96fb7cb20bcbd4ce0724d9f0d567cee5
import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


IMPACT_TEMPLATE_TAIL = '''

def _log():
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write("compute_blast_radius\\n")


def compute_blast_radius(changed_ids, repo_root):
    _log()
    return {
        "impacted": [
            {"component_id": cid, "reason": "direct" if i == 0 else "transitive-interface",
             "via": None if i == 0 else IMPACTED[0]}
            for i, cid in enumerate(IMPACTED)
        ],
        "precondition_error": None,
    }
'''


PROV_CHECKER_TAIL = '''


class _Obj:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        self._keys = list(kw)

    def __getitem__(self, key):
        if key not in self._keys:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key) if key in self._keys else default

    def keys(self):
        return list(self._keys)


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _verification_report(component_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-X-001", "covers": "R-X-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-X-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "overall": "pass",
    }


def current_sealed_key(component_id, repo_root):
    return _Obj(
        owners=["pipeline-team"],
        source_path="legacy/" + _slug(component_id) + "/",
        source_hash="sha256:" + "0" * 64,
        verifier_version="verifier-orchestrator@2.0.0",
    )


def check_sealed_provenance(component_id, repo_root):
    return {
        "hit": True,
        "sealed": True,
        "reason": None,
        "verification_report": {"overall": "pass"},
        "license_scan": None,
        "secret_scan": None,
        "owners": ["pipeline-team"],
        "source_hash": "sha256:" + "0" * 64,
        "written_at": "2026-11-02T00:00:00Z",
    }


def current_provenance_key(component_id, repo_root):
    return _Obj(
        spec_bundle_hash="sha256:abc123",
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {
        "hit": True,
        "verification_report": _verification_report(component_id),
        "license_scan": {
            "component_id": component_id,
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
            "gate_version": "secret_scanner@0.0.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }
'''


CSV_SOURCE = '''
GATE_VERSION = "capability_scenario_verifier@2.0.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


def _report(capability_id):
    return {capability_id: {"overall": "pass", "scenarios": []}}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    return {}


def check_capability_provenance(capability_id, repo_root):
    return {"hit": True, "capability_scenario_report": _report(capability_id)}


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    return {"hit": True, "capability_scenario_report": _report(capability_id)}
'''


def _write_component(repo_root, slug):
    d = repo_root / "specs" / "components" / slug
    d.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n\n"
        + "# " + slug + "\n"
    )
    (d / "component.md").write_text(text, encoding="utf-8")


def _build_repo(repo_root, impacted, log_path):
    repo_root.mkdir(parents=True, exist_ok=True)
    for cid in impacted:
        _write_component(repo_root, cid[len("comp-"):])

    ia_dir = repo_root / "gen" / "impact-analyzer"
    ia_dir.mkdir(parents=True, exist_ok=True)
    ia_src = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        + "IMPACTED = " + repr(list(impacted)) + "\n"
        + IMPACT_TEMPLATE_TAIL
    )
    (ia_dir / "impact_analyzer.py").write_text(ia_src, encoding="utf-8")

    pc_dir = repo_root / "gen" / "provenance-checker"
    pc_dir.mkdir(parents=True, exist_ok=True)
    (pc_dir / "provenance_checker.py").write_text(PROV_CHECKER_TAIL, encoding="utf-8")

    csv_dir = repo_root / "gen" / "capability-scenario-verifier"
    csv_dir.mkdir(parents=True, exist_ok=True)
    (csv_dir / "capability_scenario_verifier.py").write_text(CSV_SOURCE, encoding="utf-8")


def _log_lines(path):
    if not path.exists():
        return []
    return [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _component_ids(report):
    comps = field(report, "components")
    if isinstance(comps, dict):
        return set(comps.keys())
    return set(dict(comps).keys())


@pytest.mark.parametrize("order", ["a_first", "b_first"])
def test_check_readiness_resolves_impact_analyzer_per_repo_root(tmp_path, order):
    logs = tmp_path / "logs"
    logs.mkdir()

    alpha_ids = ["comp-alpha-zebra-one", "comp-alpha-zebra-two"]
    beta_ids = ["comp-beta-quokka-one"]

    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    log_a = logs / "impact_a.log"
    log_b = logs / "impact_b.log"
    _build_repo(repo_a, alpha_ids, log_a)
    _build_repo(repo_b, beta_ids, log_b)

    plan = [("a", repo_a, log_a, log_b, alpha_ids, beta_ids),
            ("b", repo_b, log_b, log_a, beta_ids, alpha_ids)]
    if order == "b_first":
        plan = list(reversed(plan))

    for _name, repo_root, own_log, other_log, own_ids, other_ids in plan:
        own_before = len(_log_lines(own_log))
        other_before = len(_log_lines(other_log))

        report = provenance_tracker.check_readiness(
            repo_root, changed_ids=[own_ids[0]]
        )

        assert len(_log_lines(own_log)) == own_before + 1, (
            "this repo_root's own fake impact-analyzer was not called exactly once"
        )
        assert len(_log_lines(other_log)) == other_before, (
            "the other repo_root's fake impact-analyzer was called"
        )

        assert field(report, "scope") == "blast-radius"
        ids = _component_ids(report)
        for cid in own_ids:
            assert cid in ids, (
                "component " + repr(cid) + " from this repo_root's fake missing: "
                + json.dumps(sorted(ids))
            )
        for cid in other_ids:
            assert cid not in ids, (
                "component " + repr(cid) + " from the other repo_root's fake leaked in"
            )