import pytest


def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def read_field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def lookup(container, key):
    if isinstance(container, dict):
        return container.get(key)
    return getattr(container, key, None)


PROVENANCE_CHECKER_SRC = r'''
from pathlib import Path

LOG_PATH = Path(__file__).parent / "invocations.log"


def _log(name, component_id):
    with open(LOG_PATH, "a") as f:
        f.write(name + ":" + component_id + "\n")


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id)
    return None


class _ProvenanceKey:
    spec_bundle_hash = "sha256:" + "0" * 64
    gate_versions = {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
        "secret_scanner": "secret_scanner@0.0.0",
    }


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id)
    return _ProvenanceKey()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id)
    return {
        "hit": True,
        "verification_report": {
            "component_id": component_id,
            "criteria": [],
            "requirement_results": {},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": "pass",
        },
        "license_scan": {
            "component_id": component_id,
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.0,
            "block_threshold": 0.70,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id)
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
'''


IMPACT_ANALYZER_SRC = r'''
from pathlib import Path

LOG_PATH = Path(__file__).parent / "invocations.log"


def compute_blast_radius(changed_ids, repo_root):
    with open(LOG_PATH, "a") as f:
        f.write("compute_blast_radius:" + ",".join(changed_ids) + "\n")
    return {
        "impacted": [
            {"component_id": "comp-foo", "reason": "direct", "via": None},
        ],
        "precondition_error": None,
    }
'''


def build_repo(tmp_path):
    repo_root = tmp_path / "repo"

    write_file(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "sealed: false\n"
        "realizes: []\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "---\n"
        "\n"
        "Foo component.\n",
    )

    write_file(
        repo_root / "gen" / "foo" / "foo.py",
        "# placeholder generated component code\n",
    )

    write_file(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        PROVENANCE_CHECKER_SRC,
    )

    write_file(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        IMPACT_ANALYZER_SRC,
    )

    return repo_root


def test_check_readiness_reads_dict_shaped_dependency_results(tmp_path):
    repo_root = build_repo(tmp_path)

    import provenance_tracker

    try:
        report = provenance_tracker.check_readiness(
            repo_root, changed_ids=["comp-foo"]
        )
    except AttributeError as exc:
        pytest.fail(
            "check_readiness raised AttributeError reading a dict-shaped "
            "dependency result: " + str(exc)
        )

    impact_analyzer_log = repo_root / "gen" / "impact-analyzer" / "invocations.log"
    provenance_checker_log = (
        repo_root / "gen" / "provenance-checker" / "invocations.log"
    )
    assert impact_analyzer_log.exists(), "fake impact-analyzer was never invoked"
    assert provenance_checker_log.exists(), "fake provenance-checker was never invoked"
    assert "check_provenance:comp-foo" in provenance_checker_log.read_text()

    scope = read_field(report, "scope")
    assert scope == "blast-radius"

    components = read_field(report, "components")
    assert components is not None

    comp_result = lookup(components, "comp-foo")
    assert comp_result is not None

    hit = read_field(comp_result, "hit")
    assert hit is True

    verification_report = read_field(comp_result, "verification_report")
    assert read_field(verification_report, "overall") == "pass"

    not_ready_reasons = read_field(report, "not_ready_reasons")
    assert not_ready_reasons == []

    ready = read_field(report, "ready")
    assert ready is True