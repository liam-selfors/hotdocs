import json
import textwrap
from pathlib import Path

import pytest

import provenance_tracker


MODEL = "anthropic:claude-sonnet-5"
SEED = 7
BACKEND = "backend-sentinel"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# ---------------------------------------------------------------------------
# Fixture construction
# ---------------------------------------------------------------------------

def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _component_md(slug: str, capability: str) -> str:
    return textwrap.dedent(
        f"""\
        ---
        id: comp-{slug}
        title: Component {slug}
        status: draft
        owners: [team-{slug}]
        depends_on: []
        realizes: [{capability}]
        sealed: false
        ---

        # comp-{slug}

        A synthetic component realizing {capability}.
        """
    )


def _product_md(cap_id: str, name: str) -> str:
    suffix = cap_id[len("P-"):]
    return textwrap.dedent(
        f"""\
        ---
        id: {cap_id}
        title: Capability {name}
        status: draft
        owners: [product-team]
        ---

        # {cap_id}

        A synthetic product capability.

        ### CS-{suffix}-001

        Covers: {cap_id}
        Kind: generated-test

        ```gherkin
        Given a thing
        When it is exercised
        Then it works
        ```
        """
    )


PROVENANCE_CHECKER_FAKE = '''
import json
from types import SimpleNamespace

LOG_PATH = {log_path!r}


def _log(record):
    with open(LOG_PATH, "a") as fh:
        fh.write(json.dumps(record) + "\\n")


def current_sealed_key(component_id, repo_root):
    _log({{"fn": "current_sealed_key", "component_id": component_id}})
    return None


def current_provenance_key(component_id, repo_root):
    _log({{"fn": "current_provenance_key", "component_id": component_id}})
    return SimpleNamespace(
        spec_bundle_hash="sha256:" + "ab" * 32,
        gate_versions={{
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        }},
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log({{"fn": "check_provenance", "component_id": component_id}})
    return {{
        "hit": True,
        "verification_report": {{
            "component_id": component_id,
            "criteria": [
                {{"id": "AC-X-001", "covers": "R-X-001", "kind": "compiled", "result": "pass"}}
            ],
            "requirement_results": {{"R-X-001": "pass"}},
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": "pass",
        }},
        "license_scan": {{
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
    _log({{"fn": "check_sealed_provenance", "component_id": component_id}})
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


CAPABILITY_VERIFIER_FAKE = '''
import json

LOG_PATH = {log_path!r}
FAILING = {failing!r}

GATE_VERSION = "capability_scenario_verifier@2.0.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


def _log(record):
    with open(LOG_PATH, "a") as fh:
        fh.write(json.dumps(record) + "\\n")


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    _log({{"fn": "run_capability_scenarios"}})
    return {{}}


def check_capability_provenance(capability_id, repo_root):
    _log({{"fn": "check_capability_provenance", "capability_id": capability_id}})
    return {{"hit": False, "capability_scenario_report": None}}


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    _log({{
        "fn": "run_capability_gates",
        "capability_id": capability_id,
        "model": model,
        "seed": seed,
        "llm_backend": llm_backend if isinstance(llm_backend, (str, type(None))) else repr(llm_backend),
    }})
    suffix = capability_id[len("P-"):]
    result = "fail" if capability_id in FAILING else "pass"
    return {{
        "hit": False,
        "capability_scenario_report": {{
            capability_id: {{
                "overall": result,
                "scenarios": [
                    {{"id": "CS-" + suffix + "-001", "kind": "generated-test", "result": result}}
                ],
            }}
        }},
    }}
'''


IMPACT_ANALYZER_FAKE = '''
def compute_blast_radius(changed_ids, repo_root):
    return {
        "impacted": [
            {"component_id": c, "reason": "direct", "via": None}
            for c in changed_ids
            if c.startswith("comp-")
        ],
        "precondition_error": None,
    }
'''


def _build_repo(tmp_path: Path, failing=()):
    repo = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    prov_log = log_dir / "provenance_checker.jsonl"
    cap_log = log_dir / "capability_verifier.jsonl"
    prov_log.write_text("")
    cap_log.write_text("")

    _write(repo / "specs" / "components" / "alpha" / "component.md",
           _component_md("alpha", "P-ONE"))
    _write(repo / "specs" / "components" / "beta" / "component.md",
           _component_md("beta", "P-TWO"))
    _write(repo / "specs" / "product" / "one.md", _product_md("P-ONE", "one"))
    _write(repo / "specs" / "product" / "two.md", _product_md("P-TWO", "two"))
    _write(repo / "gen" / "alpha" / "alpha.py", "VALUE = 1\n")
    _write(repo / "gen" / "beta" / "beta.py", "VALUE = 2\n")

    _write(repo / "gen" / "provenance-checker" / "provenance_checker.py",
           PROVENANCE_CHECKER_FAKE.format(log_path=str(prov_log)))
    _write(repo / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
           CAPABILITY_VERIFIER_FAKE.format(log_path=str(cap_log), failing=list(failing)))
    _write(repo / "gen" / "impact-analyzer" / "impact_analyzer.py", IMPACT_ANALYZER_FAKE)

    return repo, prov_log, cap_log


def _read_log(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def test_all_components_and_capabilities_pass_is_ready(tmp_path):
    repo, prov_log, cap_log = _build_repo(tmp_path)

    report = provenance_tracker.check_readiness(
        repo, None, model=MODEL, seed=SEED, llm_backend=BACKEND
    )

    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []

    calls = _read_log(cap_log)
    checked = [c["capability_id"] for c in calls if c["fn"] == "check_capability_provenance"]
    ran = [c for c in calls if c["fn"] == "run_capability_gates"]
    assert sorted(checked) == ["P-ONE", "P-TWO"]
    assert sorted(c["capability_id"] for c in ran) == ["P-ONE", "P-TWO"]
    assert not any(c["fn"] == "run_capability_scenarios" for c in calls)

    # check-then-run ordering, and model/seed/llm_backend passed through unchanged
    for cap in ("P-ONE", "P-TWO"):
        idx_check = next(i for i, c in enumerate(calls)
                         if c["fn"] == "check_capability_provenance" and c["capability_id"] == cap)
        idx_run = next(i for i, c in enumerate(calls)
                       if c["fn"] == "run_capability_gates" and c["capability_id"] == cap)
        assert idx_check < idx_run
    for c in ran:
        assert c["model"] == MODEL
        assert c["seed"] == SEED
        assert c["llm_backend"] == BACKEND

    capabilities = field(report, "capabilities")
    assert set(capabilities.keys()) == {"P-ONE", "P-TWO"}


def test_one_failing_capability_makes_not_ready_despite_components_passing(tmp_path):
    repo, prov_log, cap_log = _build_repo(tmp_path, failing=("P-TWO",))

    report = provenance_tracker.check_readiness(
        repo, None, model=MODEL, seed=SEED, llm_backend=BACKEND
    )

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    assert reasons, "not_ready_reasons must name the failing capability"
    assert any("P-TWO" in str(r) for r in reasons)
    assert not any("P-ONE" in str(r) for r in reasons)

    # every component passed provenance checking
    prov_calls = _read_log(prov_log)
    checked_components = {c["component_id"] for c in prov_calls if c["fn"] == "check_provenance"}
    assert checked_components == {"comp-alpha", "comp-beta"}
    components = field(report, "components")
    for cid in ("comp-alpha", "comp-beta"):
        assert field(components[cid], "hit") is True

    ran = [c["capability_id"] for c in _read_log(cap_log) if c["fn"] == "run_capability_gates"]
    assert "P-TWO" in ran


def test_capability_miss_without_model_raises_value_error(tmp_path):
    repo, prov_log, cap_log = _build_repo(tmp_path)

    with pytest.raises(ValueError):
        provenance_tracker.check_readiness(
            repo, None, model=None, seed=SEED, llm_backend=BACKEND
        )

    calls = _read_log(cap_log)
    assert any(c["fn"] == "check_capability_provenance" for c in calls)
    assert not any(c["fn"] == "run_capability_gates" for c in calls)
    assert not any(c["fn"] == "run_capability_scenarios" for c in calls)