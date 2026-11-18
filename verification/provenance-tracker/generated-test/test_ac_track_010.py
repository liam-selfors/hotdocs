# hotdocs-criterion: sha256:ba31793e3eb629453aeb572bc685912e82fc02ecaf09465c98014a15827a0267
import importlib.util
import sys
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


CHECKER_BODY = (
    "\n"
    "def _log(line):\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(line + '\\n')\n"
    "\n"
    "\n"
    "class _Key:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('sealed_key ' + component_id)\n"
    "    return None\n"
    "\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('provenance_key ' + component_id)\n"
    "    return _Key('sha256:' + '0' * 64, {\n"
    "        'compiler': 'criterion-compiler@1.0.0',\n"
    "        'generated_test': 'generated_test@1.0.0',\n"
    "        'verifier': 'verifier-orchestrator@2.0.0',\n"
    "        'license_scanner': 'license_scanner@4.0.3',\n"
    "        'secret_scanner': 'secret_scanner@0.0.0',\n"
    "    })\n"
    "\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance ' + component_id)\n"
    "    return {\n"
    "        'hit': True,\n"
    "        'verification_report': {\n"
    "            'component_id': component_id,\n"
    "            'criteria': [{'id': 'AC-X-001', 'covers': 'R-X-001', 'kind': 'compiled', 'result': 'pass'}],\n"
    "            'requirement_results': {'R-X-001': 'pass'},\n"
    "            'interface_drift': False,\n"
    "            'mutation_score': 0.9,\n"
    "            'mutation_error': None,\n"
    "            'overall': 'pass',\n"
    "        },\n"
    "        'license_scan': {\n"
    "            'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.3',\n"
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
    "    _log('check_sealed ' + component_id)\n"
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


VERIFIER_BODY = (
    "\n"
    "GATE_VERSION = 'capability_scenario_verifier@2.0.0'\n"
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
    "def _log(line):\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(line + '\\n')\n"
    "\n"
    "\n"
    "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
    "    _log('run_scenarios')\n"
    "    return {}\n"
    "\n"
    "\n"
    "def check_capability_provenance(capability_id, repo_root):\n"
    "    _log('check ' + capability_id)\n"
    "    return {'hit': False, 'capability_scenario_report': None}\n"
    "\n"
    "\n"
    "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
    "    _log('run ' + capability_id + ' ' + repr(model) + ' ' + repr(seed))\n"
    "    overall = OUTCOMES.get(capability_id, 'pass')\n"
    "    return {\n"
    "        'hit': False,\n"
    "        'capability_scenario_report': {\n"
    "            capability_id: {\n"
    "                'overall': overall,\n"
    "                'scenarios': [\n"
    "                    {'id': 'CS-' + capability_id[2:] + '-001', 'kind': 'compiled', 'result': overall}\n"
    "                ],\n"
    "            }\n"
    "        },\n"
    "    }\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _component(repo_root, slug, realizes):
    upper = slug.upper()
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [" + ", ".join(realizes) + "]\n"
        "sealed: false\n"
        "---\n\n"
        "# " + slug.capitalize() + "\n\n"
        "A fixture component.\n",
    )
    _write(
        base / "requirements" / ("R-" + upper + "-001.md"),
        "# R-" + upper + "-001\n\nThe component MUST do its one thing.\n",
    )
    _write(
        base / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\n"
        "Covers: R-" + upper + "-001\n"
        "Kind: compiled\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )
    _write(base / "interface" / "library.md", "# Library\n\nNothing.\n")
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "gen" / slug / (slug.replace("-", "_") + ".py"), "X = 1\n")


def _capability(repo_root, cap_id):
    name = cap_id[2:].lower()
    _write(
        repo_root / "specs" / "product" / (name + ".md"),
        "---\n"
        "id: " + cap_id + "\n"
        "title: " + name.capitalize() + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n\n"
        "# " + cap_id + "\n\n"
        "### CS-" + cap_id[2:] + "-001\n\n"
        "Covers: " + cap_id + "\n"
        "Kind: compiled\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )


def _build(tmp_path, components, capabilities, outcomes):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Thing** — a thing.\n")
    for slug, realizes in components.items():
        _component(repo_root, slug, realizes)
    for cap in capabilities:
        _capability(repo_root, cap)
    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        "LOG = " + repr(str(log)) + "\n" + CHECKER_BODY,
    )
    _write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        "LOG = " + repr(str(log)) + "\n"
        + "OUTCOMES = " + repr(dict(outcomes)) + "\n"
        + VERIFIER_BODY,
    )
    return repo_root, log


def _lines(log):
    if not log.exists():
        return []
    return [line for line in log.read_text().splitlines() if line]


def test_all_components_and_capabilities_pass_is_ready(tmp_path):
    repo_root, log = _build(
        tmp_path,
        {"alpha": ["P-FOO"], "beta": ["P-BAR"]},
        ["P-FOO", "P-BAR"],
        {"P-FOO": "pass", "P-BAR": "pass"},
    )
    report = provenance_tracker.check_readiness(repo_root, model="test-model", seed=0)

    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []
    components = field(report, "components")
    assert "comp-alpha" in components
    assert "comp-beta" in components

    lines = _lines(log)
    run_lines = [line for line in lines if line.startswith("run ")]
    assert any(line.startswith("run P-FOO ") for line in run_lines)
    assert any(line.startswith("run P-BAR ") for line in run_lines)
    for cap in ("P-FOO", "P-BAR"):
        check_idx = lines.index("check " + cap)
        run_idx = next(i for i, line in enumerate(lines) if line.startswith("run " + cap + " "))
        assert check_idx < run_idx


def test_one_failing_capability_makes_not_ready(tmp_path):
    repo_root, log = _build(
        tmp_path,
        {"alpha": ["P-FOO"], "beta": ["P-BAR"]},
        ["P-FOO", "P-BAR"],
        {"P-FOO": "pass", "P-BAR": "fail"},
    )
    report = provenance_tracker.check_readiness(repo_root, model="test-model", seed=0)

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    assert any("P-BAR" in r for r in reasons)
    assert not any("P-FOO" in r for r in reasons)
    assert not any("comp-alpha" in r or "comp-beta" in r for r in reasons)
    components = field(report, "components")
    assert "comp-alpha" in components
    assert "comp-beta" in components


def test_capability_miss_without_model_is_not_ready_and_never_runs(tmp_path):
    repo_root, log = _build(
        tmp_path,
        {"alpha": ["P-FOO"], "beta": ["P-FOO"]},
        ["P-FOO"],
        {"P-FOO": "pass"},
    )
    report = provenance_tracker.check_readiness(repo_root, model=None)

    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "P-FOO: needs a fresh run; pass --model"
    ]
    components = field(report, "components")
    assert "comp-alpha" in components
    assert "comp-beta" in components

    lines = _lines(log)
    assert "check P-FOO" in lines
    assert not any(line.startswith("run ") for line in lines)