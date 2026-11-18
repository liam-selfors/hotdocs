# hotdocs-criterion: sha256:cc8f26218217c9a73de2b41305d3ed14274349919c32f0fa6f033f6ee584cc92
import json
import os
import re
from pathlib import Path

import pytest

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


STALE_TEXT = json.dumps(
    {
        "spec_bundle_hash": "sha256:stalestalestale",
        "stale_marker": "old-content-must-vanish",
        "verification_report": {"stale": True},
    },
    sort_keys=True,
)


def _all_files(root):
    found = set()
    for dirpath, _dirnames, filenames in os.walk(str(root)):
        for name in filenames:
            full = Path(dirpath) / name
            found.add(full.relative_to(root).as_posix())
    return found


def _license_scan():
    return {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _secret_scan():
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


def _generation_result(files, model_call_error=None, refused=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": files,
        "model_call_error": model_call_error,
        "refused": refused,
        "retry_feedback": None,
    }


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "overall": "pass",
    }


def _inputs(generation_result, verification_report):
    return {
        "component_id": "comp-foo",
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": _license_scan(),
        "secret_scan_result": _secret_scan(),
        "provenance_hit": True,
        "attempts": 3,
        "gate_versions": {"compiler": "9.9.9", "license_scanner": "k-gram@7.7.7"},
    }


def _manifest_paths(repo_root):
    return (
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    )


def test_write_provenance_overwrites_both_stale_copies_identically(tmp_path):
    repo_root = tmp_path
    gen_path, ver_path = _manifest_paths(repo_root)
    for p in (gen_path, ver_path):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(STALE_TEXT, encoding="utf-8")

    report = _verification_report()
    inputs = _inputs(_generation_result({"foo.py": "x = 1\n"}), report)

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    assert gen_path.is_file()
    assert ver_path.is_file()
    gen_bytes = gen_path.read_bytes()
    ver_bytes = ver_path.read_bytes()
    assert gen_bytes == ver_bytes, "the two provenance copies diverged"

    text = gen_bytes.decode("utf-8")
    assert "old-content-must-vanish" not in text
    assert "sha256:stalestalestale" not in text

    manifest = json.loads(text)
    assert isinstance(manifest, dict)
    assert "stale_marker" not in manifest
    assert manifest.get("spec_bundle_hash") != "sha256:stalestalestale"
    assert manifest["provenance_hit"] is True
    assert manifest["gate_versions"] == inputs["gate_versions"]
    assert manifest["verification_report"] == report
    assert manifest["license_scan"] == _license_scan()
    assert manifest["secret_scan"] == _secret_scan()


def test_write_sealed_provenance_overwrites_stale_single_file(tmp_path):
    repo_root = tmp_path
    sealed_path = repo_root / "pipeline" / "foo" / ".sealed-provenance.json"
    sealed_path.parent.mkdir(parents=True, exist_ok=True)
    sealed_path.write_text(STALE_TEXT, encoding="utf-8")
    files_before = _all_files(repo_root)

    report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-003", "covers": "R-FOO-003", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass", "R-FOO-003": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "overall": "pass",
    }
    source_hash = "sha256:" + "0123456789abcdef" * 4
    inputs = {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": source_hash,
        "verifier_version": "verifier-orchestrator@2.2.0",
        "verification_report": report,
    }

    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    assert _all_files(repo_root) == files_before, "a second file was created"
    assert sorted(os.listdir(str(sealed_path.parent))) == [".sealed-provenance.json"]

    text = sealed_path.read_text(encoding="utf-8")
    assert "old-content-must-vanish" not in text
    manifest = json.loads(text)
    assert set(manifest) == {
        "kind",
        "version",
        "component_id",
        "owners",
        "source_path",
        "source_hash",
        "verifier_version",
        "characterization",
        "written_at",
    }
    assert manifest["kind"] == "sealed-provenance"
    assert manifest["version"] == 1 and manifest["version"] is not True
    assert manifest["component_id"] == "comp-foo"
    assert manifest["owners"] == ["pipeline-team"]
    assert manifest["source_path"] == "pipeline/foo/"
    assert manifest["source_hash"] == source_hash
    assert manifest["verifier_version"] == "verifier-orchestrator@2.2.0"
    assert manifest["characterization"] == {
        "overall": "pass",
        "criteria_passed": 3,
        "criteria_total": 3,
    }
    assert re.match(
        r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$",
        manifest["written_at"],
    )


@pytest.mark.parametrize(
    "generation_result",
    [
        _generation_result({}, refused="sealed-component"),
        _generation_result(
            None, model_call_error={"category": "network", "message": "down"}
        ),
    ],
    ids=["files-empty", "files-none"],
)
def test_write_provenance_without_candidate_writes_null_report(tmp_path, generation_result):
    repo_root = tmp_path
    inputs = _inputs(generation_result, None)

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    gen_path, ver_path = _manifest_paths(repo_root)
    assert gen_path.is_file()
    assert ver_path.is_file()
    assert gen_path.read_bytes() == ver_path.read_bytes()
    manifest = json.loads(gen_path.read_text(encoding="utf-8"))
    assert "verification_report" in manifest
    assert manifest["verification_report"] is None


def test_write_provenance_missing_report_with_files_raises_and_writes_nothing(tmp_path):
    repo_root = tmp_path
    assert hasattr(provenance_writer, "MissingInputError")
    inputs = _inputs(_generation_result({"foo.py": "x = 1\n"}), None)

    with pytest.raises(provenance_writer.MissingInputError):
        provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    gen_path, ver_path = _manifest_paths(repo_root)
    assert not gen_path.exists()
    assert not ver_path.exists()
    assert _all_files(repo_root) == set()