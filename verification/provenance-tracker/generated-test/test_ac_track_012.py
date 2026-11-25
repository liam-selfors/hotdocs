# hotdocs-criterion: sha256:b0c7d2d9eaa3a2d8734077c9e893549b7f3b19c09cd60945dc0fbdcbb3c378c2
"""AC-TRACK-012: check_readiness reads dict-shaped dependency results.

Given a dict-shaped (never object-shaped) fake provenance-checker result and
a dict-shaped fake impact-analyzer impacted entry, check_readiness reads
hit/component_id/etc. correctly from the dict shape and does not raise
AttributeError.
"""

import copy
from pathlib import Path

import pytest

import provenance_tracker


LOG_ENV = "HOTDOCS_AC_TRACK_012_LOG"

COMPONENT_ID = "comp-foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.3+abc",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}

ASSETS = [
    {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": "sha256:00",
        "versions": {"python": "3.12.4"},
        "lockfile_sha256": None,
    }
]

VERIFICATION_REPORT = {
    "component_id": COMPONENT_ID,
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "mutation_error": None,
    "assets": copy.deepcopy(ASSETS),
    "overall": "pass",
}

LICENSE_SCAN = {
    "component_id": COMPONENT_ID,
    "gate_version": "license_scanner@4.0.3+abc",
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

STORED_SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@0.0.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

HIT_RESULT = {
    "hit": True,
    "reason": None,
    "verification_report": VERIFICATION_REPORT,
    "license_scan": LICENSE_SCAN,
    "secret_scan": STORED_SECRET_SCAN,
}

MISS_RESULT = {
    "hit": False,
    "reason": "no manifest",
    "verification_report": None,
    "license_scan": None,
    "secret_scan": None,
}

NOT_SEALED_RESULT = {
    "hit": False,
    "sealed": False,
    "reason": "not_sealed",
    "verification_report": None,
    "license_scan": None,
    "secret_scan": None,
    "owners": None,
    "source_hash": None,
    "written_at": None,
}

BLAST_RADIUS = {
    "impacted": [
        {"component_id": COMPONENT_ID, "reason": "direct", "via": None}
    ],
    "precondition_error": None,
}

LOG_HELPER = (
    "import os\n"
    "\n"
    "def _log(line):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as f:\n"
    "        f.write(line + '\\n')\n"
    "\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_fixture(repo_root, check_result):
    # Minimal spec corpus for the one component.
    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do one thing.\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: llm-judge\n\nFoo does one thing.\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "constraints.md",
        "# Constraints\n\nNone.\n",
    )

    # Fake provenance-checker: every result is dict-shaped except the
    # ProvenanceKey, which is documented as an attribute object.
    write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        "import copy\n"
        + LOG_HELPER
        + "GATE_VERSIONS = " + repr(GATE_VERSIONS) + "\n"
        "ASSETS = " + repr(ASSETS) + "\n"
        "CHECK_RESULT = " + repr(check_result) + "\n"
        "NOT_SEALED = " + repr(NOT_SEALED_RESULT) + "\n"
        "\n"
        "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key ' + str(component_id))\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key ' + str(component_id))\n"
        "    return ProvenanceKey('sha256:ab', dict(GATE_VERSIONS), copy.deepcopy(ASSETS))\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance ' + str(component_id))\n"
        "    return copy.deepcopy(CHECK_RESULT)\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance ' + str(component_id))\n"
        "    return copy.deepcopy(NOT_SEALED)\n",
    )

    # Fake impact-analyzer: dict-shaped report and dict-shaped impacted entry.
    write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        "import copy\n"
        + LOG_HELPER
        + "REPORT = " + repr(BLAST_RADIUS) + "\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log('compute_blast_radius ' + ','.join(str(c) for c in changed_ids))\n"
        "    return copy.deepcopy(REPORT)\n",
    )

    # Fake capability-scenario-verifier (dict-shaped hits), in case any
    # capability is consulted.
    write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        LOG_HELPER
        + "GATE_VERSION = 'capability_scenario_verifier@2.2.0'\n"
        "\n"
        "class UnknownCapabilityError(ValueError):\n"
        "    pass\n"
        "\n"
        "class ModelRequiredError(ValueError):\n"
        "    pass\n"
        "\n"
        "def _hit(capability_id):\n"
        "    return {'hit': True, 'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    _log('check_capability_provenance ' + str(capability_id))\n"
        "    return _hit(capability_id)\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    _log('run_capability_gates ' + str(capability_id))\n"
        "    return _hit(capability_id)\n"
        "\n"
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    return {}\n",
    )

    # Stand-in secret-scanner, per repository-secret-scan.md's fixtures.
    write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        LOG_HELPER
        + "def scan(repo_root):\n"
        "    _log('scan ' + str(repo_root))\n"
        "    return {'flagged': False, 'matches': []}\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@0.0.0'\n",
    )


def read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text().splitlines() if line]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    return repo_root, log_path


def test_dict_shaped_hit_is_read_without_attribute_error(repo):
    repo_root, log_path = repo
    build_fixture(repo_root, HIT_RESULT)

    try:
        report = provenance_tracker.check_readiness(repo_root, changed_ids=[COMPONENT_ID])
    except AttributeError as exc:  # pragma: no cover - the failure being tested
        pytest.fail("check_readiness raised AttributeError on dict-shaped results: " + repr(exc))

    log = read_log(log_path)
    # component_id was read from the dict-shaped impacted entry and passed on.
    assert "check_provenance " + COMPONENT_ID in log, log

    assert field(report, "scope") == "blast-radius"
    components = field(report, "components")
    assert COMPONENT_ID in components
    entry = components[COMPONENT_ID]
    assert field(entry, "hit") is True
    assert field(entry, "reason") is None

    # hit was read correctly from the dict: the component is ready.
    reasons = list(field(report, "not_ready_reasons"))
    assert not any(COMPONENT_ID in str(r) for r in reasons), reasons
    assert field(report, "ready") is True, reasons
    assert reasons == []


def test_dict_shaped_miss_is_read_without_attribute_error(repo):
    repo_root, log_path = repo
    build_fixture(repo_root, MISS_RESULT)

    try:
        report = provenance_tracker.check_readiness(repo_root, changed_ids=[COMPONENT_ID])
    except AttributeError as exc:  # pragma: no cover - the failure being tested
        pytest.fail("check_readiness raised AttributeError on dict-shaped results: " + repr(exc))

    log = read_log(log_path)
    assert "check_provenance " + COMPONENT_ID in log, log

    components = field(report, "components")
    assert COMPONENT_ID in components
    entry = components[COMPONENT_ID]
    assert field(entry, "hit") is False
    assert field(entry, "reason") == "no manifest"

    # hit=False was read correctly from the dict: not ready, and the
    # component (by the component_id read from the dict entry) is named.
    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    assert any(COMPONENT_ID in str(r) for r in reasons), reasons