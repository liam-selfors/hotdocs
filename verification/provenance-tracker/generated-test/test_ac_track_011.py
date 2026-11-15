import json
import textwrap
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


REPO_A_IDS = ["comp-alpharepo-one", "comp-alpharepo-two"]
REPO_B_IDS = ["comp-betarepo-one", "comp-betarepo-two", "comp-betarepo-three"]


IMPACT_ANALYZER_TEMPLATE = textwrap.dedent(
    '''
    import json

    _IMPACTED_IDS = __IMPACTED_IDS__
    _LOG_PATH = __LOG_PATH__


    def compute_blast_radius(changed_ids, repo_root):
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "changed_ids": list(changed_ids),
                "repo_root": str(repo_root),
            }) + "\\n")
        impacted = []
        first = _IMPACTED_IDS[0]
        for cid in _IMPACTED_IDS:
            if cid == first:
                impacted.append({"component_id": cid, "reason": "direct", "via": None})
            else:
                impacted.append({
                    "component_id": cid,
                    "reason": "transitive-interface",
                    "via": first,
                })
        return {"impacted": impacted, "precondition_error": None}
    '''
)


PROVENANCE_CHECKER_SOURCE = textwrap.dedent(
    '''
    _GATE_VERSIONS = {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
        "secret_scanner": "secret_scanner@0.0.0",
    }


    class ProvenanceKey:
        def __init__(self, spec_bundle_hash, gate_versions):
            self.spec_bundle_hash = spec_bundle_hash
            self.gate_versions = gate_versions


    def current_sealed_key(component_id, repo_root):
        return None


    def current_provenance_key(component_id, repo_root):
        return ProvenanceKey("sha256:" + "ab" * 32, dict(_GATE_VERSIONS))


    def _verification_report(component_id):
        return {
            "component_id": component_id,
            "criteria": [
                {"id": "AC-X-001", "covers": "R-X-001", "kind": "compiled", "result": "pass"}
            ],
            "requirement_results": {"R-X-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": "pass",
        }


    def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
        return {
            "hit": True,
            "verification_report": _verification_report(component_id),
            "license_scan": {
                "component_id": component_id,
                "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
                "evaluated": True,
                "reason": None,
                "similarity_score": 0.0,
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


    def check_sealed_provenance(component_id, repo_root):
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
)


CAPABILITY_VERIFIER_SOURCE = textwrap.dedent(
    '''
    GATE_VERSION = "capability_scenario_verifier@2.0.0"


    class UnknownCapabilityError(ValueError):
        pass


    class ModelRequiredError(ValueError):
        pass


    def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
        return {}


    def check_capability_provenance(capability_id, repo_root):
        return {
            "hit": True,
            "capability_scenario_report": {
                capability_id: {"overall": "pass", "scenarios": []}
            },
        }


    def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
        return {
            "hit": False,
            "capability_scenario_report": {
                capability_id: {"overall": "pass", "scenarios": []}
            },
        }
    '''
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _component_md(component_id: str) -> str:
    slug = component_id[len("comp-"):]
    return (
        "---\n"
        f"id: {component_id}\n"
        f"title: Fixture {slug}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: []\n"
        "depends_on: []\n"
        "sealed: false\n"
        "---\n\n"
        f"# {component_id}\n\nFixture component.\n"
    )


def _build_repo(repo_root: Path, impacted_ids, log_path: Path) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    for cid in impacted_ids:
        slug = cid[len("comp-"):]
        _write(repo_root / "specs" / "components" / slug / "component.md", _component_md(cid))

    impact_src = IMPACT_ANALYZER_TEMPLATE.replace(
        "__IMPACTED_IDS__", repr(list(impacted_ids))
    ).replace("__LOG_PATH__", repr(str(log_path)))
    _write(repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py", impact_src)
    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        PROVENANCE_CHECKER_SOURCE,
    )
    _write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        CAPABILITY_VERIFIER_SOURCE,
    )


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.parametrize("order", ["a_then_b", "b_then_a"])
def test_check_readiness_resolves_impact_analyzer_per_repo_root(tmp_path, order):
    logs = tmp_path / "logs"
    logs.mkdir()
    log_a = logs / "impact_a.jsonl"
    log_b = logs / "impact_b.jsonl"

    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    _build_repo(repo_a, REPO_A_IDS, log_a)
    _build_repo(repo_b, REPO_B_IDS, log_b)

    cases = {
        "a": (repo_a, REPO_A_IDS, REPO_B_IDS, log_a, log_b),
        "b": (repo_b, REPO_B_IDS, REPO_A_IDS, log_b, log_a),
    }
    sequence = ["a", "b"] if order == "a_then_b" else ["b", "a"]

    results = {}
    for key in sequence:
        repo_root, own_ids, _other_ids, _own_log, _other_log = cases[key]
        results[key] = provenance_tracker.check_readiness(
            repo_root,
            changed_ids=[own_ids[0]],
            model="fake:model",
            seed=0,
            llm_backend=None,
        )

    for key in sequence:
        repo_root, own_ids, other_ids, own_log, other_log = cases[key]
        result = results[key]

        assert field(result, "scope") == "blast-radius"

        components = field(result, "components")
        component_keys = set(components.keys())
        assert component_keys == set(own_ids), (
            f"result for repo {key} has components {sorted(component_keys)}, "
            f"expected exactly its own fake's {sorted(own_ids)}"
        )
        for other in other_ids:
            assert other not in component_keys
            assert other not in json.dumps(
                field(result, "not_ready_reasons"), default=str
            )

    # Each fake was invoked exactly once, with its own repo_root.
    for key in ("a", "b"):
        repo_root, own_ids, _other_ids, own_log, _other_log = cases[key]
        entries = _read_log(own_log)
        assert len(entries) == 1, (
            f"repo {key}'s fake impact-analyzer was called {len(entries)} times"
        )
        assert Path(entries[0]["repo_root"]).resolve() == repo_root.resolve()
        assert entries[0]["changed_ids"] == [own_ids[0]]