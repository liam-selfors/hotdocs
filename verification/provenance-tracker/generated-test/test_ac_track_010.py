# hotdocs-criterion: sha256:29dc1927a981d69362458c347414cc1c92022c84475825589d85739fd0459b14
import json
from pathlib import Path

import provenance_tracker


MODEL = "anthropic:claude-sonnet-5"
SEED = 7


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PASSING_VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.92,
    "mutation_error": None,
    "assets": [
        {
            "kind": "python",
            "path": ".",
            "definition_sha256": None,
            "adapter_sha256": "sha256:" + "a" * 64,
            "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }
    ],
    "overall": "pass",
}

LICENSE_SCAN = {
    "component_id": "comp-foo",
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
}

SECRET_SCAN = {
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


def _provenance_checker_source():
    return (
        "class _Key:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "\n"
        "VERIFICATION_REPORT = " + repr(PASSING_VERIFICATION_REPORT) + "\n"
        "LICENSE_SCAN = " + repr(LICENSE_SCAN) + "\n"
        "SECRET_SCAN = " + repr(SECRET_SCAN) + "\n"
        "GATE_VERSIONS = " + repr({
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
            "generator": "generator@3.0.0+v11",
        }) + "\n"
        "ASSETS = " + repr([
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": "sha256:" + "b" * 64,
                "adapter_sha256": "sha256:" + "c" * 64,
                "versions": {"python": "3.12.4", "packages": "sha256:" + "d" * 64},
                "lockfile_sha256": None,
            }
        ]) + "\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    return _Key(" + repr("sha256:" + "e" * 64) + ", dict(GATE_VERSIONS), list(ASSETS))\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    report = dict(VERIFICATION_REPORT)\n"
        "    report['component_id'] = component_id\n"
        "    return {\n"
        "        'hit': True,\n"
        "        'reason': None,\n"
        "        'verification_report': report,\n"
        "        'license_scan': dict(LICENSE_SCAN),\n"
        "        'secret_scan': dict(SECRET_SCAN),\n"
        "    }\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    return {\n"
        "        'hit': False,\n"
        "        'sealed': False,\n"
        "        'reason': 'not_sealed',\n"
        "        'verification_report': None,\n"
        "        'license_scan': None,\n"
        "        'secret_scan': None,\n"
        "        'owners': None,\n"
        "        'source_hash': None,\n"
        "        'written_at': None,\n"
        "    }\n"
    )


def _capability_verifier_source(log_path):
    return (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "CONFIG = Path(__file__).resolve().parent / 'fake_config.json'\n"
        "GATE_VERSION = 'capability_scenario_verifier@2.2.0'\n"
        "\n"
        "class UnknownCapabilityError(ValueError):\n"
        "    pass\n"
        "\n"
        "class ModelRequiredError(ValueError):\n"
        "    pass\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def _cfg():\n"
        "    return json.loads(CONFIG.read_text())\n"
        "\n"
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    _log('run_capability_scenarios')\n"
        "    return {}\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    _log('check_capability_provenance\\t' + str(capability_id))\n"
        "    return _cfg()['check'][capability_id]\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    _log('run_capability_gates\\t' + str(capability_id) + '\\t' + repr(model)"
        " + '\\t' + repr(seed) + '\\t' + repr(llm_backend))\n"
        "    return _cfg()['gates'][capability_id]\n"
    )


def _write_component(repo_root, slug, upper, realizes):
    comp_dir = repo_root / "specs" / "components" / slug
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)
    (comp_dir / "interface").mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [" + ", ".join(realizes) + "]\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
        "\n"
        "A fixture component.\n"
    )
    rid = "R-" + upper + "-001"
    (comp_dir / "requirements" / (rid + ".md")).write_text(
        "# " + rid + "\n\n**" + rid + "** — The component MUST do its job.\n"
    )
    acid = "AC-" + upper + "-001"
    (comp_dir / "acceptance" / (acid + ".md")).write_text(
        "# " + acid + "\n\nCovers: " + rid + "\nKind: compiled\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n"
    )
    (comp_dir / "interface" / "library.md").write_text("# Library\n\nNothing.\n")


def _build_repo(tmp_path, check_result, gates_result):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("")

    _write_component(repo_root, "foo", "FOO", ["P-FOO"])
    _write_component(repo_root, "bar", "BAR", [])

    product = repo_root / "specs" / "product"
    product.mkdir(parents=True)
    (product / "foo.md").write_text(
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# P-FOO\n"
        "\n"
        "The product MUST foo.\n"
        "\n"
        "## CS-FOO-001\n"
        "\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\nGiven foo\nWhen bar\nThen baz\n```\n"
    )

    pc_dir = repo_root / "gen" / "provenance-checker"
    pc_dir.mkdir(parents=True)
    (pc_dir / "provenance_checker.py").write_text(_provenance_checker_source())

    csv_dir = repo_root / "gen" / "capability-scenario-verifier"
    csv_dir.mkdir(parents=True)
    (csv_dir / "capability_scenario_verifier.py").write_text(
        _capability_verifier_source(log_path)
    )
    (csv_dir / "fake_config.json").write_text(
        json.dumps({"check": {"P-FOO": check_result}, "gates": {"P-FOO": gates_result}})
    )
    return repo_root, log_path


def _log_lines(log_path):
    return [line for line in log_path.read_text().splitlines() if line]


def _gates_calls(log_path):
    return [l for l in _log_lines(log_path) if l.startswith("run_capability_gates\t")]


MISS = {"hit": False, "capability_scenario_report": None}

PASSING_GATES = {
    "hit": False,
    "capability_scenario_report": {
        "P-FOO": {
            "overall": "pass",
            "scenarios": [
                {"id": "CS-FOO-001", "kind": "compiled", "result": "pass"}
            ],
        }
    },
}

EMPTY_REPORT = {"P-FOO": {"overall": "fail", "scenarios": []}}

NO_SCENARIOS_REASON = (
    "P-FOO: has no capability scenarios; add a CS- scenario to its file under specs/product/"
)


def test_all_passing_is_ready(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, MISS, PASSING_GATES)

    report = provenance_tracker.check_readiness(
        repo_root, model=MODEL, seed=SEED, llm_backend=None
    )

    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []

    lines = _log_lines(log_path)
    assert "check_capability_provenance\tP-FOO" in lines
    expected = "run_capability_gates\tP-FOO\t" + repr(MODEL) + "\t" + repr(SEED) + "\tNone"
    assert _gates_calls(log_path) == [expected]
    assert lines.index("check_capability_provenance\tP-FOO") < lines.index(expected)


def test_failing_scenarios_named_in_one_reason(tmp_path):
    gates = {
        "hit": False,
        "capability_scenario_report": {
            "P-FOO": {
                "overall": "fail",
                "scenarios": [
                    {"id": "CS-FOO-001", "kind": "compiled", "result": "pass"},
                    {"id": "CS-FOO-002", "kind": "llm-judge", "result": "fail"},
                    {"id": "CS-FOO-003", "kind": "llm-judge", "result": "skipped"},
                    {"id": "CS-FOO-004", "kind": "generated-test", "result": "fail"},
                ],
            }
        },
    }
    repo_root, log_path = _build_repo(tmp_path, MISS, gates)

    report = provenance_tracker.check_readiness(
        repo_root, model=MODEL, seed=SEED, llm_backend=None
    )

    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "P-FOO: capability scenarios failed: CS-FOO-002, CS-FOO-004"
    ]
    assert len(_gates_calls(log_path)) == 1


def test_empty_scenarios_after_run(tmp_path):
    gates = {"hit": False, "capability_scenario_report": EMPTY_REPORT}
    repo_root, log_path = _build_repo(tmp_path, MISS, gates)

    report = provenance_tracker.check_readiness(
        repo_root, model=MODEL, seed=SEED, llm_backend=None
    )

    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [NO_SCENARIOS_REASON]
    assert len(_gates_calls(log_path)) == 1


def test_hit_with_empty_scenarios_short_circuits(tmp_path):
    check = {"hit": True, "capability_scenario_report": EMPTY_REPORT}
    repo_root, log_path = _build_repo(tmp_path, check, PASSING_GATES)

    report = provenance_tracker.check_readiness(
        repo_root, model=MODEL, seed=SEED, llm_backend=None
    )

    assert list(field(report, "not_ready_reasons")) == [NO_SCENARIOS_REASON]
    assert field(report, "ready") is False
    assert "check_capability_provenance\tP-FOO" in _log_lines(log_path)
    assert _gates_calls(log_path) == []


def test_miss_without_model_reports_not_ready(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, MISS, PASSING_GATES)

    report = provenance_tracker.check_readiness(repo_root, model=None)

    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "P-FOO: needs a fresh run; pass --model"
    ]
    components = field(report, "components")
    assert "comp-foo" in components
    assert "comp-bar" in components
    assert "check_capability_provenance\tP-FOO" in _log_lines(log_path)
    assert _gates_calls(log_path) == []