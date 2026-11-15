"""AC-TRACK-012 (covers R-TRACK-012).

Given a dict-shaped (never object-shaped) fake provenance-checker result and
a dict-shaped fake impact-analyzer impacted entry, when check_readiness runs
over that scope, then it reads hit/component_id/etc. correctly from the dict
shape and does not raise AttributeError.
"""

import json
from pathlib import Path

import pytest

import provenance_tracker


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
    "secret_scanner": "secret_scanner@0.0.0",
}


def hit_result(component_id):
    return {
        "hit": True,
        "verification_report": {
            "component_id": component_id,
            "criteria": [
                {
                    "id": "AC-X-001",
                    "covers": "R-X-001",
                    "kind": "compiled",
                    "result": "pass",
                }
            ],
            "requirement_results": {"R-X-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": "pass",
        },
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


MISS_RESULT = {
    "hit": False,
    "verification_report": None,
    "license_scan": None,
    "secret_scan": None,
}


FAKE_PROVENANCE_CHECKER = '''\
import json

LOG = __LOG__
HIT_IDS = json.loads(__HIT_IDS__)
HIT_TEMPLATES = json.loads(__HIT_TEMPLATES__)
MISS = json.loads(__MISS__)
GATE_VERSIONS = json.loads(__GATES__)


class ProvenanceKey(dict):
    """Documented as an object exposing both fields as attributes."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _log(fn, component_id, **extra):
    rec = {"fn": fn, "component_id": component_id}
    rec.update(extra)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\\n")


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id)
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "ab" * 32,
        gate_versions=dict(GATE_VERSIONS),
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id, spec_bundle_hash=str(spec_bundle_hash))
    if component_id in HIT_IDS:
        return json.loads(json.dumps(HIT_TEMPLATES[component_id]))
    return json.loads(json.dumps(MISS))


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id)
    return {
        "hit": False,
        "sealed": False,
        "reason": "not_sealed",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
        "owners": None,
        "source_hash": None,
        "written_at": None,
    }
'''


FAKE_IMPACT_ANALYZER = '''\
import json

LOG = __LOG__
REPORT = json.loads(__REPORT__)


def compute_blast_radius(changed_ids, repo_root):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"fn": "compute_blast_radius",
                            "changed_ids": list(changed_ids)}) + "\\n")
    return json.loads(json.dumps(REPORT))
'''


FAKE_CAPABILITY_VERIFIER = '''\
import json

LOG = __LOG__
GATE_VERSION = "capability_scenario_verifier@2.0.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


def _report(capability_id):
    return {capability_id: {"overall": "pass", "scenarios": [
        {"id": "CS-DEMO-001", "kind": "compiled", "result": "pass"}]}}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    return {}


def check_capability_provenance(capability_id, repo_root):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"fn": "check_capability_provenance",
                            "capability_id": capability_id}) + "\\n")
    return {"hit": True, "capability_scenario_report": _report(capability_id)}


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"fn": "run_capability_gates",
                            "capability_id": capability_id}) + "\\n")
    if model is None:
        raise ModelRequiredError("model required")
    return {"hit": False, "capability_scenario_report": _report(capability_id)}
'''


def _fill(template, **values):
    out = template
    for key, val in values.items():
        out = out.replace("__%s__" % key, repr(val))
    return out


def _write_component(repo_root, slug):
    upper = slug.upper()
    comp_dir = repo_root / "specs" / "components" / slug
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface").mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug} component\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "realizes: [P-DEMO]\n"
        "depends_on: []\n"
        "---\n\n"
        f"# comp-{slug}\n\nA fixture component.\n",
        encoding="utf-8",
    )
    (comp_dir / "requirements" / f"R-{upper}-001.md").write_text(
        f"# R-{upper}-001\n\n**R-{upper}-001** — The component MUST work.\n",
        encoding="utf-8",
    )
    (comp_dir / "acceptance" / f"AC-{upper}-001.md").write_text(
        f"# AC-{upper}-001\n\nCovers: R-{upper}-001\nKind: compiled\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
        encoding="utf-8",
    )
    (comp_dir / "interface" / "library.md").write_text(
        "# Library\n\n```\nrun() -> None\n```\n", encoding="utf-8"
    )
    code_dir = repo_root / "gen" / slug
    code_dir.mkdir(parents=True, exist_ok=True)
    (code_dir / f"{slug.replace('-', '_')}.py").write_text(
        "def run():\n    return None\n", encoding="utf-8"
    )


def _build_repo(tmp_path, hit_ids):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "invocations.jsonl"
    log.write_text("", encoding="utf-8")

    for slug in ("alpha", "beta"):
        _write_component(repo_root, slug)

    product = repo_root / "specs" / "product"
    product.mkdir(parents=True)
    (product / "demo.md").write_text(
        "---\n"
        "id: P-DEMO\n"
        "title: Demo capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n\n"
        "# P-DEMO\n\n"
        "### CS-DEMO-001\n\n"
        "Covers: P-DEMO\n"
        "Kind: compiled\n\n"
        "```gherkin\nGiven a demo\nWhen it runs\nThen it works\n```\n",
        encoding="utf-8",
    )

    templates = {cid: hit_result(cid) for cid in ("comp-alpha", "comp-beta")}

    pc_dir = repo_root / "gen" / "provenance-checker"
    pc_dir.mkdir(parents=True)
    (pc_dir / "provenance_checker.py").write_text(
        _fill(
            FAKE_PROVENANCE_CHECKER,
            LOG=str(log),
            HIT_IDS=json.dumps(sorted(hit_ids)),
            HIT_TEMPLATES=json.dumps(templates),
            MISS=json.dumps(MISS_RESULT),
            GATES=json.dumps(GATE_VERSIONS),
        ),
        encoding="utf-8",
    )

    impact_report = {
        "impacted": [
            {"component_id": "comp-alpha", "reason": "direct", "via": None},
            {
                "component_id": "comp-beta",
                "reason": "transitive-interface",
                "via": "comp-alpha",
            },
        ],
        "precondition_error": None,
    }
    ia_dir = repo_root / "gen" / "impact-analyzer"
    ia_dir.mkdir(parents=True)
    (ia_dir / "impact_analyzer.py").write_text(
        _fill(FAKE_IMPACT_ANALYZER, LOG=str(log), REPORT=json.dumps(impact_report)),
        encoding="utf-8",
    )

    csv_dir = repo_root / "gen" / "capability-scenario-verifier"
    csv_dir.mkdir(parents=True)
    (csv_dir / "capability_scenario_verifier.py").write_text(
        _fill(FAKE_CAPABILITY_VERIFIER, LOG=str(log)), encoding="utf-8"
    )

    return repo_root, log, templates


def _read_log(log):
    return [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_dict_shaped_results_read_correctly_with_a_miss(tmp_path):
    repo_root, log, templates = _build_repo(tmp_path, hit_ids={"comp-alpha"})

    try:
        report = provenance_tracker.check_readiness(
            repo_root, changed_ids=["comp-alpha"]
        )
    except AttributeError as exc:  # pragma: no cover - the criterion's failure mode
        pytest.fail(f"check_readiness raised AttributeError on dict-shaped input: {exc}")

    assert field(report, "scope") == "blast-radius"

    components = field(report, "components")
    # component_id was read from each dict-shaped impacted entry
    assert "comp-alpha" in components
    assert "comp-beta" in components

    # hit was read from the dict-shaped ProvenanceCheckResult
    alpha = components["comp-alpha"]
    beta = components["comp-beta"]
    assert field(alpha, "hit") is True
    assert field(beta, "hit") is False
    # copied verbatim, not recomputed
    assert alpha == templates["comp-alpha"]
    assert beta == MISS_RESULT

    assert field(report, "ready") is False

    reasons = list(field(report, "not_ready_reasons"))
    assert any("comp-beta" in r for r in reasons), reasons
    assert not any("comp-alpha" in r and "comp-beta" not in r for r in reasons), reasons

    calls = _read_log(log)
    checked = {c["component_id"] for c in calls if c["fn"] == "check_provenance"}
    assert {"comp-alpha", "comp-beta"} <= checked
    assert not any(c["fn"] == "check_sealed_provenance" for c in calls)
    assert any(c["fn"] == "compute_blast_radius" for c in calls)


def test_dict_shaped_results_all_hits_are_ready(tmp_path):
    repo_root, log, templates = _build_repo(
        tmp_path, hit_ids={"comp-alpha", "comp-beta"}
    )

    try:
        report = provenance_tracker.check_readiness(
            repo_root, changed_ids=["comp-alpha"]
        )
    except AttributeError as exc:  # pragma: no cover - the criterion's failure mode
        pytest.fail(f"check_readiness raised AttributeError on dict-shaped input: {exc}")

    assert field(report, "scope") == "blast-radius"

    components = field(report, "components")
    for cid in ("comp-alpha", "comp-beta"):
        assert cid in components
        assert field(components[cid], "hit") is True
        assert components[cid] == templates[cid]

    capabilities = field(report, "capabilities")
    for cap_id, cap in dict(capabilities).items():
        assert field(cap, "hit") is True, cap_id

    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []

    calls = _read_log(log)
    assert not any(c["fn"] == "run_capability_gates" for c in calls)
    assert not any(c["fn"] == "check_sealed_provenance" for c in calls)