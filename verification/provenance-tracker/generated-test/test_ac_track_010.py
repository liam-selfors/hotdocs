import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_PROVENANCE_CHECKER = '''
import json

LOG_PATH = {log_path!r}


def _log(record):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


class _Key:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log({{"fn": "current_sealed_key", "component_id": component_id}})
    return None


def current_provenance_key(component_id, repo_root):
    _log({{"fn": "current_provenance_key", "component_id": component_id}})
    return _Key(
        "sha256:abc123",
        {{
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
                {{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}}
            ],
            "requirement_results": {{"R-FOO-001": "pass"}},
            "interface_drift": False,
            "mutation_score": 0.92,
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


FAKE_CAPABILITY_VERIFIER = '''
import json

LOG_PATH = {log_path!r}
CONFIG_PATH = {config_path!r}

GATE_VERSION = "capability_scenario_verifier@2.0.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


def _log(record):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def _outcome(capability_id):
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh).get(capability_id, "pass")


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
    }})
    result = _outcome(capability_id)
    scenario_id = "CS-" + capability_id[2:] + "-001"
    return {{
        "hit": False,
        "capability_scenario_report": {{
            capability_id: {{
                "overall": result,
                "scenarios": [
                    {{"id": scenario_id, "kind": "generated-test", "result": result}}
                ],
            }}
        }},
    }}
'''


def _capability_doc(cap_id, name):
    suffix = cap_id[2:]
    return (
        "---\n"
        f"id: {cap_id}\n"
        f"title: {name} capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n\n"
        f"# {cap_id}\n\n"
        f"The system MUST provide the {name} capability.\n\n"
        f"### CS-{suffix}-001\n\n"
        f"Covers: {cap_id}\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a prepared system\n"
        "When the capability is exercised\n"
        "Then it behaves as specified\n"
        "```\n"
    )


def build_repo(tmp_path, outcomes):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "invocations.log"
    log_path.write_text("", encoding="utf-8")
    config_path = tmp_path / "outcomes.json"
    config_path.write_text(json.dumps(outcomes), encoding="utf-8")

    (repo_root / "specs").mkdir()
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )

    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)
    (comp_dir / "interface").mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "realizes: [P-ALPHA, P-BETA]\n"
        "---\n\n"
        "# comp-foo\n\nA test component.\n",
        encoding="utf-8",
    )
    (comp_dir / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — The component MUST do foo.\n", encoding="utf-8"
    )
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen foo runs\nThen foo is done\n```\n",
        encoding="utf-8",
    )
    (comp_dir / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo() -> None\n```\n", encoding="utf-8"
    )
    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "gen" / "foo" / "foo.py").write_text(
        "def foo():\n    return None\n", encoding="utf-8"
    )

    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True)
    (product_dir / "alpha.md").write_text(_capability_doc("P-ALPHA", "alpha"), encoding="utf-8")
    (product_dir / "beta.md").write_text(_capability_doc("P-BETA", "beta"), encoding="utf-8")

    pc_dir = repo_root / "gen" / "provenance-checker"
    pc_dir.mkdir(parents=True)
    (pc_dir / "provenance_checker.py").write_text(
        FAKE_PROVENANCE_CHECKER.format(log_path=str(log_path)), encoding="utf-8"
    )

    csv_dir = repo_root / "gen" / "capability-scenario-verifier"
    csv_dir.mkdir(parents=True)
    (csv_dir / "capability_scenario_verifier.py").write_text(
        FAKE_CAPABILITY_VERIFIER.format(
            log_path=str(log_path), config_path=str(config_path)
        ),
        encoding="utf-8",
    )
    return repo_root, log_path


def read_log(log_path):
    lines = Path(log_path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def calls(log, fn):
    return [r for r in log if r.get("fn") == fn]


def test_all_components_and_capabilities_pass_is_ready(tmp_path):
    repo_root, log_path = build_repo(tmp_path, {"P-ALPHA": "pass", "P-BETA": "pass"})

    report = provenance_tracker.check_readiness(
        repo_root, model="fake-model", seed=7, llm_backend=None
    )

    log = read_log(log_path)
    gated = {r["capability_id"] for r in calls(log, "run_capability_gates")}
    assert gated == {"P-ALPHA", "P-BETA"}

    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []


def test_one_failing_capability_makes_not_ready(tmp_path):
    repo_root, log_path = build_repo(tmp_path, {"P-ALPHA": "pass", "P-BETA": "fail"})

    report = provenance_tracker.check_readiness(
        repo_root, model="fake-model", seed=7, llm_backend=None
    )

    log = read_log(log_path)
    gated = {r["capability_id"] for r in calls(log, "run_capability_gates")}
    assert "P-BETA" in gated

    components = field(report, "components")
    assert "comp-foo" in components
    assert field(components["comp-foo"], "hit") is True

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    assert any("P-BETA" in str(r) for r in reasons), reasons


def test_capability_miss_without_model_raises_value_error(tmp_path):
    repo_root, log_path = build_repo(tmp_path, {"P-ALPHA": "pass", "P-BETA": "pass"})

    with pytest.raises(ValueError):
        provenance_tracker.check_readiness(
            repo_root, model=None, seed=0, llm_backend=None
        )

    log = read_log(log_path)
    assert calls(log, "check_capability_provenance"), log
    assert calls(log, "run_capability_gates") == []