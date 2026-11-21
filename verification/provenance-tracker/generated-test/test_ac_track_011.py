# hotdocs-criterion: sha256:defbac3b4d8756e6a55fa0db0c699bc05c4ffb5d2b6c239629e1463dce4207e7
import importlib.util
import sys
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _impact_source(log_path, tag, impacted):
    lines = [
        "import dataclasses",
        "",
        "LOG = " + repr(str(log_path)),
        "TAG = " + repr(tag),
        "IMPACTED = " + repr(impacted),
        "",
        "",
        "@dataclasses.dataclass",
        "class ImpactedComponent:",
        "    component_id: str",
        "    reason: str",
        "    via: object = None",
        "    guarantee_ids: object = None",
        "",
        "    def __getitem__(self, key):",
        "        if key == 'guarantee_ids' and self.reason != 'transitive-guarantee':",
        "            raise KeyError(key)",
        "        return getattr(self, key)",
        "",
        "    def get(self, key, default=None):",
        "        try:",
        "            return self[key]",
        "        except KeyError:",
        "            return default",
        "",
        "    def to_dict(self):",
        "        d = {'component_id': self.component_id, 'reason': self.reason, 'via': self.via}",
        "        if self.reason == 'transitive-guarantee':",
        "            d['guarantee_ids'] = list(self.guarantee_ids or [])",
        "        return d",
        "",
        "",
        "@dataclasses.dataclass",
        "class BlastRadiusReport:",
        "    impacted: list",
        "    precondition_error: object = None",
        "",
        "    def __getitem__(self, key):",
        "        if key == 'impacted':",
        "            return self.impacted",
        "        if key == 'precondition_error':",
        "            return self.precondition_error",
        "        raise KeyError(key)",
        "",
        "    def get(self, key, default=None):",
        "        try:",
        "            return self[key]",
        "        except KeyError:",
        "            return default",
        "",
        "    def to_dict(self):",
        "        return {'impacted': [i.to_dict() for i in self.impacted],",
        "                'precondition_error': self.precondition_error}",
        "",
        "",
        "def compute_blast_radius(changed_ids, repo_root):",
        "    with open(LOG, 'a') as f:",
        "        f.write(TAG + '\\t' + ','.join(list(changed_ids)) + '\\n')",
        "    return BlastRadiusReport(",
        "        impacted=[ImpactedComponent(component_id=c, reason=r, via=v) for (c, r, v) in IMPACTED],",
        "        precondition_error=None,",
        "    )",
        "",
    ]
    return "\n".join(lines)


def _checker_source(log_path, tag):
    lines = [
        "LOG = " + repr(str(log_path)),
        "TAG = " + repr(tag),
        "",
        "",
        "def _log(name, component_id):",
        "    with open(LOG, 'a') as f:",
        "        f.write(TAG + '\\t' + name + '\\t' + str(component_id) + '\\n')",
        "",
        "",
        "class ProvenanceKey:",
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):",
        "        self.spec_bundle_hash = spec_bundle_hash",
        "        self.gate_versions = gate_versions",
        "        self.assets = assets",
        "",
        "",
        "def current_sealed_key(component_id, repo_root):",
        "    _log('current_sealed_key', component_id)",
        "    return None",
        "",
        "",
        "def current_provenance_key(component_id, repo_root):",
        "    _log('current_provenance_key', component_id)",
        "    return ProvenanceKey(",
        "        spec_bundle_hash='sha256:' + 'a' * 64,",
        "        gate_versions={",
        "            'compiler': 'criterion-compiler@1.0.0',",
        "            'generated_test': 'generated_test@1.0.0',",
        "            'verifier': 'verifier-orchestrator@2.0.0',",
        "            'license_scanner': 'license_scanner@4.0.3+9f2c41ab07de',",
        "            'secret_scanner': 'secret_scanner@0.0.0',",
        "            'generator': 'generator@3.0.0+v11',",
        "        },",
        "        assets=[{'kind': 'python', 'path': '.', 'definition_sha256': None,",
        "                 'adapter_sha256': 'sha256:' + 'b' * 64,",
        "                 'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}],",
        "    )",
        "",
        "",
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):",
        "    _log('check_provenance', component_id)",
        "    return {",
        "        'hit': True,",
        "        'reason': None,",
        "        'verification_report': {",
        "            'component_id': component_id,",
        "            'criteria': [],",
        "            'requirement_results': {},",
        "            'interface_drift': False,",
        "            'mutation_score': 1.0,",
        "            'mutation_error': None,",
        "            'assets': [],",
        "            'overall': 'pass',",
        "        },",
        "        'license_scan': {",
        "            'component_id': component_id,",
        "            'gate_version': 'license_scanner@4.0.3+9f2c41ab07de',",
        "            'evaluated': True, 'reason': None, 'similarity_score': 0.0,",
        "            'block_threshold': 0.7, 'blocked': False, 'matches': [],",
        "            'notified': False, 'notification_delivery_error': None, 'cache_hit': False,",
        "        },",
        "        'secret_scan': {",
        "            'scope': 'full', 'gate_version': 'secret_scanner@0.0.0',",
        "            'flagged': False, 'matches': [], 'allowed': [],",
        "            'unused_allowlist_entries': [], 'notified': False,",
        "            'notification_delivery_error': None, 'cache_hit': False,",
        "        },",
        "    }",
        "",
        "",
        "def check_sealed_provenance(component_id, repo_root):",
        "    _log('check_sealed_provenance', component_id)",
        "    return {",
        "        'hit': False, 'sealed': False, 'reason': 'not_sealed',",
        "        'verification_report': None, 'license_scan': None, 'secret_scan': None,",
        "        'owners': None, 'source_hash': None, 'written_at': None,",
        "    }",
        "",
    ]
    return "\n".join(lines)


def _capability_source(log_path, tag):
    lines = [
        "LOG = " + repr(str(log_path)),
        "TAG = " + repr(tag),
        "GATE_VERSION = 'capability_scenario_verifier@2.2.0'",
        "",
        "",
        "class UnknownCapabilityError(ValueError):",
        "    pass",
        "",
        "",
        "class ModelRequiredError(ValueError):",
        "    pass",
        "",
        "",
        "def _log(name, capability_id):",
        "    with open(LOG, 'a') as f:",
        "        f.write(TAG + '\\t' + name + '\\t' + str(capability_id) + '\\n')",
        "",
        "",
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):",
        "    _log('run_capability_scenarios', ','.join(list(blast_radius)))",
        "    return {}",
        "",
        "",
        "def check_capability_provenance(capability_id, repo_root):",
        "    _log('check_capability_provenance', capability_id)",
        "    return {'hit': True, 'capability_scenario_report': {",
        "        capability_id: {'overall': 'pass', 'scenarios': []}}}",
        "",
        "",
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):",
        "    _log('run_capability_gates', capability_id)",
        "    return {'hit': True, 'capability_scenario_report': {",
        "        capability_id: {'overall': 'pass', 'scenarios': []}}}",
        "",
    ]
    return "\n".join(lines)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_root(root, log_dir, tag, impacted):
    root.mkdir(parents=True, exist_ok=True)
    (root / "specs").mkdir(parents=True, exist_ok=True)
    _write(
        root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        _impact_source(log_dir / ("impact_" + tag + ".log"), tag, impacted),
    )
    _write(
        root / "gen" / "provenance-checker" / "provenance_checker.py",
        _checker_source(log_dir / ("checker_" + tag + ".log"), tag),
    )
    _write(
        root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        _capability_source(log_dir / ("capability_" + tag + ".log"), tag),
    )


def _read_lines(path):
    if not path.is_file():
        return []
    return [line for line in path.read_text().splitlines() if line.strip()]


@pytest.mark.parametrize("order", ["alpha-first", "beta-first"])
def test_check_readiness_resolves_impact_analyzer_per_repo_root(tmp_path, order):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    alpha_root = tmp_path / "root-alpha"
    beta_root = tmp_path / "root-beta"

    alpha_impacted = [
        ("comp-zebra-alpha-one", "direct", None),
        ("comp-zebra-alpha-two", "transitive-interface", "comp-zebra-alpha-one"),
    ]
    beta_impacted = [
        ("comp-quokka-beta-one", "direct", None),
        ("comp-quokka-beta-two", "transitive-interface", "comp-quokka-beta-one"),
        ("comp-quokka-beta-three", "transitive-interface", "comp-quokka-beta-one"),
    ]

    _build_root(alpha_root, log_dir, "alpha", alpha_impacted)
    _build_root(beta_root, log_dir, "beta", beta_impacted)

    calls = [
        ("alpha", alpha_root, ["comp-zebra-alpha-one"]),
        ("beta", beta_root, ["comp-quokka-beta-one"]),
    ]
    if order == "beta-first":
        calls.reverse()

    results = {}
    for tag, root, changed in calls:
        results[tag] = provenance_tracker.check_readiness(root, changed_ids=changed)

    expected = {
        "alpha": {c for (c, _r, _v) in alpha_impacted},
        "beta": {c for (c, _r, _v) in beta_impacted},
    }
    other = {"alpha": "beta", "beta": "alpha"}

    for tag in ("alpha", "beta"):
        report = results[tag]
        assert field(report, "scope") == "blast-radius"
        components = field(report, "components")
        keys = set(components.keys())
        assert keys == expected[tag], (
            tag + " result components " + repr(sorted(keys))
            + " do not match its own fake's blast radius " + repr(sorted(expected[tag]))
        )
        assert not (keys & expected[other[tag]]), (
            tag + " result leaked the other repo_root's fake ids: "
            + repr(sorted(keys & expected[other[tag]]))
        )

    alpha_impact_log = _read_lines(log_dir / "impact_alpha.log")
    beta_impact_log = _read_lines(log_dir / "impact_beta.log")
    assert alpha_impact_log == ["alpha\tcomp-zebra-alpha-one"]
    assert beta_impact_log == ["beta\tcomp-quokka-beta-one"]

    alpha_checker_ids = {
        line.split("\t")[2] for line in _read_lines(log_dir / "checker_alpha.log")
    }
    beta_checker_ids = {
        line.split("\t")[2] for line in _read_lines(log_dir / "checker_beta.log")
    }
    assert alpha_checker_ids == expected["alpha"]
    assert beta_checker_ids == expected["beta"]