# hotdocs-criterion: sha256:4e87b7550de3394f41d86ad3a639370ce91cd2b7d61f36c3818a44ba6972fb09
"""AC-TRACK-012: check_readiness reads dict-shaped dependency results.

Covers R-TRACK-012: every field of a value a dependency returns is read with
dual dict-or-attribute access, so dict-shaped fakes of provenance-checker's
ProvenanceCheckResult / SealedCheckResult and impact-analyzer's
BlastRadiusReport (with dict-shaped `impacted` entries) never raise
AttributeError.
"""

from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
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


def _license_scan():
    return {
        "component_id": "comp-foo",
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


def _stored_secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _hit_result():
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(),
        "license_scan": _license_scan(),
        "secret_scan": _stored_secret_scan(),
    }


def _miss_result():
    return {
        "hit": False,
        "reason": "no manifest",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def _sealed_check_result():
    return {
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


def _blast_radius():
    return {
        "impacted": [
            {"component_id": "comp-foo", "reason": "direct", "via": None},
        ],
        "precondition_error": None,
    }


def _build_fixture(repo_root, check_result):
    repo_root = Path(repo_root)
    log = repo_root / "calls.log"
    scan_log = repo_root / "scan.log"

    # Minimal spec corpus for one generated component.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do foo.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n",
    )

    # Fake provenance-checker: dict-shaped check results.
    checker_src = (
        "LOG = " + repr(str(log)) + "\n"
        "CHECK_RESULT = " + repr(check_result) + "\n"
        "SEALED_RESULT = " + repr(_sealed_check_result()) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, spec_bundle_parts, gate_versions, assets, drivers):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.spec_bundle_parts = spec_bundle_parts\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "        self.drivers = drivers\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key ' + str(component_id))\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key ' + str(component_id))\n"
        "    return ProvenanceKey(\n"
        "        " + repr("sha256:" + "b" * 64) + ",\n"
        "        " + repr({"spec": "sha256:" + "c" * 64, "dependency_code": "sha256:" + "d" * 64}) + ",\n"
        "        " + repr({
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
            "generator": "generator@3.0.0+v11",
        }) + ",\n"
        "        " + repr([{
            "kind": "python",
            "path": ".",
            "definition_sha256": "sha256:" + "e" * 64,
            "adapter_sha256": "sha256:" + "f" * 64,
            "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }]) + ",\n"
        "        [],\n"
        "    )\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance ' + str(component_id))\n"
        "    import copy\n"
        "    return copy.deepcopy(CHECK_RESULT)\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance ' + str(component_id))\n"
        "    import copy\n"
        "    return copy.deepcopy(SEALED_RESULT)\n"
    )
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", checker_src)

    # Fake impact-analyzer: dict-shaped report and dict-shaped impacted entries.
    impact_src = (
        "LOG = " + repr(str(log)) + "\n"
        "REPORT = " + repr(_blast_radius()) + "\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('compute_blast_radius ' + ','.join(changed_ids) + '\\n')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
    )
    _write(repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py", impact_src)

    # Fake capability-scenario-verifier (no capability should intersect, but
    # provide a correct-shaped stand-in in case it is loaded).
    cap_report = {"hit": True, "capability_scenario_report": None}
    cap_src = (
        "LOG = " + repr(str(log)) + "\n"
        "GATE_VERSION = 'capability_scenario_verifier@3.0.0'\n"
        "\n"
        "class UnknownCapabilityError(ValueError):\n"
        "    pass\n"
        "\n"
        "class ModelRequiredError(ValueError):\n"
        "    pass\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def _result(capability_id):\n"
        "    r = dict(" + repr(cap_report) + ")\n"
        "    r['capability_scenario_report'] = {capability_id: {'overall': 'pass', 'scenarios': []}}\n"
        "    return r\n"
        "\n"
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    _log('run_capability_scenarios')\n"
        "    return {}\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    _log('check_capability_provenance ' + str(capability_id))\n"
        "    return _result(capability_id)\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    _log('run_capability_gates ' + str(capability_id))\n"
        "    return _result(capability_id)\n"
    )
    _write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        cap_src,
    )

    # Fake secret-scanner per the repository-secret-scan test-fixture rule.
    scanner_src = (
        "LOG = " + repr(str(scan_log)) + "\n"
        "\n"
        "def scan(repo_root):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(str(repo_root) + '\\n')\n"
        "    return " + repr({"flagged": False, "matches": []}) + "\n"
    )
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", scanner_src)

    return log, scan_log


def _read_lines(path):
    path = Path(path)
    if not path.exists():
        return []
    return [line for line in path.read_text().splitlines() if line]


def test_dict_shaped_hit_is_read_without_attribute_error(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log, scan_log = _build_fixture(repo_root, _hit_result())

    try:
        report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-foo"])
    except AttributeError as exc:  # pragma: no cover - the failure under test
        pytest.fail("check_readiness raised AttributeError on dict-shaped results: " + repr(exc))

    calls = _read_lines(log)
    assert any(line.startswith("compute_blast_radius") for line in calls), calls
    # component_id was read correctly from the dict-shaped impacted entry.
    assert "check_provenance comp-foo" in calls, calls

    assert field(report, "scope") == "blast-radius"
    components = field(report, "components")
    assert "comp-foo" in components
    entry = components["comp-foo"]
    assert field(entry, "hit") is True
    assert field(entry, "reason") is None
    assert field(field(entry, "verification_report"), "overall") == "pass"

    # hit was read correctly from the dict shape: the component is ready.
    assert field(report, "not_ready_reasons") == []
    assert field(report, "ready") is True

    assert _read_lines(scan_log) == [str(repo_root)]


def test_dict_shaped_miss_is_read_without_attribute_error(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log, scan_log = _build_fixture(repo_root, _miss_result())

    try:
        report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-foo"])
    except AttributeError as exc:  # pragma: no cover - the failure under test
        pytest.fail("check_readiness raised AttributeError on dict-shaped results: " + repr(exc))

    calls = _read_lines(log)
    assert "check_provenance comp-foo" in calls, calls

    assert field(report, "scope") == "blast-radius"
    components = field(report, "components")
    assert "comp-foo" in components
    assert field(components["comp-foo"], "hit") is False

    # hit=False was read from the dict shape: not ready, with comp-foo named.
    assert field(report, "ready") is False
    reasons = field(report, "not_ready_reasons")
    assert any("comp-foo" in r for r in reasons), reasons