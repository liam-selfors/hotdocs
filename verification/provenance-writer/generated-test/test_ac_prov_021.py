# hotdocs-criterion: sha256:63522218fffd500d41a08ea504965bd2b978e18dcb35edc1d9befa0ced36962d
import json
import re
from pathlib import Path

import pytest

import provenance_writer


MANIFEST_KEYS = {
    "spec_bundle_hash",
    "spec_bundle_parts",
    "model_pin",
    "prompt_version",
    "retry_feedback",
    "generation",
    "attempts",
    "attempt_history",
    "pipeline_version",
    "gate_versions",
    "provenance_hit",
    "generated_at",
    "verification_run_id",
    "verification_report",
    "license_scan",
    "secret_scan",
    "assets",
    "drivers",
}

SEALED_KEYS = {
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def all_files(root):
    return sorted(p.relative_to(root).as_posix() for p in Path(root).rglob("*") if p.is_file())


def stale_text(marker):
    stale = {
        "stale_marker": marker,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "attempts": 99,
        "verification_run_id": "foo-attempt-99",
        "padding": "z" * 5000,
    }
    return json.dumps(stale, indent=2) + "\n"


def new_verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
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


def new_inputs():
    return {
        "component_id": "comp-foo",
        "generation_result": {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + "b" * 64,
            "model": "claude-new-model",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {"foo.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification_report": new_verification_report(),
        "license_scan_result": {"component_id": "comp-foo", "evaluated": False,
                                "reason": "no-reference-corpus", "blocked": False},
        "secret_scan_result": {"scope": "full", "flagged": False, "matches": []},
        "provenance_hit": False,
        "attempts": 3,
        "gate_versions": {"compiler": "2.0.0", "license_scanner": "k-gram@2.0.0"},
    }


def test_write_provenance_overwrites_both_stale_copies_identically(tmp_path):
    repo_root = tmp_path / "repo"
    gen_file = repo_root / "gen" / "foo" / ".provenance.json"
    ver_file = repo_root / "verification" / "foo" / ".provenance.json"
    gen_file.parent.mkdir(parents=True)
    ver_file.parent.mkdir(parents=True)
    gen_file.write_text(stale_text("stale-gen"), encoding="utf-8")
    ver_file.write_text(stale_text("stale-verification"), encoding="utf-8")

    inputs = new_inputs()
    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    gen_bytes = gen_file.read_bytes()
    ver_bytes = ver_file.read_bytes()
    assert gen_bytes == ver_bytes, "the two provenance copies diverge"

    for raw in (gen_bytes, ver_bytes):
        text = raw.decode("utf-8")
        assert "stale" not in text
        manifest = json.loads(text)
        assert isinstance(manifest, dict)
        assert set(manifest.keys()) == MANIFEST_KEYS
        assert manifest["spec_bundle_hash"] == "sha256:" + "b" * 64
        assert manifest["model_pin"] == "claude-new-model"
        assert manifest["prompt_version"] == "v12"
        assert manifest["attempts"] == 3
        assert manifest["verification_run_id"] == "foo-attempt-3"
        assert manifest["gate_versions"] == {"compiler": "2.0.0", "license_scanner": "k-gram@2.0.0"}
        assert manifest["provenance_hit"] is False
        assert manifest["verification_report"] == new_verification_report()
        assert manifest["license_scan"] == inputs["license_scan_result"]
        assert manifest["secret_scan"] == inputs["secret_scan_result"]
        assert manifest["assets"] == new_verification_report()["assets"]
        assert re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$",
                        manifest["generated_at"])


def sealed_report():
    return {
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
        "drivers": [],
        "overall": "pass",
    }


def test_write_sealed_provenance_overwrites_stale_single_file(tmp_path):
    repo_root = tmp_path / "repo"
    sealed_file = repo_root / "pipeline" / "foo" / ".sealed-provenance.json"
    sealed_file.parent.mkdir(parents=True)
    stale = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-foo",
        "owners": ["old-team"],
        "source_path": "pipeline/foo/",
        "source_hash": "sha256:" + "0" * 64,
        "verifier_version": "verifier-orchestrator@1.0.0",
        "characterization": {"overall": "fail", "criteria_passed": 1, "criteria_total": 7},
        "written_at": "2000-01-01T00:00:00Z",
        "padding": "z" * 5000,
    }
    sealed_file.write_text(json.dumps(stale, indent=2) + "\n", encoding="utf-8")

    new_hash = "sha256:" + "c" * 64
    inputs = {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": new_hash,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": sealed_report(),
    }
    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    text = sealed_file.read_text(encoding="utf-8")
    assert "old-team" not in text
    assert "padding" not in text
    manifest = json.loads(text)
    assert isinstance(manifest, dict)
    assert set(manifest.keys()) == SEALED_KEYS
    assert manifest["kind"] == "sealed-provenance"
    assert manifest["version"] == 1 and manifest["version"] is not True
    assert manifest["component_id"] == "comp-foo"
    assert manifest["owners"] == ["pipeline-team"]
    assert manifest["source_path"] == "pipeline/foo/"
    assert manifest["source_hash"] == new_hash
    assert manifest["verifier_version"] == "verifier-orchestrator@2.0.0"
    assert manifest["characterization"] == {
        "overall": "pass",
        "criteria_passed": 2,
        "criteria_total": 2,
    }
    assert re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$",
                    manifest["written_at"])

    assert all_files(repo_root) == ["pipeline/foo/.sealed-provenance.json"]


@pytest.mark.parametrize("files", [{}, None])
def test_no_files_and_no_report_writes_null_report(tmp_path, files):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = {
        "component_id": "comp-foo",
        "generation_result": {"files": files},
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {},
    }
    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    gen_file = repo_root / "gen" / "foo" / ".provenance.json"
    ver_file = repo_root / "verification" / "foo" / ".provenance.json"
    assert gen_file.is_file()
    assert ver_file.is_file()
    assert gen_file.read_bytes() == ver_file.read_bytes()
    for path in (gen_file, ver_file):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert "verification_report" in manifest
        assert manifest["verification_report"] is None


def test_files_present_without_report_raises_and_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = {
        "component_id": "comp-foo",
        "generation_result": {"files": {"foo.py": "x = 1\n"}},
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {},
    }
    with pytest.raises(provenance_writer.MissingInputError):
        provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    assert not (repo_root / "gen" / "foo" / ".provenance.json").exists()
    assert not (repo_root / "verification" / "foo" / ".provenance.json").exists()
    assert all_files(repo_root) == []