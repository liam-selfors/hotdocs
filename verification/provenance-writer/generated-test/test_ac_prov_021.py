import json
import re
from datetime import datetime, timedelta, timezone

import pytest

import provenance_writer


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _make_provenance_inputs(**kwargs):
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None:
        try:
            return cls(**kwargs)
        except TypeError:
            pass
    return dict(kwargs)


def _generation_result(files, model_call_error=None, refused=None, retry_feedback=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": files,
        "model_call_error": model_call_error,
        "refused": refused,
        "retry_feedback": retry_feedback,
    }


def _verification_report(overall="pass"):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "overall": overall,
    }


def _license_scan_result():
    return {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.3",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.1,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _secret_scan_result():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def test_write_provenance_overwrites_stale_identical_copies(tmp_path):
    repo_root = tmp_path
    gen_dir = repo_root / "gen" / "foo"
    verif_dir = repo_root / "verification" / "foo"
    gen_dir.mkdir(parents=True)
    verif_dir.mkdir(parents=True)

    stale = {"stale": True, "marker": "old"}
    gen_file = gen_dir / ".provenance.json"
    verif_file = verif_dir / ".provenance.json"
    gen_file.write_text(json.dumps(stale))
    verif_file.write_text(json.dumps(stale))

    generation_result = _generation_result(files={"foo.py": "print(1)"}, retry_feedback=["R-FOO-003"])
    verification_report = _verification_report()
    license_scan_result = _license_scan_result()
    secret_scan_result = _secret_scan_result()
    gate_versions = {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"}

    inputs = _make_provenance_inputs(
        component_id="comp-foo",
        generation_result=generation_result,
        verification_report=verification_report,
        license_scan_result=license_scan_result,
        secret_scan_result=secret_scan_result,
        provenance_hit=False,
        attempts=2,
        gate_versions=gate_versions,
    )

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    gen_manifest = json.loads(gen_file.read_text())
    verif_manifest = json.loads(verif_file.read_text())

    assert gen_manifest == verif_manifest
    assert gen_manifest != stale
    assert _get(gen_manifest, "verification_report") == verification_report
    assert _get(gen_manifest, "license_scan") == license_scan_result
    assert _get(gen_manifest, "secret_scan") == secret_scan_result
    assert _get(gen_manifest, "provenance_hit") is False
    assert _get(gen_manifest, "gate_versions") == gate_versions
    assert _get(gen_manifest, "prompt_version") == "v1"


def test_write_sealed_provenance_overwrites_stale_single_file(tmp_path):
    repo_root = tmp_path
    source_dir = repo_root / "pipeline" / "foo"
    source_dir.mkdir(parents=True)
    sealed_file = source_dir / ".sealed-provenance.json"
    stale = {"stale": True}
    sealed_file.write_text(json.dumps(stale))

    verification_report = _verification_report(overall="pass")
    source_hash = "sha256:" + ("1234567890abcdef" * 4)

    inputs = {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": source_hash,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": verification_report,
    }

    before = datetime.now(timezone.utc).replace(microsecond=0)
    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)
    after = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=1)

    matches = list(repo_root.rglob(".sealed-provenance.json"))
    assert len(matches) == 1
    assert matches[0] == sealed_file

    manifest = json.loads(sealed_file.read_text())
    assert manifest != stale
    assert set(manifest.keys()) == {
        "kind", "version", "component_id", "owners", "source_path",
        "source_hash", "verifier_version", "characterization", "written_at",
    }
    assert manifest["kind"] == "sealed-provenance"
    assert manifest["version"] == 1
    assert manifest["component_id"] == "comp-foo"
    assert manifest["owners"] == ["pipeline-team"]
    assert manifest["source_path"] == "pipeline/foo/"
    assert manifest["source_hash"] == source_hash
    assert manifest["verifier_version"] == "verifier-orchestrator@2.0.0"
    assert manifest["characterization"] == {
        "overall": "pass",
        "criteria_passed": 2,
        "criteria_total": 2,
    }
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", manifest["written_at"])
    written_at = datetime.strptime(manifest["written_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert before <= written_at <= after

    assert not (repo_root / "gen" / "foo" / ".provenance.json").exists()
    assert not (repo_root / "verification" / "foo" / ".provenance.json").exists()


def test_write_provenance_null_verification_report_when_no_files(tmp_path):
    cases = [
        ({}, {"refused": "sealed-component"}),
        (None, {"model_call_error": "api timeout"}),
    ]
    for index, (files_value, failure_kwargs) in enumerate(cases):
        repo_root = tmp_path / f"case{index}"
        repo_root.mkdir()

        generation_result = _generation_result(files=files_value, **failure_kwargs)
        inputs = _make_provenance_inputs(
            component_id="comp-foo",
            generation_result=generation_result,
            verification_report=None,
            license_scan_result=_license_scan_result(),
            secret_scan_result=_secret_scan_result(),
            provenance_hit=False,
            attempts=1,
            gate_versions={},
        )

        provenance_writer.write_provenance("comp-foo", inputs, repo_root)

        gen_file = repo_root / "gen" / "foo" / ".provenance.json"
        verif_file = repo_root / "verification" / "foo" / ".provenance.json"
        assert gen_file.exists()
        assert verif_file.exists()

        gen_manifest = json.loads(gen_file.read_text())
        verif_manifest = json.loads(verif_file.read_text())
        assert gen_manifest == verif_manifest
        assert _get(gen_manifest, "verification_report") is None


def test_write_provenance_missing_verification_report_raises_and_writes_nothing(tmp_path):
    missing_error = getattr(provenance_writer, "MissingInputError")

    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    generation_result = _generation_result(files={"foo.py": "print(1)"})
    inputs = _make_provenance_inputs(
        component_id="comp-foo",
        generation_result=generation_result,
        verification_report=None,
        license_scan_result=_license_scan_result(),
        secret_scan_result=_secret_scan_result(),
        provenance_hit=False,
        attempts=1,
        gate_versions={},
    )

    with pytest.raises(missing_error):
        provenance_writer.write_provenance("comp-foo", inputs, empty_root)

    assert not (empty_root / "gen" / "foo" / ".provenance.json").exists()
    assert not (empty_root / "verification" / "foo" / ".provenance.json").exists()

    stale_root = tmp_path / "stale"
    gen_dir = stale_root / "gen" / "foo"
    verif_dir = stale_root / "verification" / "foo"
    gen_dir.mkdir(parents=True)
    verif_dir.mkdir(parents=True)
    stale = {"stale": True}
    gen_file = gen_dir / ".provenance.json"
    verif_file = verif_dir / ".provenance.json"
    gen_file.write_text(json.dumps(stale))
    verif_file.write_text(json.dumps(stale))

    inputs2 = _make_provenance_inputs(
        component_id="comp-foo",
        generation_result=generation_result,
        verification_report=None,
        license_scan_result=_license_scan_result(),
        secret_scan_result=_secret_scan_result(),
        provenance_hit=False,
        attempts=1,
        gate_versions={},
    )

    with pytest.raises(missing_error):
        provenance_writer.write_provenance("comp-foo", inputs2, stale_root)

    assert json.loads(gen_file.read_text()) == stale
    assert json.loads(verif_file.read_text()) == stale