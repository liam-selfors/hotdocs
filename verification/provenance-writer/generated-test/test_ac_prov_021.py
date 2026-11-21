# hotdocs-criterion: sha256:0be47eb489c559c489c5577b58a7ca44fb56ee3bb444352effb25e801dfdf9c1
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

import provenance_writer


STALE_MARKER = "STALE-CONTENT-MARKER"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def stale_text():
    # Long stale content, so a write that does not fully replace the file
    # would leave trailing garbage and fail to parse.
    doc = {
        "stale": True,
        "marker": STALE_MARKER,
        "padding": ["x" * 200 for _ in range(50)],
        "verification_run_id": "foo-attempt-999",
        "attempts": 999,
    }
    return json.dumps(doc, indent=2) + "\n"


def all_files(root):
    found = set()
    for dirpath, _dirnames, filenames in os.walk(str(root)):
        for name in filenames:
            full = Path(dirpath) / name
            found.add(full.relative_to(root).as_posix())
    return found


def make_generation_result(files):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": files,
        "model_call_error": None,
        "refused": None,
        "retry_feedback": ["R-FOO-003"],
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def make_verification_report():
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
                "adapter_sha256": "sha256:" + "b" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "pass",
    }


def make_license_scan():
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


def make_secret_scan():
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


def make_inputs(files, verification_report, attempts=3, provenance_hit=True):
    return {
        "component_id": "comp-foo",
        "generation_result": make_generation_result(files),
        "verification_report": verification_report,
        "license_scan_result": make_license_scan(),
        "secret_scan_result": make_secret_scan(),
        "provenance_hit": provenance_hit,
        "attempts": attempts,
        "attempt_history": [
            {"number": 1, "outcome": "passed", "retry_feedback": [],
             "error_category": None, "failed_requirements": [],
             "transcript_sha256": None},
        ],
        "gate_versions": {"compiler": "9.9.9", "license_scanner": "k-gram@2.0.0"},
    }


def manifest_paths(repo_root):
    return (
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    )


def test_stale_provenance_files_are_fully_replaced_and_identical(tmp_path):
    repo_root = tmp_path / "repo"
    gen_path, ver_path = manifest_paths(repo_root)
    gen_path.parent.mkdir(parents=True)
    ver_path.parent.mkdir(parents=True)
    gen_path.write_text(stale_text(), encoding="utf-8")
    ver_path.write_text(stale_text() + "different-stale\n", encoding="utf-8")

    report = make_verification_report()
    inputs = make_inputs({"foo.py": "x = 1\n"}, report, attempts=3, provenance_hit=True)

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    gen_bytes = gen_path.read_bytes()
    ver_bytes = ver_path.read_bytes()
    assert gen_bytes == ver_bytes, "the two provenance copies diverged"
    assert STALE_MARKER.encode() not in gen_bytes

    for path in (gen_path, ver_path):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(manifest, dict)
        assert "stale" not in manifest
        assert "marker" not in manifest
        assert "padding" not in manifest
        assert manifest["attempts"] == 3
        assert manifest["provenance_hit"] is True
        assert manifest["verification_run_id"] == "foo-attempt-3"
        assert manifest["gate_versions"] == {"compiler": "9.9.9", "license_scanner": "k-gram@2.0.0"}
        assert manifest["spec_bundle_hash"] == "sha256:" + "a" * 64
        assert manifest["model_pin"] == "claude-sonnet-5"
        assert manifest["verification_report"] == report
        assert manifest["license_scan"] == make_license_scan()
        assert manifest["secret_scan"] == make_secret_scan()
        assert manifest["assets"] == report["assets"]


def test_stale_sealed_provenance_is_replaced_without_second_file(tmp_path):
    repo_root = tmp_path / "repo"
    sealed_path = repo_root / "pipeline" / "foo" / ".sealed-provenance.json"
    sealed_path.parent.mkdir(parents=True)
    sealed_path.write_text(stale_text(), encoding="utf-8")
    before_files = all_files(repo_root)
    assert before_files == {"pipeline/foo/.sealed-provenance.json"}

    report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
    }
    source_hash = "sha256:" + "c" * 64
    inputs = {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": source_hash,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": report,
    }

    before = datetime.now(timezone.utc).replace(microsecond=0)
    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)
    after = datetime.now(timezone.utc).replace(microsecond=0)

    assert all_files(repo_root) == before_files, "a second file was created"

    text = sealed_path.read_text(encoding="utf-8")
    assert STALE_MARKER not in text
    manifest = json.loads(text)
    assert isinstance(manifest, dict)
    assert set(manifest.keys()) == {
        "kind", "version", "component_id", "owners", "source_path",
        "source_hash", "verifier_version", "characterization", "written_at",
    }
    assert manifest["kind"] == "sealed-provenance"
    assert manifest["version"] == 1 and manifest["version"] is not True
    assert manifest["component_id"] == "comp-foo"
    assert manifest["owners"] == ["pipeline-team"]
    assert manifest["source_path"] == "pipeline/foo/"
    assert manifest["source_hash"] == source_hash
    assert manifest["verifier_version"] == "verifier-orchestrator@2.0.0"
    assert manifest["characterization"] == {
        "overall": "pass", "criteria_passed": 2, "criteria_total": 2,
    }
    written_at = manifest["written_at"]
    assert re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", written_at)
    stamp = datetime.strptime(written_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert before <= stamp <= after


@pytest.mark.parametrize("files", [{}, None])
def test_no_files_and_null_report_writes_null_verification_report(tmp_path, files):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = make_inputs(files, None, attempts=1, provenance_hit=False)

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    gen_path, ver_path = manifest_paths(repo_root)
    assert gen_path.read_bytes() == ver_path.read_bytes()
    for path in (gen_path, ver_path):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert "verification_report" in manifest
        assert manifest["verification_report"] is None
        assert manifest["verification_run_id"] == "foo-attempt-1"
        assert manifest["assets"] == []


def test_files_with_null_report_raises_and_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = make_inputs({"foo.py": "x = 1\n"}, None)

    with pytest.raises(provenance_writer.MissingInputError):
        provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    gen_path, ver_path = manifest_paths(repo_root)
    assert not gen_path.exists()
    assert not ver_path.exists()
    assert all_files(repo_root) == set()