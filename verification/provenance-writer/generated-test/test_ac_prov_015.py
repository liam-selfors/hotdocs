# hotdocs-criterion: sha256:c3d5709a7e21133facdf5bcca05c46331707f97f40c9f415ef9ee81b991ccbb8
import io
import json
import sys

import pytest

import provenance_writer


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
    }


def _generation_result():
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
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
    }


def _valid_doc():
    return {
        "component_id": "comp-foo",
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": {
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
        },
        "secret_scan_result": {
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
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {"compiler": "1.0.0"},
    }


def _set_stdin(monkeypatch, text):
    stream = io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stream)


def _manifests(root):
    return (
        root / "gen" / "foo" / ".provenance.json",
        root / "verification" / "foo" / ".provenance.json",
    )


def _all_files(root):
    return [p for p in root.rglob("*") if p.is_file()]


def test_valid_equals_form_returns_0_and_writes_both(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    _set_stdin(monkeypatch, json.dumps(_valid_doc()))
    rc = provenance_writer.main(["provenance", "write", "comp-foo", "--repo-root=" + str(repo)])
    assert rc == 0
    gen_file, ver_file = _manifests(repo)
    assert gen_file.is_file()
    assert ver_file.is_file()


def test_valid_space_form_returns_0_and_writes_both(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    _set_stdin(monkeypatch, json.dumps(_valid_doc()))
    rc = provenance_writer.main(["provenance", "write", "comp-foo", "--repo-root", str(repo)])
    assert rc == 0
    gen_file, ver_file = _manifests(repo)
    assert gen_file.is_file()
    assert ver_file.is_file()


def test_missing_license_scan_result_returns_1_and_writes_nothing(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    doc = _valid_doc()
    del doc["license_scan_result"]
    _set_stdin(monkeypatch, json.dumps(doc))
    rc = provenance_writer.main(["provenance", "write", "comp-foo", "--repo-root=" + str(repo)])
    assert rc == 1
    gen_file, ver_file = _manifests(repo)
    assert not gen_file.exists()
    assert not ver_file.exists()
    assert _all_files(repo) == []
    assert _all_files(cwd) == []


@pytest.mark.parametrize(
    "argv_tail",
    [
        [],
        ["comp-foo", "--bogus-flag"],
        ["comp-foo", "--repo-root"],
        ["comp-foo", "comp-bar"],
    ],
)
def test_usage_errors_return_2(tmp_path, monkeypatch, argv_tail):
    monkeypatch.chdir(tmp_path)
    _set_stdin(monkeypatch, json.dumps(_valid_doc()))
    rc = provenance_writer.main(["provenance", "write"] + argv_tail)
    assert rc == 2


def test_malformed_json_returns_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _set_stdin(monkeypatch, "{not valid json")
    rc = provenance_writer.main(["provenance", "write", "comp-foo"])
    assert rc == 2