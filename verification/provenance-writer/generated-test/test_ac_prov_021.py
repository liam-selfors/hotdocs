"""AC-PROV-021 (Covers: R-PROV-010).

The provenance manifest is written identically to both
gen/<slug>/.provenance.json and verification/<slug>/.provenance.json,
replacing (never merging with) any stale content. The sealed manifest is
replaced in place with no second file created. A null verification report
is recorded as null only when nothing was generated; a null report
alongside generated files raises MissingInputError and writes nothing.
"""

import json
import os
import re
from pathlib import Path

import pytest

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"
STALE_MARKER = "STALE-MARKER-ac-prov-021"


# ---------------------------------------------------------------- helpers

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def gen_path(repo_root):
    return Path(repo_root) / "gen" / SLUG / ".provenance.json"


def ver_path(repo_root):
    return Path(repo_root) / "verification" / SLUG / ".provenance.json"


def sealed_path(repo_root):
    return Path(repo_root) / "pipeline" / SLUG / ".sealed-provenance.json"


def all_files(root):
    out = set()
    for dirpath, _dirnames, filenames in os.walk(str(root)):
        for name in filenames:
            full = Path(dirpath) / name
            out.add(full.relative_to(root).as_posix())
    return out


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def make_generation_result(files, refused=None):
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "1" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": files,
        "model_call_error": None,
        "refused": refused,
        "retry_feedback": None,
    }


def make_verification_report(overall="pass"):
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": overall,
    }


def make_license_scan_result():
    return {
        "component_id": COMPONENT_ID,
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


def make_secret_scan_result():
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


def make_inputs(generation_result, verification_report):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": make_license_scan_result(),
        "secret_scan_result": make_secret_scan_result(),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def stale_manifest():
    return {
        "spec_bundle_hash": "sha256:" + "9" * 64,
        "model_pin": "stale-model",
        "prompt_version": "v0",
        "retry_feedback": ["R-STALE-001"],
        "pipeline_version": "v0",
        "gate_versions": {"compiler": "0.0.1"},
        "provenance_hit": True,
        "generated_at": "2000-01-01T00:00:00Z",
        "verification_run_id": "run-stale",
        "verification_report": {
            "component_id": "comp-stale",
            "criteria": [],
            "requirement_results": {},
            "interface_drift": True,
            "mutation_score": 0.0,
            "overall": "fail",
        },
        "license_scan": {"component_id": "comp-stale"},
        "secret_scan": {"scope": "stale"},
        "stale_marker": STALE_MARKER,
    }


def read_both(repo_root):
    g, v = gen_path(repo_root), ver_path(repo_root)
    assert g.is_file(), "gen/<slug>/.provenance.json was not written"
    assert v.is_file(), "verification/<slug>/.provenance.json was not written"
    g_bytes, v_bytes = g.read_bytes(), v.read_bytes()
    g_obj = json.loads(g_bytes.decode("utf-8"))
    v_obj = json.loads(v_bytes.decode("utf-8"))
    return g_bytes, v_bytes, g_obj, v_obj


# ---------------------------------------------------- scenario 1: overwrite

def test_write_provenance_replaces_stale_content_in_both_copies(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    stale = stale_manifest()
    write_json(gen_path(repo_root), stale)
    write_json(ver_path(repo_root), stale)

    new_report = make_verification_report()
    inputs = make_inputs(make_generation_result({"foo.py": "def bar():\n    return 1\n"}), new_report)

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    g_bytes, v_bytes, g_obj, v_obj = read_both(repo_root)

    # Two copies of one logical artifact: identical.
    assert g_obj == v_obj
    assert g_bytes == v_bytes

    # Nothing stale survives (overwritten, never merged).
    assert isinstance(g_obj, dict)
    assert "stale_marker" not in g_obj
    assert STALE_MARKER.encode("utf-8") not in g_bytes
    assert STALE_MARKER.encode("utf-8") not in v_bytes
    assert b"comp-stale" not in g_bytes
    assert b"run-stale" not in g_bytes

    # The content reflects the new inputs.
    assert g_obj["verification_report"] == new_report
    assert g_obj["license_scan"] == make_license_scan_result()
    assert g_obj["secret_scan"] == make_secret_scan_result()
    assert g_obj["provenance_hit"] is False

    # Exactly the new manifest: same shape as a fresh write of the same inputs.
    fresh_root = tmp_path / "fresh"
    fresh_root.mkdir()
    provenance_writer.write_provenance(
        COMPONENT_ID,
        make_inputs(make_generation_result({"foo.py": "def bar():\n    return 1\n"}), make_verification_report()),
        fresh_root,
    )
    _, _, fresh_obj, _ = read_both(fresh_root)
    assert set(g_obj.keys()) == set(fresh_obj.keys())
    for key in fresh_obj:
        if key in ("generated_at", "verification_run_id"):
            continue
        assert g_obj[key] == fresh_obj[key], key


# --------------------------------------------- scenario 2: sealed overwrite

SEALED_KEYS = {
    "kind", "version", "component_id", "owners", "source_path", "source_hash",
    "verifier_version", "characterization", "written_at",
}


def test_write_sealed_provenance_replaces_stale_content_without_second_file(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    stale = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-stale",
        "owners": ["stale-team"],
        "source_path": "pipeline/foo/",
        "source_hash": "sha256:" + "f" * 64,
        "verifier_version": "verifier-orchestrator@1.0.0",
        "characterization": {"overall": "fail", "criteria_passed": 0, "criteria_total": 7},
        "written_at": "2000-01-01T00:00:00Z",
        "stale_marker": STALE_MARKER,
    }
    write_json(sealed_path(repo_root), stale)
    before = all_files(repo_root)

    new_hash = "sha256:" + "0123456789abcdef" * 4
    report = {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-003", "covers": "R-FOO-003", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass", "R-FOO-003": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "overall": "pass",
    }
    inputs = provenance_writer.SealedProvenanceInputs(
        component_id=COMPONENT_ID,
        owners=["pipeline-team"],
        source_path="pipeline/foo/",
        source_hash=new_hash,
        verifier_version="verifier-orchestrator@2.0.0",
        verification_report=report,
    )

    provenance_writer.write_sealed_provenance(COMPONENT_ID, inputs, repo_root)

    path = sealed_path(repo_root)
    assert path.is_file()
    raw = path.read_bytes()
    assert STALE_MARKER.encode("utf-8") not in raw
    manifest = json.loads(raw.decode("utf-8"))

    assert isinstance(manifest, dict)
    assert set(manifest.keys()) == SEALED_KEYS
    assert manifest["kind"] == "sealed-provenance"
    assert manifest["version"] == 1 and manifest["version"] is not True
    assert manifest["component_id"] == COMPONENT_ID
    assert manifest["owners"] == ["pipeline-team"]
    assert manifest["source_path"].rstrip("/") == "pipeline/foo"
    assert manifest["source_hash"] == new_hash
    assert manifest["verifier_version"] == "verifier-orchestrator@2.0.0"
    assert manifest["characterization"] == {
        "overall": "pass", "criteria_passed": 3, "criteria_total": 3,
    }
    assert re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", manifest["written_at"])
    assert manifest["written_at"] != "2000-01-01T00:00:00Z"

    # No second file anywhere: the file set is unchanged.
    assert all_files(repo_root) == before


# ------------------------------------- scenario 3: nothing generated -> null

@pytest.mark.parametrize("files", [{}, None], ids=["files-empty", "files-none"])
def test_no_files_and_null_report_writes_null_verification_report(tmp_path, files):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = make_inputs(make_generation_result(files, refused="pinned-override"), None)

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    g_bytes, v_bytes, g_obj, v_obj = read_both(repo_root)
    assert g_obj == v_obj
    assert g_bytes == v_bytes
    assert "verification_report" in g_obj
    assert g_obj["verification_report"] is None
    assert v_obj["verification_report"] is None


# ------------------------- scenario 4: files but null report -> MissingInput

def test_files_with_null_report_raises_and_writes_nothing_fresh_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    missing_error = getattr(provenance_writer, "MissingInputError")
    inputs = make_inputs(make_generation_result({"foo.py": "def bar():\n    return 1\n"}), None)

    with pytest.raises(missing_error):
        provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    assert not gen_path(repo_root).exists()
    assert not ver_path(repo_root).exists()
    assert all_files(repo_root) == set()


def test_files_with_null_report_raises_and_leaves_existing_files_untouched(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    stale = stale_manifest()
    write_json(gen_path(repo_root), stale)
    write_json(ver_path(repo_root), stale)
    g_before = gen_path(repo_root).read_bytes()
    v_before = ver_path(repo_root).read_bytes()
    files_before = all_files(repo_root)

    missing_error = getattr(provenance_writer, "MissingInputError")
    inputs = make_inputs(make_generation_result({"foo.py": "def bar():\n    return 1\n"}), None)

    with pytest.raises(missing_error):
        provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    assert gen_path(repo_root).read_bytes() == g_before
    assert ver_path(repo_root).read_bytes() == v_before
    assert all_files(repo_root) == files_before