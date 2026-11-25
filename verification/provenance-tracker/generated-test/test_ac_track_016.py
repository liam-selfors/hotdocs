# hotdocs-criterion: sha256:61ee293ca9adef20b2c8df968235d1278e742847c57ddf9cc06e3972b4d477dd
"""AC-TRACK-016: check_readiness judges secrets by one fresh repository scan."""

from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


STORED_SECRET_SCAN = {"flagged": True, "matches": []}


PROVENANCE_CHECKER_SRC = (
    "class _Key:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    return None\n"
    "\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    return _Key(\n"
    "        " + repr("sha256:" + "ab" * 32) + ",\n"
    "        " + repr({
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.3",
        "secret_scanner": "secret_scanner@0.0.0",
        "generator": "generator@3.0.0+v11",
    }) + ",\n"
    "        " + repr([{
        "kind": "python", "path": ".", "definition_sha256": None,
        "adapter_sha256": None, "versions": {"python": "3"},
        "lockfile_sha256": None,
    }]) + ",\n"
    "    )\n"
    "\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    return {\n"
    "        'hit': True,\n"
    "        'reason': None,\n"
    "        'verification_report': " + repr({
        "component_id": "comp-plain",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
    }) + ",\n"
    "        'license_scan': " + repr({"blocked": False}) + ",\n"
    "        'secret_scan': " + repr(STORED_SECRET_SCAN) + ",\n"
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


SECRET_SCANNER_SRC = (
    "import os\n"
    "\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "\n"
    "def scan(repo_root):\n"
    "    log = os.environ['AC_TRACK_016_SCAN_LOG']\n"
    "    with open(log, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(str(repo_root) + '\\n')\n"
    "    mode = os.environ.get('AC_TRACK_016_SCAN_MODE', 'clean')\n"
    "    if mode == 'raise':\n"
    "        raise RuntimeError('boom')\n"
    "    if mode == 'flagged':\n"
    "        return " + repr({
        "flagged": True,
        "matches": [{"file": "a/b.py", "line": 3, "rule_id": "AWS Access Key", "risk_tier": "high"}],
    }) + "\n"
    "    return " + repr({"flagged": False, "matches": []}) + "\n"
)


IMPACT_ANALYZER_SRC = (
    "class ImpactedComponent:\n"
    "    def __init__(self, component_id, reason, via, guarantee_ids=None):\n"
    "        self.component_id = component_id\n"
    "        self.reason = reason\n"
    "        self.via = via\n"
    "        self.guarantee_ids = guarantee_ids\n"
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
    "class BlastRadiusReport:\n"
    "    def __init__(self, impacted, precondition_error):\n"
    "        self.impacted = impacted\n"
    "        self.precondition_error = precondition_error\n"
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
    "    return BlastRadiusReport([], " + repr("spec-linter reported hard failures") + ")\n"
)


CAPABILITY_VERIFIER_SRC = (
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
    "    return {}\n"
    "\n"
    "\n"
    "def check_capability_provenance(capability_id, repo_root):\n"
    "    return {'hit': True, 'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
    "\n"
    "\n"
    "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
    "    return {'hit': True, 'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(tmp_path, monkeypatch, mode):
    repo_root = tmp_path / "repo"
    comp = repo_root / "specs" / "components" / "plain"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-plain\n"
        "title: Plain\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Plain\n"
        "\n"
        "A plain fixture component.\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        comp / "requirements" / "R-PLAIN-001.md",
        "# R-PLAIN-001\n\nThe component MUST exist.\n",
    )
    _write(
        comp / "acceptance" / "AC-PLAIN-001.md",
        "# AC-PLAIN-001\n\nCovers: R-PLAIN-001\nKind: llm-judge\n\nThe component exists.\n",
    )
    _write(comp / "interface" / "library.md", "# Library\n\nNothing.\n")

    gen = repo_root / "gen"
    _write(gen / "provenance-checker" / "provenance_checker.py", PROVENANCE_CHECKER_SRC)
    _write(gen / "secret-scanner" / "secret_scanner.py", SECRET_SCANNER_SRC)
    _write(gen / "impact-analyzer" / "impact_analyzer.py", IMPACT_ANALYZER_SRC)
    _write(
        gen / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        CAPABILITY_VERIFIER_SRC,
    )

    log = tmp_path / "scan.log"
    monkeypatch.setenv("AC_TRACK_016_SCAN_LOG", str(log))
    monkeypatch.setenv("AC_TRACK_016_SCAN_MODE", mode)
    return repo_root, log


def _log_lines(log):
    if not log.exists():
        return []
    return [line for line in log.read_text(encoding="utf-8").splitlines() if line != ""]


def test_clean_scan_is_ready_and_stored_scan_untouched(tmp_path, monkeypatch):
    repo_root, log = _build_repo(tmp_path, monkeypatch, "clean")

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []
    assert _log_lines(log) == [str(repo_root)]
    secret_scan = field(report, "secret_scan")
    assert field(secret_scan, "flagged") is False
    assert list(field(secret_scan, "matches")) == []
    if isinstance(secret_scan, dict):
        assert secret_scan == {"flagged": False, "matches": []}
    components = field(report, "components")
    plain = components["comp-plain"]
    assert field(plain, "secret_scan") == STORED_SECRET_SCAN


def test_flagged_scan_is_not_ready(tmp_path, monkeypatch):
    repo_root, log = _build_repo(tmp_path, monkeypatch, "flagged")

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "secret_scan flagged: a/b.py:3 AWS Access Key"
    ]
    assert _log_lines(log) == [str(repo_root)]


def test_failed_scan_is_reported_not_raised(tmp_path, monkeypatch):
    repo_root, log = _build_repo(tmp_path, monkeypatch, "raise")

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "secret_scan") is None
    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "secret_scan unavailable: RuntimeError: boom"
    ]


def test_precondition_error_never_scans(tmp_path, monkeypatch):
    repo_root, log = _build_repo(tmp_path, monkeypatch, "clean")

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-plain"])

    assert _log_lines(log) == []
    assert field(report, "secret_scan") is None