import json
import sys
from pathlib import Path

import pytest

import provenance_tracker


CHANGED_ID = "VAR-SHARED-TOGGLE"

REPO_SPECS = {
    "alpha": {
        "components": ["comp-zeta-alpha-ruby", "comp-zeta-alpha-onyx"],
        "owners": ["team-alpha"],
        "hash_digit": "a",
    },
    "beta": {
        "components": ["comp-zeta-beta-sapphire", "comp-zeta-beta-jade", "comp-zeta-beta-opal"],
        "owners": ["team-beta"],
        "hash_digit": "b",
    },
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _norm(p):
    return str(Path(p).resolve())


def _write_component_md(repo_root, component_id, owners):
    slug = component_id[len("comp-"):]
    comp_dir = repo_root / "specs" / "components" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        f"id: {component_id}\n"
        f"title: {slug}\n"
        "status: draft\n"
        f"owners: [{', '.join(owners)}]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "depends_on: []\n"
        "---\n"
        f"# {component_id}\n\nA synthetic sealed fixture component.\n"
    )
    legacy = repo_root / "legacy" / slug
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "placeholder.py").write_text("VALUE = 1\n")


def _write_var(repo_root):
    vars_dir = repo_root / "specs" / "vars"
    vars_dir.mkdir(parents=True, exist_ok=True)
    (vars_dir / f"{CHANGED_ID}.md").write_text(
        "---\n"
        f"id: {CHANGED_ID}\n"
        "title: Shared toggle\n"
        "status: draft\n"
        "owners: [team-shared]\n"
        "---\n"
        f"# {CHANGED_ID}\n\nA synthetic var declaration.\n"
    )


def _write_fake_impact_analyzer(repo_root, components, log_path):
    d = repo_root / "gen" / "impact-analyzer"
    d.mkdir(parents=True, exist_ok=True)
    (d / "impact_analyzer.py").write_text(
        "import json\n"
        "\n"
        f"_LOG = {str(log_path)!r}\n"
        f"_COMPONENTS = {components!r}\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'changed_ids': list(changed_ids), 'repo_root': str(repo_root)}) + '\\n')\n"
        "    impacted = []\n"
        "    for cid in _COMPONENTS:\n"
        "        impacted.append({'component_id': cid, 'reason': 'transitive-var', 'via': "
        f"{CHANGED_ID!r}" "})\n"
        "    return {'impacted': impacted, 'precondition_error': None}\n"
    )


def _write_fake_provenance_checker(repo_root, owners, hash_digit, log_path):
    d = repo_root / "gen" / "provenance-checker"
    d.mkdir(parents=True, exist_ok=True)
    source_hash = "sha256:" + hash_digit * 64
    (d / "provenance_checker.py").write_text(
        "import json\n"
        "from types import SimpleNamespace\n"
        "\n"
        f"_LOG = {str(log_path)!r}\n"
        f"_OWNERS = {owners!r}\n"
        f"_SOURCE_HASH = {source_hash!r}\n"
        "\n"
        "def _log(fn, component_id, repo_root):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'fn': fn, 'component_id': component_id, 'repo_root': str(repo_root)}) + '\\n')\n"
        "\n"
        "def _slug(component_id):\n"
        "    return component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id, repo_root)\n"
        "    return SimpleNamespace(\n"
        "        owners=list(_OWNERS),\n"
        "        source_path='legacy/' + _slug(component_id) + '/',\n"
        "        source_hash=_SOURCE_HASH,\n"
        "        verifier_version='verifier-orchestrator@2.0.0',\n"
        "    )\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id, repo_root)\n"
        "    return {\n"
        "        'hit': True,\n"
        "        'sealed': True,\n"
        "        'reason': None,\n"
        "        'verification_report': {'overall': 'pass'},\n"
        "        'license_scan': None,\n"
        "        'secret_scan': None,\n"
        "        'owners': list(_OWNERS),\n"
        "        'source_hash': _SOURCE_HASH,\n"
        "        'written_at': '2026-11-02T00:00:00Z',\n"
        "    }\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id, repo_root)\n"
        "    return SimpleNamespace(\n"
        "        spec_bundle_hash=_SOURCE_HASH,\n"
        "        gate_versions={\n"
        "            'compiler': 'criterion-compiler@1.0.0',\n"
        "            'generated_test': 'generated_test@1.0.0',\n"
        "            'verifier': 'verifier-orchestrator@2.0.0',\n"
        "            'license_scanner': 'license_scanner@4.0.3+9f2c41ab07de',\n"
        "            'secret_scanner': 'secret_scanner@0.0.0',\n"
        "        },\n"
        "    )\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id, repo_root)\n"
        "    return {\n"
        "        'hit': True,\n"
        "        'verification_report': {\n"
        "            'component_id': component_id,\n"
        "            'criteria': [],\n"
        "            'requirement_results': {},\n"
        "            'interface_drift': False,\n"
        "            'mutation_score': None,\n"
        "            'overall': 'pass',\n"
        "        },\n"
        "        'license_scan': {\n"
        "            'component_id': component_id,\n"
        "            'gate_version': 'license_scanner@4.0.3+9f2c41ab07de',\n"
        "            'evaluated': True,\n"
        "            'reason': None,\n"
        "            'similarity_score': 0.0,\n"
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
    )


def _write_fake_capability_verifier(repo_root, log_path):
    d = repo_root / "gen" / "capability-scenario-verifier"
    d.mkdir(parents=True, exist_ok=True)
    (d / "capability_scenario_verifier.py").write_text(
        "import json\n"
        "\n"
        f"_LOG = {str(log_path)!r}\n"
        "GATE_VERSION = 'capability_scenario_verifier@2.0.0'\n"
        "\n"
        "class UnknownCapabilityError(ValueError):\n"
        "    pass\n"
        "\n"
        "class ModelRequiredError(ValueError):\n"
        "    pass\n"
        "\n"
        "def _log(fn, capability_id, repo_root):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'fn': fn, 'capability_id': capability_id, 'repo_root': str(repo_root)}) + '\\n')\n"
        "\n"
        "def _hit(capability_id):\n"
        "    return {'hit': True, 'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
        "\n"
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    _log('run_capability_scenarios', None, repo_root)\n"
        "    return {}\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    _log('check_capability_provenance', capability_id, repo_root)\n"
        "    return _hit(capability_id)\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    _log('run_capability_gates', capability_id, repo_root)\n"
        "    return _hit(capability_id)\n"
    )


def _build_repo(base, name):
    spec = REPO_SPECS[name]
    repo_root = base / f"repo_{name}"
    repo_root.mkdir(parents=True)
    logs = base / f"logs_{name}"
    logs.mkdir(parents=True)
    impact_log = logs / "impact.jsonl"
    prov_log = logs / "provenance.jsonl"
    cap_log = logs / "capability.jsonl"
    _write_var(repo_root)
    for cid in spec["components"]:
        _write_component_md(repo_root, cid, spec["owners"])
    _write_fake_impact_analyzer(repo_root, spec["components"], impact_log)
    _write_fake_provenance_checker(repo_root, spec["owners"], spec["hash_digit"], prov_log)
    _write_fake_capability_verifier(repo_root, cap_log)
    return {
        "repo_root": repo_root,
        "impact_log": impact_log,
        "prov_log": prov_log,
        "cap_log": cap_log,
        "components": spec["components"],
    }


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@pytest.mark.parametrize("order", [("alpha", "beta"), ("beta", "alpha")])
def test_check_readiness_resolves_dependencies_per_repo_root(tmp_path, order):
    repos = {name: _build_repo(tmp_path / "-".join(order), name) for name in order}

    results = {}
    for name in order:
        repo = repos[name]
        results[name] = provenance_tracker.check_readiness(
            repo["repo_root"], changed_ids=[CHANGED_ID]
        )

    for name in order:
        repo = repos[name]
        other = repos["beta" if name == "alpha" else "alpha"]
        result = results[name]

        # The call's result reflects its own repo_root's fake impact-analyzer.
        components = field(result, "components")
        assert set(components.keys()) == set(repo["components"]), (
            f"{name}: expected components {sorted(repo['components'])}, "
            f"got {sorted(components.keys())}"
        )
        assert not (set(components.keys()) & set(other["components"]))
        assert field(result, "scope") == "blast-radius"

        # Its own fake impact-analyzer was invoked exactly once, for its own repo_root.
        impact_calls = _read_log(repo["impact_log"])
        assert len(impact_calls) == 1, f"{name}: impact-analyzer fake calls = {impact_calls}"
        assert _norm(impact_calls[0]["repo_root"]) == _norm(repo["repo_root"])
        assert impact_calls[0]["changed_ids"] == [CHANGED_ID]

        # Its own fake provenance-checker was used, only for its own components/repo_root.
        prov_calls = _read_log(repo["prov_log"])
        assert prov_calls, f"{name}: own provenance-checker fake was never invoked"
        for call in prov_calls:
            assert _norm(call["repo_root"]) == _norm(repo["repo_root"])
            assert call["component_id"] in repo["components"]
        assert {c["component_id"] for c in prov_calls} == set(repo["components"])

        # Any capability verifier calls this repo's fake saw were for its own repo_root only.
        for call in _read_log(repo["cap_log"]):
            assert _norm(call["repo_root"]) == _norm(repo["repo_root"])