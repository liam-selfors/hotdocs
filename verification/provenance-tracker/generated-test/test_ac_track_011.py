from pathlib import Path

import pytest

import provenance_tracker


_PROVENANCE_CHECKER_SRC = '''
class _SealedKey:
    owners = ["pipeline-team"]
    source_path = "fake/sealed/"
    source_hash = "sha256:" + "0" * 64
    verifier_version = "verifier-orchestrator@2.0.0"


class _ProvenanceKey:
    spec_bundle_hash = "sha256:" + "1" * 64
    gate_versions = {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@1.0.0",
        "secret_scanner": "secret_scanner@1.0.0",
    }


def current_sealed_key(component_id, repo_root):
    return _SealedKey()


def current_provenance_key(component_id, repo_root):
    return _ProvenanceKey()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    return {
        "hit": False,
        "sealed": True,
        "reason": "manifest_missing",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
        "owners": None,
        "source_hash": None,
        "written_at": None,
    }
'''


def _impact_analyzer_source(component_id: str) -> str:
    return (
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': '" + component_id + "', 'reason': 'direct', 'via': None}\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    )


def _build_repo(repo_root: Path, distinctive_component_id: str) -> Path:
    impact_analyzer_path = repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py"
    impact_analyzer_path.parent.mkdir(parents=True, exist_ok=True)
    impact_analyzer_path.write_text(_impact_analyzer_source(distinctive_component_id))

    provenance_checker_path = repo_root / "gen" / "provenance-checker" / "provenance_checker.py"
    provenance_checker_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_checker_path.write_text(_PROVENANCE_CHECKER_SRC)

    return repo_root


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


@pytest.mark.parametrize("order", ["ab", "ba"])
def test_check_readiness_resolves_impact_analyzer_per_repo_root(tmp_path, order):
    repo_a = _build_repo(tmp_path / "repo_a", "comp-fake-alpha")
    repo_b = _build_repo(tmp_path / "repo_b", "comp-fake-beta")

    call_order = {
        "ab": [("a", repo_a), ("b", repo_b)],
        "ba": [("b", repo_b), ("a", repo_a)],
    }[order]

    results = {}
    for label, repo_root in call_order:
        results[label] = provenance_tracker.check_readiness(
            repo_root, changed_ids=["SPEC-TRIGGER"]
        )

    components_a = _get(results["a"], "components")
    components_b = _get(results["b"], "components")

    assert isinstance(components_a, dict)
    assert isinstance(components_b, dict)

    assert "comp-fake-alpha" in components_a
    assert "comp-fake-beta" not in components_a

    assert "comp-fake-beta" in components_b
    assert "comp-fake-alpha" not in components_b

    reasons_a = _get(results["a"], "not_ready_reasons") or []
    reasons_b = _get(results["b"], "not_ready_reasons") or []

    assert any("comp-fake-alpha" in reason for reason in reasons_a)
    assert not any("comp-fake-beta" in reason for reason in reasons_a)

    assert any("comp-fake-beta" in reason for reason in reasons_b)
    assert not any("comp-fake-alpha" in reason for reason in reasons_b)