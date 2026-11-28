# hotdocs-criterion: sha256:2bf8adb6de6e72e10f1b1cc104e8a3a729b8cda167ef262fff5fb7145540870e
"""AC-TRACK-011: check_readiness resolves impact-analyzer relative to each
call's own repo_root, never reusing another repo_root's module."""

from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _impact_analyzer_source(log_path, direct_id, transitive_ids):
    return (
        "import dataclasses\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "DIRECT_ID = " + repr(direct_id) + "\n"
        "TRANSITIVE_IDS = " + repr(list(transitive_ids)) + "\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class ImpactedComponent:\n"
        "    component_id: str\n"
        "    reason: str\n"
        "    via: object = None\n"
        "    guarantee_ids: object = None\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def to_dict(self):\n"
        "        d = {'component_id': self.component_id, 'reason': self.reason, 'via': self.via}\n"
        "        if self.reason == 'transitive-guarantee':\n"
        "            d['guarantee_ids'] = list(self.guarantee_ids or [])\n"
        "        return d\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class BlastRadiusReport:\n"
        "    impacted: list\n"
        "    precondition_error: object = None\n"
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
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(str(repo_root) + '\\n')\n"
        "    impacted = [ImpactedComponent(DIRECT_ID, 'direct', None, None)]\n"
        "    for cid in sorted(TRANSITIVE_IDS):\n"
        "        impacted.append(ImpactedComponent(cid, 'transitive-interface', DIRECT_ID, None))\n"
        "    return BlastRadiusReport(impacted, None)\n"
    )


def _provenance_checker_source():
    gate_versions = {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
        "secret_scanner": "secret_scanner@0.0.0",
        "generator": "generator@3.0.0+v11",
    }
    source_hash = "sha256:" + "0" * 64
    return (
        "GATE_VERSIONS = " + repr(gate_versions) + "\n"
        "SOURCE_HASH = " + repr(source_hash) + "\n"
        "\n"
        "\n"
        "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, spec_bundle_parts, gate_versions, assets, drivers):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.spec_bundle_parts = spec_bundle_parts\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "        self.drivers = drivers\n"
        "\n"
        "\n"
        "class SealedKey:\n"
        "    def __init__(self, owners, source_path, source_hash, verifier_version):\n"
        "        self.owners = owners\n"
        "        self.source_path = source_path\n"
        "        self.source_hash = source_hash\n"
        "        self.verifier_version = verifier_version\n"
        "\n"
        "\n"
        "def _slug(component_id):\n"
        "    return component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
        "\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    return ProvenanceKey(\n"
        "        'sha256:' + 'a' * 64,\n"
        "        {'spec': 'sha256:' + 'b' * 64, 'dependency_code': 'sha256:' + 'c' * 64},\n"
        "        dict(GATE_VERSIONS),\n"
        "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "          'adapter_sha256': 'sha256:' + 'd' * 64, 'versions': {'python': '3.12.4'},\n"
        "          'lockfile_sha256': None}],\n"
        "        [],\n"
        "    )\n"
        "\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    return {\n"
        "        'hit': True,\n"
        "        'reason': None,\n"
        "        'verification_report': {'component_id': component_id, 'criteria': [],\n"
        "                                'requirement_results': {}, 'interface_drift': False,\n"
        "                                'mutation_score': None, 'mutation_error': None,\n"
        "                                'assets': [], 'drivers': [], 'overall': 'pass'},\n"
        "        'license_scan': None,\n"
        "        'secret_scan': None,\n"
        "    }\n"
        "\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    return SealedKey(['pipeline-team'], 'legacy/' + _slug(component_id) + '/',\n"
        "                     SOURCE_HASH, 'verifier-orchestrator@2.0.0')\n"
        "\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    return {\n"
        "        'hit': True,\n"
        "        'sealed': True,\n"
        "        'reason': None,\n"
        "        'verification_report': {'overall': 'pass'},\n"
        "        'license_scan': None,\n"
        "        'secret_scan': None,\n"
        "        'owners': ['pipeline-team'],\n"
        "        'source_hash': SOURCE_HASH,\n"
        "        'written_at': '2026-11-02T00:00:00Z',\n"
        "    }\n"
    )


def _capability_verifier_source():
    return (
        "GATE_VERSION = 'capability_scenario_verifier@3.0.0'\n"
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
        "def _hit(capability_id):\n"
        "    return {'hit': True,\n"
        "            'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
        "\n"
        "\n"
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    return {}\n"
        "\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    return _hit(capability_id)\n"
        "\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    return _hit(capability_id)\n"
    )


def _secret_scanner_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def scan(repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
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


def _component_md(component_id):
    slug = component_id[len("comp-"):]
    return (
        "---\n"
        "id: " + component_id + "\n"
        "title: Fixture " + slug + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# Fixture " + slug + "\n"
    )


def _build_repo(repo_root, logs_dir, label, direct_id, transitive_ids):
    repo_root.mkdir(parents=True, exist_ok=True)
    impact_log = logs_dir / (label + "-impact.log")
    scan_log = logs_dir / (label + "-scan.log")
    gen = repo_root / "gen"
    _write(gen / "impact-analyzer" / "impact_analyzer.py",
           _impact_analyzer_source(impact_log, direct_id, transitive_ids))
    _write(gen / "provenance-checker" / "provenance_checker.py", _provenance_checker_source())
    _write(gen / "capability-scenario-verifier" / "capability_scenario_verifier.py",
           _capability_verifier_source())
    _write(gen / "secret-scanner" / "secret_scanner.py", _secret_scanner_source(scan_log))
    for cid in [direct_id] + list(transitive_ids):
        slug = cid[len("comp-"):]
        _write(repo_root / "specs" / "components" / slug / "component.md", _component_md(cid))
    return impact_log


def _log_roots(log_path):
    if not log_path.exists():
        return []
    return [Path(line).resolve() for line in log_path.read_text(encoding="utf-8").splitlines() if line]


@pytest.mark.parametrize("order", ["alpha-first", "beta-first"])
def test_each_call_uses_its_own_repo_roots_impact_analyzer(tmp_path, order):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    alpha_root = tmp_path / "repo-alpha"
    beta_root = tmp_path / "repo-beta"
    alpha_ids = ["comp-alphazed-one", "comp-alphazed-two"]
    beta_ids = ["comp-betaquux-one", "comp-betaquux-two", "comp-betaquux-three"]

    alpha_log = _build_repo(alpha_root, logs_dir, "alpha", alpha_ids[0], alpha_ids[1:])
    beta_log = _build_repo(beta_root, logs_dir, "beta", beta_ids[0], beta_ids[1:])

    cases = {
        "alpha": (alpha_root, alpha_ids, alpha_log),
        "beta": (beta_root, beta_ids, beta_log),
    }
    sequence = ["alpha", "beta"] if order == "alpha-first" else ["beta", "alpha"]

    results = {}
    for name in sequence:
        root, ids, _ = cases[name]
        results[name] = provenance_tracker.check_readiness(root, changed_ids=[ids[0]])

    for name in sequence:
        root, ids, log = cases[name]
        other = "beta" if name == "alpha" else "alpha"
        other_root, other_ids, other_log = cases[other]

        report = results[name]
        assert field(report, "scope") == "blast-radius"
        components = field(report, "components")
        assert set(components.keys()) == set(ids), (
            name + " call's components should come from its own fake impact-analyzer"
        )
        assert not (set(components.keys()) & set(other_ids))

        own_calls = _log_roots(log)
        assert own_calls == [root.resolve()], (
            name + " repo_root's fake impact-analyzer should be called exactly once, for itself"
        )
        assert other_root.resolve() not in own_calls