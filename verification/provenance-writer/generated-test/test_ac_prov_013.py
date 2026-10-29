import json

import provenance_writer


def _build_generation_result():
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"spec_linter.py": "# generated content"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _build_verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }


def _build_license_scan_result():
    return {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.0,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _build_secret_scan_result():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@2.0.0",
        "flagged": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _build_inputs():
    return provenance_writer.ProvenanceInputs(
        component_id="comp-foo",
        generation_result=_build_generation_result(),
        verification_report=_build_verification_report(),
        license_scan_result=_build_license_scan_result(),
        secret_scan_result=_build_secret_scan_result(),
        provenance_hit=False,
        attempts=2,
        gate_versions={"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    )


def _collect_manifests(repo_root):
    manifests = []
    for path in repo_root.rglob(".provenance.json"):
        with open(path, "r", encoding="utf-8") as f:
            manifests.append(json.load(f))
    return manifests


def test_verification_run_id_is_slug_attempt_construction(tmp_path):
    repo_root = tmp_path / "repo1"
    repo_root.mkdir()

    inputs = _build_inputs()

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    manifests = _collect_manifests(repo_root)
    assert len(manifests) == 2

    run_ids = {m["verification_run_id"] for m in manifests}
    assert run_ids == {"foo-attempt-2"}


def test_verification_run_id_identical_across_repeated_runs(tmp_path):
    repo_root_a = tmp_path / "repo_a"
    repo_root_a.mkdir()
    repo_root_b = tmp_path / "repo_b"
    repo_root_b.mkdir()

    inputs = _build_inputs()

    provenance_writer.write_provenance("comp-foo", inputs, repo_root_a)
    provenance_writer.write_provenance("comp-foo", inputs, repo_root_b)

    run_ids_a = {m["verification_run_id"] for m in _collect_manifests(repo_root_a)}
    run_ids_b = {m["verification_run_id"] for m in _collect_manifests(repo_root_b)}

    assert len(run_ids_a) == 1
    assert run_ids_a == run_ids_b