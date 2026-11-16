import json
import textwrap
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SHARED_CHANGED = ["comp-seed"]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _component_md(slug: str) -> str:
    return (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug} test component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: false\n"
        "realizes: []\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        f"# comp-{slug}\n"
        "\n"
        "Synthetic fixture component.\n"
    )


def _impact_analyzer_source(log_path: Path, distinctive_id: str) -> str:
    return textwrap.dedent(
        f'''
        import json
        from pathlib import Path

        _LOG = {str(log_path)!r}
        _DISTINCTIVE = {distinctive_id!r}


        def compute_blast_radius(changed_ids, repo_root):
            with open(_LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({{
                    "changed_ids": list(changed_ids),
                    "repo_root": str(repo_root),
                }}) + "\\n")
            impacted = []
            for cid in changed_ids:
                impacted.append({{"component_id": cid, "reason": "direct", "via": None}})
            impacted.append({{
                "component_id": _DISTINCTIVE,
                "reason": "transitive-interface",
                "via": changed_ids[0] if changed_ids else None,
            }})
            return {{"impacted": impacted, "precondition_error": None}}
        '''
    )


def _provenance_checker_source(log_path: Path) -> str:
    return textwrap.dedent(
        f'''
        import json

        _LOG = {str(log_path)!r}


        class ProvenanceKey:
            def __init__(self, spec_bundle_hash, gate_versions):
                self.spec_bundle_hash = spec_bundle_hash
                self.gate_versions = gate_versions


        def _log(fn, component_id, repo_root):
            with open(_LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({{
                    "fn": fn,
                    "component_id": component_id,
                    "repo_root": str(repo_root),
                }}) + "\\n")


        def current_sealed_key(component_id, repo_root):
            _log("current_sealed_key", component_id, repo_root)
            return None


        def current_provenance_key(component_id, repo_root):
            _log("current_provenance_key", component_id, repo_root)
            return ProvenanceKey(
                "sha256:" + "0" * 64,
                {{
                    "compiler": "criterion-compiler@1.0.0",
                    "generated_test": "generated_test@1.0.0",
                    "verifier": "verifier-orchestrator@2.0.0",
                    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
                    "secret_scanner": "secret_scanner@0.0.0",
                }},
            )


        def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
            _log("check_provenance", component_id, repo_root)
            return {{
                "hit": True,
                "verification_report": {{
                    "component_id": component_id,
                    "criteria": [
                        {{"id": "AC-X-001", "covers": "R-X-001", "kind": "compiled", "result": "pass"}}
                    ],
                    "requirement_results": {{"R-X-001": "pass"}},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                }},
                "license_scan": {{
                    "component_id": component_id,
                    "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
                    "evaluated": True,
                    "reason": None,
                    "similarity_score": 0.0,
                    "block_threshold": 0.70,
                    "blocked": False,
                    "matches": [],
                    "notified": False,
                    "notification_delivery_error": None,
                    "cache_hit": False,
                }},
                "secret_scan": {{
                    "scope": "full",
                    "gate_version": "secret_scanner@0.0.0",
                    "flagged": False,
                    "matches": [],
                    "allowed": [],
                    "unused_allowlist_entries": [],
                    "notified": False,
                    "notification_delivery_error": None,
                    "cache_hit": False,
                }},
            }}


        def check_sealed_provenance(component_id, repo_root):
            _log("check_sealed_provenance", component_id, repo_root)
            return {{
                "hit": False,
                "sealed": False,
                "reason": "not_sealed",
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
                "owners": None,
                "source_hash": None,
                "written_at": None,
            }}
        '''
    )


def _capability_verifier_source() -> str:
    return textwrap.dedent(
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
            return check_capability_provenance(capability_id, repo_root)
        '''
    )


def _build_repo(repo_root: Path, distinctive_slug: str) -> dict:
    repo_root.mkdir(parents=True, exist_ok=True)
    distinctive_id = f"comp-{distinctive_slug}"
    impact_log = repo_root / "impact_calls.jsonl"
    prov_log = repo_root / "provenance_calls.jsonl"

    for slug in ("seed", distinctive_slug):
        _write(repo_root / "specs" / "components" / slug / "component.md", _component_md(slug))

    _write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        _impact_analyzer_source(impact_log, distinctive_id),
    )
    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        _provenance_checker_source(prov_log),
    )
    _write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        _capability_verifier_source(),
    )
    return {
        "repo_root": repo_root,
        "distinctive_id": distinctive_id,
        "impact_log": impact_log,
        "prov_log": prov_log,
    }


def _read_log(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _same_path(a, b) -> bool:
    return Path(a).resolve() == Path(b).resolve()


@pytest.mark.parametrize("order", ["ab", "ba"])
def test_each_call_resolves_impact_analyzer_from_its_own_repo_root(tmp_path, order):
    repo_a = _build_repo(tmp_path / "repo_a", "alpha-impact")
    repo_b = _build_repo(tmp_path / "repo_b", "beta-impact")
    repos = {"a": repo_a, "b": repo_b}

    results = {}
    for key in order:
        repo = repos[key]
        results[key] = provenance_tracker.check_readiness(
            repo["repo_root"], changed_ids=list(SHARED_CHANGED)
        )

    for key, other_key in (("a", "b"), ("b", "a")):
        repo = repos[key]
        other = repos[other_key]
        result = results[key]

        components = field(result, "components")
        component_ids = set(components.keys())

        # The result reflects this call's own repo_root's fake impact-analyzer...
        assert repo["distinctive_id"] in component_ids, (
            f"repo {key}: expected its own fake's distinctive id "
            f"{repo['distinctive_id']!r} in components, got {sorted(component_ids)!r}"
        )
        # ...never the other repo_root's fake.
        assert other["distinctive_id"] not in component_ids, (
            f"repo {key}: result leaked the other repo's fake id "
            f"{other['distinctive_id']!r}: {sorted(component_ids)!r}"
        )
        # Exactly the blast radius its own fake returned (not a real analyzer's answer).
        assert component_ids == {"comp-seed", repo["distinctive_id"]}

        assert field(result, "scope") == "blast-radius"

        # Each repo's own fake was invoked exactly once, for its own repo_root only.
        impact_calls = _read_log(repo["impact_log"])
        assert len(impact_calls) == 1, (
            f"repo {key}: expected its own fake compute_blast_radius to be called "
            f"exactly once, got {impact_calls!r}"
        )
        assert impact_calls[0]["changed_ids"] == SHARED_CHANGED
        assert _same_path(impact_calls[0]["repo_root"], repo["repo_root"])