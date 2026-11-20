# hotdocs-criterion: sha256:9f54ce2c383f98648ac6bf1313707b6c3c57ec23bda135600b2a725d89df968b
import json
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENTS = {
    "alpha": "P-FOO",
    "beta": "P-BAR",
}


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root, components):
    for slug, cap in components.items():
        upper = slug.upper()
        comp_dir = repo_root / "specs" / "components" / slug
        _write(
            comp_dir / "component.md",
            "---\n"
            "id: comp-" + slug + "\n"
            "title: Component " + slug + "\n"
            "status: draft\n"
            "owners: [pipeline-team]\n"
            "depends_on: []\n"
            "realizes: [" + cap + "]\n"
            "---\n\n"
            "# Component " + slug + "\n\n"
            "A fixture component.\n",
        )
        rid = "R-" + upper + "-001"
        aid = "AC-" + upper + "-001"
        _write(
            comp_dir / "requirements" / (rid + ".md"),
            "# " + rid + "\n\n**" + rid + "** — The component MUST do " + slug + ".\n",
        )
        _write(
            comp_dir / "acceptance" / (aid + ".md"),
            "# " + aid + "\n\nCovers: " + rid + "\nKind: generated-test\n\n"
            "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
        )
        _write(
            comp_dir / "interface" / "library.md",
            "# Library\n\n```\ndo_" + slug + "() -> None\n```\n",
        )
        _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    for cap in sorted(set(components.values())):
        _write(
            repo_root / "specs" / "product" / (cap + ".md"),
            "---\n"
            "id: " + cap + "\n"
            "title: Capability " + cap + "\n"
            "status: draft\n"
            "owners: [pipeline-team]\n"
            "---\n\n"
            "# " + cap + "\n\nThe product MUST provide " + cap + ".\n",
        )


def _write_provenance_checker_fake(repo_root, log_path):
    src = (
        "import json\n"
        "import types\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log(['current_sealed_key', component_id])\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log(['current_provenance_key', component_id])\n"
        "    return types.SimpleNamespace(\n"
        "        spec_bundle_hash='sha256:' + 'a' * 64,\n"
        "        gate_versions={\n"
        "            'compiler': 'criterion-compiler@1.0.0',\n"
        "            'generated_test': 'generated_test@1.0.0',\n"
        "            'verifier': 'verifier-orchestrator@2.0.0',\n"
        "            'license_scanner': 'license_scanner@4.0.3+9f2c41ab07de',\n"
        "            'secret_scanner': 'secret_scanner@0.0.0',\n"
        "            'generator': 'generator@3.0.0+v11',\n"
        "        },\n"
        "        assets=[{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                 'adapter_sha256': 'sha256:' + 'b' * 64,\n"
        "                 'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}],\n"
        "    )\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log(['check_provenance', component_id])\n"
        "    return {\n"
        "        'hit': True,\n"
        "        'reason': None,\n"
        "        'verification_report': {\n"
        "            'component_id': component_id,\n"
        "            'criteria': [],\n"
        "            'requirement_results': {},\n"
        "            'interface_drift': False,\n"
        "            'mutation_score': 0.9,\n"
        "            'mutation_error': None,\n"
        "            'assets': [],\n"
        "            'overall': 'pass',\n"
        "        },\n"
        "        'license_scan': {\n"
        "            'component_id': component_id,\n"
        "            'gate_version': 'license_scanner@4.0.3+9f2c41ab07de',\n"
        "            'evaluated': True, 'reason': None,\n"
        "            'similarity_score': 0.1, 'block_threshold': 0.7,\n"
        "            'blocked': False, 'matches': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False,\n"
        "        },\n"
        "        'secret_scan': {\n"
        "            'scope': 'full', 'gate_version': 'secret_scanner@0.0.0',\n"
        "            'flagged': False, 'matches': [], 'allowed': [],\n"
        "            'unused_allowlist_entries': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False,\n"
        "        },\n"
        "    }\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log(['check_sealed_provenance', component_id])\n"
        "    return {\n"
        "        'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "        'verification_report': None, 'license_scan': None,\n"
        "        'secret_scan': None, 'owners': None, 'source_hash': None,\n"
        "        'written_at': None,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", src)


def _write_capability_verifier_fake(repo_root, check_log, gates_log, outcomes):
    src = (
        "import json\n"
        "\n"
        "GATE_VERSION = 'capability_scenario_verifier@2.2.0'\n"
        "CHECK_LOG = " + repr(str(check_log)) + "\n"
        "GATES_LOG = " + repr(str(gates_log)) + "\n"
        "OUTCOMES = " + repr(outcomes) + "\n"
        "\n"
        "class UnknownCapabilityError(ValueError):\n"
        "    pass\n"
        "\n"
        "class ModelRequiredError(ValueError):\n"
        "    pass\n"
        "\n"
        "def _append(path, entry):\n"
        "    with open(path, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
        "\n"
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    raise AssertionError('run_capability_scenarios must never be called')\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    _append(CHECK_LOG, [capability_id, str(repo_root)])\n"
        "    return {'hit': False, 'capability_scenario_report': None}\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    _append(GATES_LOG, [capability_id, str(repo_root), model, seed, repr(llm_backend)])\n"
        "    overall = OUTCOMES.get(capability_id, 'pass')\n"
        "    return {\n"
        "        'hit': False,\n"
        "        'capability_scenario_report': {\n"
        "            capability_id: {\n"
        "                'overall': overall,\n"
        "                'scenarios': [\n"
        "                    {'id': 'CS-' + capability_id[2:] + '-001',\n"
        "                     'kind': 'generated-test', 'result': overall},\n"
        "                ],\n"
        "            },\n"
        "        },\n"
        "    }\n"
    )
    _write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        src,
    )


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _setup(tmp_path, components, outcomes):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    prov_log = logs / "prov.log"
    check_log = logs / "check.log"
    gates_log = logs / "gates.log"
    _build_corpus(repo_root, components)
    _write_provenance_checker_fake(repo_root, prov_log)
    _write_capability_verifier_fake(repo_root, check_log, gates_log, outcomes)
    return repo_root, prov_log, check_log, gates_log


def test_all_components_and_capabilities_pass_is_ready(tmp_path):
    repo_root, prov_log, check_log, gates_log = _setup(
        tmp_path, COMPONENTS, {"P-FOO": "pass", "P-BAR": "pass"}
    )
    report = provenance_tracker.check_readiness(
        repo_root, None, model="fake-model", seed=7, llm_backend=None
    )
    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []

    components = field(report, "components")
    assert "comp-alpha" in components
    assert "comp-beta" in components

    checked = sorted(entry[0] for entry in _read_log(check_log))
    assert checked == ["P-BAR", "P-FOO"]

    gates = _read_log(gates_log)
    assert sorted(entry[0] for entry in gates) == ["P-BAR", "P-FOO"]
    for entry in gates:
        assert Path(entry[1]).resolve() == repo_root.resolve()
        assert entry[2] == "fake-model"
        assert entry[3] == 7
        assert entry[4] == repr(None)


def test_one_failing_capability_makes_not_ready(tmp_path):
    repo_root, prov_log, check_log, gates_log = _setup(
        tmp_path, COMPONENTS, {"P-FOO": "pass", "P-BAR": "fail"}
    )
    report = provenance_tracker.check_readiness(
        repo_root, None, model="fake-model", seed=0, llm_backend=None
    )
    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    assert any("P-BAR" in reason for reason in reasons)
    assert not any("comp-alpha" in reason or "comp-beta" in reason for reason in reasons)

    components = field(report, "components")
    assert "comp-alpha" in components
    assert "comp-beta" in components
    for cid in ("comp-alpha", "comp-beta"):
        assert field(components[cid], "hit") is True

    gates = _read_log(gates_log)
    assert sorted(entry[0] for entry in gates) == ["P-BAR", "P-FOO"]


def test_capability_miss_without_model_reports_needs_fresh_run(tmp_path):
    repo_root, prov_log, check_log, gates_log = _setup(
        tmp_path, {"alpha": "P-FOO", "beta": "P-FOO"}, {"P-FOO": "pass"}
    )
    report = provenance_tracker.check_readiness(repo_root, None, model=None)
    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "P-FOO: needs a fresh run; pass --model"
    ]

    components = field(report, "components")
    assert "comp-alpha" in components
    assert "comp-beta" in components

    checked = [entry[0] for entry in _read_log(check_log)]
    assert "P-FOO" in checked
    assert _read_log(gates_log) == []