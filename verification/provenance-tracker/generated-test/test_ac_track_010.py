"""AC-TRACK-010 (covers R-TRACK-010).

check_readiness additionally checks every product capability whose
realizes-set intersects the resolved component scope: check-then-run
through capability-scenario-verifier. Here every capability's
check_capability_provenance is faked to return hit false, so
run_capability_gates is exercised for it.
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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _make_component(repo_root: Path, slug: str, realizes: list[str]) -> None:
    upper = slug.upper()
    comp_dir = repo_root / "specs" / "components" / slug
    realizes_flow = "[" + ", ".join(realizes) + "]"
    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} component\n"
        "status: draft\n"
        "owners: [team-a]\n"
        f"realizes: {realizes_flow}\n"
        "sealed: false\n"
        "---\n\n"
        f"# comp-{slug}\n\n"
        f"The {slug} component exists to be checked for readiness.\n",
    )
    _write(
        comp_dir / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n"
        f"**R-{upper}-001** — `do_{slug}()` MUST return the integer 1.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given nothing\n"
        f"When do_{slug} is called\n"
        "Then it returns 1\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n"
        "```\n"
        f"do_{slug}() -> int\n"
        "```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        repo_root / "gen" / slug / f"{slug}.py",
        f"def do_{slug}():\n    return 1\n",
    )


def _make_capability(repo_root: Path, name: str, cap_id: str) -> None:
    scenario = cap_id.replace("P-", "CS-", 1) + "-001"
    _write(
        repo_root / "specs" / "product" / f"{name}.md",
        "---\n"
        f"id: {cap_id}\n"
        f"title: {name.capitalize()} capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n\n"
        f"# {cap_id}\n\n"
        f"The product MUST support {name}.\n\n"
        f"### {scenario}\n\n"
        f"Covers: {cap_id}\n"
        "Kind: compiled\n\n"
        "```gherkin\n"
        "Given a working tree\n"
        "When the capability is exercised\n"
        "Then it succeeds\n"
        "```\n",
    )


PROVENANCE_CHECKER_FAKE = '''\
import json

LOG = {log!r}


def _log(rec):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\\n")


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions

    def __getitem__(self, key):
        return getattr(self, key)


def current_sealed_key(component_id, repo_root):
    _log({{"fn": "current_sealed_key", "component_id": str(component_id)}})
    return None


def current_provenance_key(component_id, repo_root):
    _log({{"fn": "current_provenance_key", "component_id": str(component_id)}})
    return ProvenanceKey(
        "sha256:0123456789abcdef",
        {{
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        }},
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log({{"fn": "check_provenance", "component_id": str(component_id)}})
    rid = "R-" + str(component_id).replace("comp-", "").upper() + "-001"
    aid = "AC-" + str(component_id).replace("comp-", "").upper() + "-001"
    return {{
        "hit": True,
        "verification_report": {{
            "component_id": str(component_id),
            "criteria": [
                {{"id": aid, "covers": rid, "kind": "generated-test", "result": "pass"}}
            ],
            "requirement_results": {{rid: "pass"}},
            "interface_drift": False,
            "mutation_score": 0.92,
            "overall": "pass",
        }},
        "license_scan": {{
            "component_id": str(component_id),
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.05,
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
    _log({{"fn": "check_sealed_provenance", "component_id": str(component_id)}})
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


CAPABILITY_VERIFIER_FAKE = '''\
import json

LOG = {log!r}
OUTCOMES = {outcomes!r}

GATE_VERSION = "capability_scenario_verifier@2.0.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


def _log(rec):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\\n")


def check_capability_provenance(capability_id, repo_root):
    _log({{"fn": "check_capability_provenance", "capability_id": str(capability_id)}})
    return {{"hit": False, "capability_scenario_report": None}}


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    _log({{
        "fn": "run_capability_gates",
        "capability_id": str(capability_id),
        "model": model,
        "seed": seed,
        "llm_backend": repr(llm_backend),
    }})
    result = OUTCOMES.get(str(capability_id), "pass")
    scenario_id = str(capability_id).replace("P-", "CS-", 1) + "-001"
    return {{
        "hit": False,
        "capability_scenario_report": {{
            str(capability_id): {{
                "overall": result,
                "scenarios": [
                    {{"id": scenario_id, "kind": "compiled", "result": result}}
                ],
            }}
        }},
    }}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    _log({{"fn": "run_capability_scenarios"}})
    return {{}}
'''


def _install_fakes(repo_root: Path, log_path: Path, outcomes: dict) -> None:
    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        PROVENANCE_CHECKER_FAKE.format(log=str(log_path)),
    )
    _write(
        repo_root / "gen" / "capability-scenario-verifier"
        / "capability_scenario_verifier.py",
        CAPABILITY_VERIFIER_FAKE.format(log=str(log_path), outcomes=outcomes),
    )


def _build_two_capability_repo(tmp_path: Path, outcomes: dict):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "invocations.jsonl"
    _make_component(repo_root, "foo", ["P-ALPHA"])
    _make_component(repo_root, "bar", ["P-BETA"])
    _make_capability(repo_root, "alpha", "P-ALPHA")
    _make_capability(repo_root, "beta", "P-BETA")
    _install_fakes(repo_root, log_path, outcomes)
    return repo_root, log_path


MODEL = "anthropic:claude-sonnet-5"
SEED = 7
BACKEND = "backend-sentinel"


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------

def test_all_components_hit_and_all_capabilities_pass_is_ready(tmp_path):
    repo_root, log_path = _build_two_capability_repo(
        tmp_path, {"P-ALPHA": "pass", "P-BETA": "pass"}
    )

    report = provenance_tracker.check_readiness(
        repo_root, model=MODEL, seed=SEED, llm_backend=BACKEND
    )

    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []

    # Both intersecting capabilities were actually run through the fake,
    # with model/seed/llm_backend passed through unchanged.
    gate_calls = [r for r in _read_log(log_path) if r["fn"] == "run_capability_gates"]
    called_ids = {r["capability_id"] for r in gate_calls}
    assert called_ids == {"P-ALPHA", "P-BETA"}
    for rec in gate_calls:
        assert rec["model"] == MODEL
        assert rec["seed"] == SEED
        assert rec["llm_backend"] == repr(BACKEND)


def test_one_failing_capability_makes_not_ready_despite_components_passing(tmp_path):
    repo_root, log_path = _build_two_capability_repo(
        tmp_path, {"P-ALPHA": "pass", "P-BETA": "fail"}
    )

    report = provenance_tracker.check_readiness(
        repo_root, model=MODEL, seed=SEED, llm_backend=BACKEND
    )

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    assert any("P-BETA" in str(reason) for reason in reasons), reasons
    assert not any("P-ALPHA" in str(reason) for reason in reasons), reasons

    # Every component passed: each one's provenance result is a hit.
    components = field(report, "components")
    assert set(components.keys()) == {"comp-foo", "comp-bar"}
    for comp_result in components.values():
        assert field(comp_result, "hit") is True

    gate_calls = [r for r in _read_log(log_path) if r["fn"] == "run_capability_gates"]
    assert "P-BETA" in {r["capability_id"] for r in gate_calls}


def test_capability_miss_without_model_raises_value_error(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "invocations.jsonl"
    _make_component(repo_root, "foo", ["P-ALPHA"])
    _make_capability(repo_root, "alpha", "P-ALPHA")
    _install_fakes(repo_root, log_path, {"P-ALPHA": "pass"})

    with pytest.raises(ValueError):
        provenance_tracker.check_readiness(repo_root, model=None)

    gate_calls = [r for r in _read_log(log_path) if r["fn"] == "run_capability_gates"]
    assert gate_calls == []