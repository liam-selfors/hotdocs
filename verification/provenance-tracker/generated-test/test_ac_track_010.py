# hotdocs-criterion: sha256:d8bda1ad6767d7149c321169793ab16e5dbf7175dba51513b3dcaeb64376f010
"""AC-TRACK-010: check_readiness checks intersecting product capabilities
through capability-scenario-verifier (R-TRACK-010)."""

import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# ---------------------------------------------------------------------------
# Fixture corpus
# ---------------------------------------------------------------------------

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "realizes: [P-FOO]\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A fixture component realizing P-FOO.\n"
)

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 The component MUST exist.\n"
)

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: llm-judge\n"
    "\n"
    "The component exists.\n"
)

INTERFACE_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "foo() -> None\n"
    "```\n"
)

PRODUCT_MD = (
    "---\n"
    "id: P-FOO\n"
    "title: Foo capability\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# P-FOO\n"
    "\n"
    "A fixture product capability.\n"
)


def write_corpus(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)
    (comp / "interface" / "library.md").write_text(INTERFACE_MD)
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n")
    product = repo_root / "specs" / "product"
    product.mkdir(parents=True)
    (product / "foo.md").write_text(PRODUCT_MD)


# ---------------------------------------------------------------------------
# Fake dependencies
# ---------------------------------------------------------------------------

PROVENANCE_CHECKER_SRC = (
    "class _ProvenanceKey:\n"
    "    def __init__(self):\n"
    "        self.spec_bundle_hash = 'sha256:' + 'a' * 64\n"
    "        self.spec_bundle_parts = {'spec': 'sha256:' + 'b' * 64, 'dependency_code': 'sha256:' + 'c' * 64}\n"
    "        self.gate_versions = {\n"
    "            'compiler': 'criterion-compiler@1.0.0',\n"
    "            'generated_test': 'generated_test@1.0.0',\n"
    "            'verifier': 'verifier-orchestrator@2.0.0',\n"
    "            'license_scanner': 'license_scanner@4.0.3+9f2c41ab07de',\n"
    "            'secret_scanner': 'secret_scanner@0.0.0',\n"
    "            'generator': 'generator@3.0.0+v11',\n"
    "        }\n"
    "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                        'adapter_sha256': 'sha256:' + 'd' * 64,\n"
    "                        'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}]\n"
    "        self.drivers = []\n"
    "\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    return None\n"
    "\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    return _ProvenanceKey()\n"
    "\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
    "    return {\n"
    "        'hit': True,\n"
    "        'reason': None,\n"
    "        'verification_report': {\n"
    "            'component_id': component_id,\n"
    "            'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'llm-judge',\n"
    "                          'result': 'pass', 'rationale': 'ok'}],\n"
    "            'requirement_results': {'R-FOO-001': 'pass'},\n"
    "            'interface_drift': False,\n"
    "            'mutation_score': 0.9,\n"
    "            'mutation_error': None,\n"
    "            'assets': [],\n"
    "            'drivers': [],\n"
    "            'overall': 'pass',\n"
    "        },\n"
    "        'license_scan': {\n"
    "            'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.3+9f2c41ab07de',\n"
    "            'evaluated': True,\n"
    "            'reason': None,\n"
    "            'similarity_score': 0.1,\n"
    "            'block_threshold': 0.7,\n"
    "            'blocked': False,\n"
    "            'matches': [],\n"
    "            'notified': False,\n"
    "            'notification_delivery_error': None,\n"
    "            'cache_hit': False,\n"
    "        },\n"
    "        'secret_scan': {\n"
    "            'scope': 'full',\n"
    "            'gate_version': 'secret_scanner@0.0.0',\n"
    "            'flagged': False,\n"
    "            'matches': [],\n"
    "            'allowed': [],\n"
    "            'unused_allowlist_entries': [],\n"
    "            'notified': False,\n"
    "            'notification_delivery_error': None,\n"
    "            'cache_hit': False,\n"
    "        },\n"
    "    }\n"
    "\n"
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


def capability_verifier_src(config_path, check_log, gates_log):
    return (
        "import json\n"
        "\n"
        "GATE_VERSION = 'capability_scenario_verifier@3.0.0'\n"
        "CONFIG = " + repr(str(config_path)) + "\n"
        "CHECK_LOG = " + repr(str(check_log)) + "\n"
        "GATES_LOG = " + repr(str(gates_log)) + "\n"
        "\n"
        "\n"
        "class UnknownCapabilityError(ValueError):\n"
        "    pass\n"
        "\n"
        "\n"
        "class ModelRequiredError(ValueError):\n"
        "    pass\n"
        "\n"
        "\n"
        "def _config():\n"
        "    with open(CONFIG) as f:\n"
        "        return json.load(f)\n"
        "\n"
        "\n"
        "def _log(path, entry):\n"
        "    with open(path, 'a') as f:\n"
        "        f.write(json.dumps(entry) + '\\n')\n"
        "\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    _log(CHECK_LOG, [capability_id, str(repo_root)])\n"
        "    entry = _config()['check'].get(capability_id)\n"
        "    if entry is None:\n"
        "        return {'hit': False, 'capability_scenario_report': None}\n"
        "    return entry\n"
        "\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    _log(GATES_LOG, [capability_id, str(repo_root), model, seed, repr(llm_backend)])\n"
        "    if model is None:\n"
        "        raise ModelRequiredError('model required for ' + capability_id)\n"
        "    entry = _config()['gates'].get(capability_id)\n"
        "    if entry is None:\n"
        "        return {'hit': False, 'capability_scenario_report': {capability_id: {'overall': 'fail', 'scenarios': []}}}\n"
        "    return entry\n"
        "\n"
        "\n"
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    return {}\n"
    )


def secret_scanner_src(scan_log):
    return (
        "SCAN_LOG = " + repr(str(scan_log)) + "\n"
        "\n"
        "\n"
        "def scan(repo_root):\n"
        "    with open(SCAN_LOG, 'a') as f:\n"
        "        f.write(str(repo_root) + '\\n')\n"
        "    return {'flagged': False, 'matches': []}\n"
        "\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    return {'flagged': False, 'matches': []}\n"
        "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@0.0.0'\n"
        "\n"
        "\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    )


IMPACT_ANALYZER_SRC = (
    "class ImpactedComponent:\n"
    "    def __init__(self, component_id, reason, via=None, guarantee_ids=None):\n"
    "        self.component_id = component_id\n"
    "        self.reason = reason\n"
    "        self.via = via\n"
    "        self.guarantee_ids = guarantee_ids\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        return getattr(self, key)\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'component_id': self.component_id, 'reason': self.reason, 'via': self.via}\n"
    "\n"
    "\n"
    "class BlastRadiusReport:\n"
    "    def __init__(self, impacted, precondition_error=None):\n"
    "        self.impacted = impacted\n"
    "        self.precondition_error = precondition_error\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        return getattr(self, key)\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'impacted': [i.to_dict() for i in self.impacted],\n"
    "                'precondition_error': self.precondition_error}\n"
    "\n"
    "\n"
    "def compute_blast_radius(changed_ids, repo_root):\n"
    "    return BlastRadiusReport([ImpactedComponent('comp-foo', 'direct', None)], None)\n"
)


class Env:
    def __init__(self, repo_root, logs):
        self.repo_root = repo_root
        self.logs = logs

    def set_config(self, check, gates):
        self.logs["config"].write_text(json.dumps({"check": check, "gates": gates}))

    def gates_calls(self):
        path = self.logs["gates"]
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@pytest.fixture
def env(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    logs = {
        "config": logs_dir / "config.json",
        "check": logs_dir / "check.log",
        "gates": logs_dir / "gates.log",
        "scan": logs_dir / "scan.log",
    }
    write_corpus(repo_root)

    def put(slug, module_name, src):
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module_name + ".py")).write_text(src)

    put("provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SRC)
    put(
        "capability-scenario-verifier",
        "capability_scenario_verifier",
        capability_verifier_src(logs["config"], logs["check"], logs["gates"]),
    )
    put("secret-scanner", "secret_scanner", secret_scanner_src(logs["scan"]))
    put("impact-analyzer", "impact_analyzer", IMPACT_ANALYZER_SRC)

    e = Env(repo_root, logs)
    e.set_config({}, {})
    return e


FAILING_REPORT = {
    "P-FOO": {
        "overall": "fail",
        "scenarios": [
            {"id": "CS-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "CS-FOO-002", "kind": "llm-judge", "result": "fail"},
            {"id": "CS-FOO-003", "kind": "llm-judge", "result": "skipped"},
            {"id": "CS-FOO-004", "kind": "generated-test", "result": "fail"},
        ],
    }
}

EMPTY_REPORT = {"P-FOO": {"overall": "fail", "scenarios": []}}

NO_SCENARIOS_REASON = (
    "P-FOO: has no capability scenarios; add a CS- scenario to its file under specs/product/"
)


def test_all_passing_is_ready(env):
    passing = {
        "hit": False,
        "capability_scenario_report": {
            "P-FOO": {
                "overall": "pass",
                "scenarios": [{"id": "CS-FOO-001", "kind": "compiled", "result": "pass"}],
            }
        },
    }
    env.set_config({}, {"P-FOO": passing})

    report = provenance_tracker.check_readiness(env.repo_root, None, "m1", 7, None)

    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []
    assert "comp-foo" in field(report, "components")
    assert "P-FOO" in field(report, "capabilities")
    calls = env.gates_calls()
    assert len(calls) == 1
    assert calls[0][0] == "P-FOO"
    assert calls[0][2] == "m1"
    assert calls[0][3] == 7
    assert calls[0][4] == repr(None)


def test_failed_scenarios_named_in_order(env):
    env.set_config({}, {"P-FOO": {"hit": False, "capability_scenario_report": FAILING_REPORT}})

    report = provenance_tracker.check_readiness(env.repo_root, None, "m1", 0, None)

    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "P-FOO: capability scenarios failed: CS-FOO-002, CS-FOO-004"
    ]


def test_empty_scenarios_after_run(env):
    env.set_config({}, {"P-FOO": {"hit": False, "capability_scenario_report": EMPTY_REPORT}})

    report = provenance_tracker.check_readiness(env.repo_root, None, "m1", 0, None)

    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [NO_SCENARIOS_REASON]


def test_provenance_hit_short_circuits(env):
    env.set_config({"P-FOO": {"hit": True, "capability_scenario_report": EMPTY_REPORT}}, {})

    report = provenance_tracker.check_readiness(env.repo_root, None, "m1", 0, None)

    assert list(field(report, "not_ready_reasons")) == [NO_SCENARIOS_REASON]
    assert env.gates_calls() == []


def test_miss_without_model_needs_fresh_run(env):
    env.set_config({}, {})

    report = provenance_tracker.check_readiness(env.repo_root, None, None, 0, None)

    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "P-FOO: needs a fresh run; pass --model"
    ]
    assert "comp-foo" in field(report, "components")
    assert env.gates_calls() == []