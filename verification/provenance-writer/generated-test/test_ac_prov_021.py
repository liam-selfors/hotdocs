# hotdocs-criterion: sha256:0091b78f7d7deda4c8e5da0a012cf2ec01b96b1a9cad834c016d624549f52caa
"""AC-PROV-021 (covers R-PROV-010): manifests are overwritten whole, written
identically to both locations, and a missing verification report for a
real candidate writes nothing."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

import provenance_writer


TS_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

STALE_PROVENANCE = json.dumps(
    {
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model_pin": "stale-model",
        "prompt_version": "v0",
        "retry_feedback": ["R-STALE-999"],
        "attempts": 99,
        "verification_run_id": "stale-run",
        "provenance_hit": True,
        "stale_marker": "this key must not survive the rewrite",
        "padding": "x" * 20000,
    },
    indent=2,
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def all_files(root):
    found = set()
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            found.add(Path(dirpath, name).relative_to(root).as_posix())
    return found


def now_s():
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_ts(text):
    assert TS_RE.match(text), text
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


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


def make_license():
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


def make_secret():
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


def make_inputs(files, report):
    return {
        "component_id": "comp-foo",
        "generation_result": make_generation_result(files),
        "verification_report": report,
        "license_scan_result": make_license(),
        "secret_scan_result": make_secret(),
        "provenance_hit": False,
        "attempts": 3,
        "attempt_history": [
            {
                "number": 1,
                "outcome": "passed",
                "retry_feedback": [],
                "error_category": None,
                "failed_requirements": [],
                "transcript_sha256": None,
            }
        ],
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def manifest_paths(repo_root):
    return (
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    )


def test_write_provenance_overwrites_both_stale_files_identically(tmp_path):
    gen_path, ver_path = manifest_paths(tmp_path)
    for p in (gen_path, ver_path):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(STALE_PROVENANCE, encoding="utf-8")

    report = make_verification_report()
    inputs = make_inputs({"foo.py": "x = 1\n"}, report)

    before = now_s()
    provenance_writer.write_provenance("comp-foo", inputs, tmp_path)
    after = now_s()

    gen_bytes = gen_path.read_bytes()
    ver_bytes = ver_path.read_bytes()
    assert gen_bytes == ver_bytes, "the two manifest copies diverge"

    for raw in (gen_bytes, ver_bytes):
        manifest = json.loads(raw.decode("utf-8"))  # whole file is one JSON doc
        assert isinstance(manifest, dict)
        assert "stale_marker" not in manifest
        assert "padding" not in manifest
        assert manifest["spec_bundle_hash"] == "sha256:" + "a" * 64
        assert manifest["model_pin"] == "claude-sonnet-5"
        assert manifest["prompt_version"] == "v12"
        assert manifest["retry_feedback"] == ["R-FOO-003"]
        assert manifest["attempts"] == 3
        assert manifest["provenance_hit"] is False
        assert manifest["verification_run_id"] == "foo-attempt-3"
        assert manifest["gate_versions"] == {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"}
        assert manifest["verification_report"] == report
        assert manifest["license_scan"] == make_license()
        assert manifest["secret_scan"] == make_secret()
        assert manifest["assets"] == report["assets"]
        assert manifest["attempt_history"] == inputs["attempt_history"]
        assert before <= parse_ts(manifest["generated_at"]) <= after


def test_write_sealed_provenance_overwrites_stale_file_and_creates_no_other(tmp_path):
    sealed_path = tmp_path / "pipeline" / "foo" / ".sealed-provenance.json"
    sealed_path.parent.mkdir(parents=True)
    sealed_path.write_text(
        json.dumps(
            {
                "kind": "sealed-provenance",
                "version": 1,
                "component_id": "comp-stale",
                "owners": ["stale-team"],
                "source_path": "pipeline/foo/",
                "source_hash": "sha256:" + "0" * 64,
                "verifier_version": "verifier-orchestrator@0.0.1",
                "characterization": {"overall": "fail", "criteria_passed": 0, "criteria_total": 9},
                "written_at": "2000-01-01T00:00:00Z",
                "stale_marker": "x" * 20000,
            }
        ),
        encoding="utf-8",
    )
    files_before = all_files(tmp_path)
    assert files_before == {"pipeline/foo/.sealed-provenance.json"}

    report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-003", "covers": "R-FOO-003", "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass", "R-FOO-003": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
    }
    inputs = {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": "sha256:" + "c" * 64,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": report,
    }

    before = now_s()
    provenance_writer.write_sealed_provenance("comp-foo", inputs, tmp_path)
    after = now_s()

    assert all_files(tmp_path) == files_before, "a second file was created"

    manifest = json.loads(sealed_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    written_at = manifest.get("written_at")
    assert isinstance(written_at, str)
    assert before <= parse_ts(written_at) <= after

    expected = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": "sha256:" + "c" * 64,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "characterization": {"overall": "pass", "criteria_passed": 3, "criteria_total": 3},
        "written_at": written_at,
    }
    assert manifest == expected
    assert type(manifest["version"]) is int
    assert type(manifest["characterization"]["criteria_passed"]) is int
    assert type(manifest["characterization"]["criteria_total"]) is int


@pytest.mark.parametrize("files", [{}, None])
def test_no_candidate_and_null_report_writes_null_verification_report(tmp_path, files):
    inputs = make_inputs(files, None)

    provenance_writer.write_provenance("comp-foo", inputs, tmp_path)

    gen_path, ver_path = manifest_paths(tmp_path)
    gen_bytes = gen_path.read_bytes()
    ver_bytes = ver_path.read_bytes()
    assert gen_bytes == ver_bytes
    for raw in (gen_bytes, ver_bytes):
        manifest = json.loads(raw.decode("utf-8"))
        assert "verification_report" in manifest
        assert manifest["verification_report"] is None
        assert manifest["assets"] == []


def test_candidate_with_null_report_raises_and_writes_nothing(tmp_path):
    inputs = make_inputs({"foo.py": "x = 1\n"}, None)

    with pytest.raises(provenance_writer.MissingInputError):
        provenance_writer.write_provenance("comp-foo", inputs, tmp_path)

    gen_path, ver_path = manifest_paths(tmp_path)
    assert not gen_path.exists()
    assert not ver_path.exists()
    assert all_files(tmp_path) == set()