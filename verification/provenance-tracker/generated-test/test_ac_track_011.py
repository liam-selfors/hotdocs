# hotdocs-criterion: sha256:4dad570a46071403f6132959d878856144ca749d2896daa2c7a1c15291c8a2ed
"""AC-TRACK-011: check_readiness resolves dependencies relative to each repo_root.

Two separate repo_root directories each hold their own fake impact-analyzer
(plus fakes for every other dependency check_readiness may load). Calling
check_readiness once against each, in the same process and in either order,
must give results that reflect only that call's own repo_root's fake.
"""

import os
from pathlib import Path

import pytest

import provenance_tracker


LOG_ENV = "AC_TRACK_011_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


LOG_HELPER = (
    "import os\n"
    "\n"
    "def _log(line):\n"
    "    path = os.environ.get(" + repr(LOG_ENV) + ")\n"
    "    if path:\n"
    "        with open(path, 'a', encoding='utf-8') as fh:\n"
    "            fh.write(line + '\\n')\n"
    "\n"
)


def _impact_source(tag, impacted_ids):
    return (
        "import dataclasses\n"
        "from pathlib import Path\n"
        + LOG_HELPER
        + "TAG = " + repr(tag) + "\n"
        "IMPACTED_IDS = " + repr(list(impacted_ids)) + "\n"
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
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key, default)\n"
        "\n"
        "    def to_dict(self):\n"
        "        d = {'component_id': self.component_id, 'reason': self.reason, 'via': self.via}\n"
        "        if self.reason == 'transitive-guarantee':\n"
        "            d['guarantee_ids'] = self.guarantee_ids\n"
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
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key, default)\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'impacted': [i.to_dict() for i in self.impacted],\n"
        "                'precondition_error': self.precondition_error}\n"
        "\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log(TAG + ' impact ' + str(repo_root))\n"
        "    entries = [ImpactedComponent(component_id=cid, reason='direct', via=None)\n"
        "               for cid in sorted(IMPACTED_IDS)]\n"
        "    return BlastRadiusReport(impacted=entries, precondition_error=None)\n"
    )


def _checker_source(tag):
    return (
        "from pathlib import Path\n"
        + LOG_HELPER
        + "TAG = " + repr(tag) + "\n"
        "ZERO_HASH = 'sha256:' + '0' * 64\n"
        "\n"
        "\n"
        "class SealedKey:\n"
        "    def __init__(self, owners, source_path, source_hash, verifier_version):\n"
        "        self.owners = owners\n"
        "        self.source_path = source_path\n"
        "        self.source_hash = source_hash\n"
        "        self.verifier_version = verifier_version\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "\n"
        "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "\n"
        "def _slug(component_id):\n"
        "    return component_id[5:] if component_id.startswith('comp-') else component_id\n"
        "\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log(TAG + ' sealed_key ' + component_id)\n"
        "    return SealedKey(owners=['test-team'],\n"
        "                     source_path='legacy/' + _slug(component_id) + '/',\n"
        "                     source_hash=ZERO_HASH,\n"
        "                     verifier_version='verifier-orchestrator@2.0.0')\n"
        "\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log(TAG + ' sealed_check ' + component_id)\n"
        "    return {\n"
        "        'hit': True,\n"
        "        'sealed': True,\n"
        "        'reason': None,\n"
        "        'verification_report': {'overall': 'pass'},\n"
        "        'license_scan': None,\n"
        "        'secret_scan': None,\n"
        "        'owners': ['test-team'],\n"
        "        'source_hash': ZERO_HASH,\n"
        "        'written_at': '2026-11-02T00:00:00Z',\n"
        "    }\n"
        "\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log(TAG + ' prov_key ' + component_id)\n"
        "    return ProvenanceKey(\n"
        "        spec_bundle_hash=ZERO_HASH,\n"
        "        gate_versions={\n"
        "            'compiler': 'criterion-compiler@1.0.0',\n"
        "            'generated_test': 'generated_test@1.0.0',\n"
        "            'verifier': 'verifier-orchestrator@2.0.0',\n"
        "            'license_scanner': 'license_scanner@4.0.3',\n"
        "            'secret_scanner': 'secret_scanner@0.0.0',\n"
        "            'generator': 'generator@3.0.0+v11',\n"
        "        },\n"
        "        assets=[{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                 'adapter_sha256': ZERO_HASH, 'versions': {'python': '3.12.4'},\n"
        "                 'lockfile_sha256': None}],\n"
        "    )\n"
        "\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log(TAG + ' prov_check ' + component_id)\n"
        "    return {\n"
        "        'hit': True,\n"
        "        'reason': None,\n"
        "        'verification_report': {\n"
        "            'component_id': component_id,\n"
        "            'criteria': [],\n"
        "            'requirement_results': {},\n"
        "            'interface_drift': False,\n"
        "            'mutation_score': None,\n"
        "            'mutation_error': None,\n"
        "            'assets': [],\n"
        "            'overall': 'pass',\n"
        "        },\n"
        "        'license_scan': None,\n"
        "        'secret_scan': None,\n"
        "    }\n"
    )


def _capability_source(tag):
    return (
        "from pathlib import Path\n"
        + LOG_HELPER
        + "TAG = " + repr(tag) + "\n"
        "GATE_VERSION = 'capability_scenario_verifier@2.2.0'\n"
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
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    _log(TAG + ' cap_scenarios ' + str(repo_root))\n"
        "    return {}\n"
        "\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    _log(TAG + ' cap_check ' + capability_id)\n"
        "    return {'hit': True, 'capability_scenario_report':\n"
        "            {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
        "\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    _log(TAG + ' cap_gates ' + capability_id)\n"
        "    return {'hit': True, 'capability_scenario_report':\n"
        "            {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
    )


def _secret_source(tag):
    return (
        "from pathlib import Path\n"
        + LOG_HELPER
        + "TAG = " + repr(tag) + "\n"
        "\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log(TAG + ' secret_scan ' + str(repo_root))\n"
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
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# Fixture " + slug + "\n"
        "\n"
        "A fixture component for AC-TRACK-011.\n"
    )


def _build_repo(root, tag, impacted_ids):
    root.mkdir(parents=True, exist_ok=True)
    gen = root / "gen"
    _write(gen / "impact-analyzer" / "impact_analyzer.py", _impact_source(tag, impacted_ids))
    _write(gen / "provenance-checker" / "provenance_checker.py", _checker_source(tag))
    _write(
        gen / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        _capability_source(tag),
    )
    _write(gen / "secret-scanner" / "secret_scanner.py", _secret_source(tag))
    for cid in impacted_ids:
        slug = cid[len("comp-"):]
        _write(root / "specs" / "components" / slug / "component.md", _component_md(cid))
    return root


A_IDS = ["comp-alpha-north", "comp-alpha-south"]
B_IDS = ["comp-beta-east", "comp-beta-west", "comp-beta-zenith"]


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]


@pytest.mark.parametrize("order", [("A", "B"), ("B", "A")])
def test_check_readiness_resolves_impact_analyzer_per_repo_root(tmp_path, monkeypatch, order):
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    repo_a = _build_repo(tmp_path / "repo_a", "A", A_IDS)
    repo_b = _build_repo(tmp_path / "repo_b", "B", B_IDS)

    setup = {
        "A": (repo_a, [A_IDS[0]], A_IDS, B_IDS),
        "B": (repo_b, [B_IDS[0]], B_IDS, A_IDS),
    }

    results = {}
    for tag in order:
        repo_root, changed, _, _ = setup[tag]
        results[tag] = provenance_tracker.check_readiness(repo_root, changed_ids=changed)

    for tag in order:
        repo_root, _, own_ids, other_ids = setup[tag]
        report = results[tag]
        assert field(report, "scope") == "blast-radius"
        components = field(report, "components")
        keys = set(components.keys())
        assert keys == set(own_ids), (
            "repo " + tag + " result should reflect its own fake's impacted ids "
            + repr(sorted(own_ids)) + ", got " + repr(sorted(keys))
        )
        assert not (keys & set(other_ids)), (
            "repo " + tag + " result leaked the other repo_root's fake ids: "
            + repr(sorted(keys & set(other_ids)))
        )

    lines = _read_log(log_path)
    impact_lines = [ln for ln in lines if " impact " in ln]
    a_impact = [ln for ln in impact_lines if ln.startswith("A impact ")]
    b_impact = [ln for ln in impact_lines if ln.startswith("B impact ")]
    assert len(a_impact) >= 1, "repo A's fake impact-analyzer never ran: " + repr(lines)
    assert len(b_impact) >= 1, "repo B's fake impact-analyzer never ran: " + repr(lines)

    for ln in a_impact:
        logged = ln[len("A impact "):]
        assert os.path.realpath(logged) == os.path.realpath(str(repo_a))
    for ln in b_impact:
        logged = ln[len("B impact "):]
        assert os.path.realpath(logged) == os.path.realpath(str(repo_b))

    # The first impact call logged belongs to the first repo_root called,
    # the second to the second: neither call reused the other's fake.
    first_tags = [ln.split(" ", 1)[0] for ln in impact_lines]
    assert first_tags[0] == order[0]
    assert order[1] in first_tags[first_tags.index(order[0]):]
    second_start = next(i for i, t in enumerate(first_tags) if t == order[1])
    assert all(t == order[1] for t in first_tags[second_start:]), repr(impact_lines)