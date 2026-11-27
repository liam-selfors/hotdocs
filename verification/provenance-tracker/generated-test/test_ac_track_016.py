# hotdocs-criterion: sha256:8ae726d813164910833e13aac1485c5986ae44ff979d9a66d506bb5d9d1e4b86
"""AC-TRACK-016: check_readiness judges secrets by one fresh repository scan.

Covers: R-TRACK-016
"""

from pathlib import Path

import provenance_tracker


CLEAN_SCAN = {"flagged": False, "matches": []}
FLAGGED_SCAN = {
    "flagged": True,
    "matches": [
        {"file": "a/b.py", "line": 3, "rule_id": "AWS Access Key", "risk_tier": "high"}
    ],
}
STORED_SECRET_SCAN = {"flagged": True, "matches": []}

VERIFICATION_REPORT = {
    "component_id": "comp-plain",
    "criteria": [
        {"id": "AC-PLAIN-001", "covers": "R-PLAIN-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-PLAIN-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
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
    "drivers": [],
    "overall": "pass",
}

LICENSE_SCAN = {
    "component_id": "comp-plain",
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

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}

PROVENANCE_RESULT = {
    "hit": True,
    "reason": None,
    "verification_report": VERIFICATION_REPORT,
    "license_scan": LICENSE_SCAN,
    "secret_scan": STORED_SECRET_SCAN,
}

SPEC_HASH = "sha256:" + "b" * 64
SPEC_PARTS = {"spec": "sha256:" + "c" * 64, "dependency_code": "sha256:" + "d" * 64}
ASSETS = [
    {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": "sha256:" + "a" * 64,
        "versions": {"python": "3.12.4"},
        "lockfile_sha256": None,
    }
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def provenance_checker_source():
    lines = [
        "class _Key:",
        "    def __init__(self):",
        "        self.spec_bundle_hash = " + repr(SPEC_HASH),
        "        self.spec_bundle_parts = " + repr(SPEC_PARTS),
        "        self.gate_versions = " + repr(GATE_VERSIONS),
        "        self.assets = " + repr(ASSETS),
        "        self.drivers = []",
        "",
        "",
        "def current_sealed_key(component_id, repo_root):",
        "    return None",
        "",
        "",
        "def current_provenance_key(component_id, repo_root):",
        "    return _Key()",
        "",
        "",
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):",
        "    return " + repr(PROVENANCE_RESULT),
        "",
        "",
        "def check_sealed_provenance(component_id, repo_root):",
        "    return " + repr({
            "hit": False,
            "sealed": False,
            "reason": "not_sealed",
            "verification_report": None,
            "license_scan": None,
            "secret_scan": None,
            "owners": None,
            "source_hash": None,
            "written_at": None,
        }),
        "",
    ]
    return "\n".join(lines)


def secret_scanner_source(log_path, mode):
    lines = [
        "def gate_version(repo_root):",
        "    return 'secret_scanner@0.0.0'",
        "",
        "",
        "def scan(repo_root):",
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:",
        "        fh.write(str(repo_root) + '\\n')",
    ]
    if mode == "clean":
        lines.append("    return " + repr(CLEAN_SCAN))
    elif mode == "flagged":
        lines.append("    return " + repr(FLAGGED_SCAN))
    else:
        lines.append("    raise RuntimeError('boom')")
    lines.append("")
    return "\n".join(lines)


def impact_analyzer_source():
    lines = [
        "class BlastRadiusReport:",
        "    def __init__(self, impacted, precondition_error):",
        "        self.impacted = impacted",
        "        self.precondition_error = precondition_error",
        "",
        "    def __getitem__(self, key):",
        "        return getattr(self, key)",
        "",
        "    def to_dict(self):",
        "        return {'impacted': [], 'precondition_error': self.precondition_error}",
        "",
        "",
        "def compute_blast_radius(changed_ids, repo_root):",
        "    return BlastRadiusReport([], " + repr("spec-linter reported hard failures") + ")",
        "",
    ]
    return "\n".join(lines)


def capability_verifier_source():
    lines = [
        "GATE_VERSION = 'capability_scenario_verifier@3.0.0'",
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
        "def _hit(capability_id):",
        "    return {'hit': True, 'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}",
        "",
        "",
        "def check_capability_provenance(capability_id, repo_root):",
        "    return _hit(capability_id)",
        "",
        "",
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):",
        "    return _hit(capability_id)",
        "",
        "",
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):",
        "    return {}",
        "",
    ]
    return "\n".join(lines)


def make_repo(tmp_path, scan_mode):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "scan.log"
    comp = repo_root / "specs" / "components" / "plain"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-plain\n"
        "title: Plain Component\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Plain Component\n"
        "\n"
        "A plain component used as a test fixture.\n",
    )
    write(
        comp / "requirements" / "R-PLAIN-001.md",
        "# R-PLAIN-001\n\n**R-PLAIN-001** — The component MUST do a plain thing.\n",
    )
    write(
        comp / "acceptance" / "AC-PLAIN-001.md",
        "# AC-PLAIN-001\n\nCovers: R-PLAIN-001\nKind: compiled\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\n```\nplain() -> None\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Plain** — plain.\n")

    write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", provenance_checker_source())
    write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", secret_scanner_source(log_path, scan_mode))
    write(repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py", impact_analyzer_source())
    write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        capability_verifier_source(),
    )
    return repo_root, log_path


def read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line != ""]


def test_clean_scan_is_ready_and_uses_fresh_scan_not_stored(tmp_path):
    repo_root, log_path = make_repo(tmp_path, "clean")

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []
    assert read_log(log_path) == [str(repo_root)]
    assert field(report, "secret_scan") == {"flagged": False, "matches": []}
    components = field(report, "components")
    assert field(components["comp-plain"], "secret_scan") == {"flagged": True, "matches": []}


def test_flagged_scan_makes_report_not_ready(tmp_path):
    repo_root, log_path = make_repo(tmp_path, "flagged")

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "secret_scan flagged: a/b.py:3 AWS Access Key"
    ]
    assert read_log(log_path) == [str(repo_root)]


def test_failed_scan_is_reported_unavailable_without_raising(tmp_path):
    repo_root, log_path = make_repo(tmp_path, "raise")

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "secret_scan") is None
    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "secret_scan unavailable: RuntimeError: boom"
    ]


def test_precondition_error_never_calls_scan(tmp_path):
    repo_root, log_path = make_repo(tmp_path, "clean")

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-plain"])

    assert read_log(log_path) == []
    assert field(report, "secret_scan") is None