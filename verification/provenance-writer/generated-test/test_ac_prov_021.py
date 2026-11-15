import json
import os
import re
from pathlib import Path

import pytest

import provenance_writer


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class AttrDict(dict):
    """A plain dict that also reads as an object with attributes and a
    ``to_dict()``, so it works whichever access style the target uses."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def to_dict(self):
        return json.loads(json.dumps(self))


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def snapshot(root: Path):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            p = Path(dirpath) / fn
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


NEW_SPEC_HASH = "sha256:" + "a" * 64
STALE_SPEC_HASH = "sha256:" + "e" * 64
PADDING = "x" * 20000  # stale files are much longer than any new manifest


def make_generation_result(files, *, model_call_error=None, refused=None):
    return AttrDict(
        component_id="comp-foo",
        spec_bundle_hash=NEW_SPEC_HASH,
        model="claude-sonnet-5",
        prompt_version="v10",
        cache_hit=False,
        files=files,
        model_call_error=model_call_error,
        refused=refused,
        retry_feedback=None,
    )


def make_verification_report():
    return AttrDict(
        component_id="comp-foo",
        criteria=[
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-003", "covers": "R-FOO-003", "kind": "compiled", "result": "pass"},
        ],
        requirement_results={"R-FOO-001": "pass", "R-FOO-002": "pass", "R-FOO-003": "pass"},
        interface_drift=False,
        mutation_score=0.9,
        overall="pass",
    )


def make_license_scan():
    return AttrDict(
        component_id="comp-foo",
        gate_version="license_scanner@4.0.0-no-reference-corpus",
        evaluated=False,
        reason="no-reference-corpus",
        similarity_score=None,
        block_threshold=None,
        blocked=False,
        matches=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def make_secret_scan():
    return AttrDict(
        scope="full",
        gate_version="secret_scanner@3.1.0+detect-secrets.1.5.0",
        flagged=False,
        matches=[],
        allowed=[],
        unused_allowlist_entries=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def make_inputs(generation_result, verification_report):
    return AttrDict(
        component_id="comp-foo",
        generation_result=generation_result,
        verification_report=verification_report,
        license_scan_result=make_license_scan(),
        secret_scan_result=make_secret_scan(),
        provenance_hit=False,
        attempts=2,
        gate_versions={"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    )


def manifest_paths(repo_root: Path):
    return (
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    )


VOLATILE = {"generated_at", "verification_run_id"}


# ---------------------------------------------------------------------------
# Scenario 1: stale .provenance.json copies are fully replaced
# ---------------------------------------------------------------------------

def test_write_provenance_overwrites_stale_copies_with_identical_new_manifest(tmp_path):
    repo = tmp_path / "repo"
    fresh = tmp_path / "fresh"
    repo.mkdir()
    fresh.mkdir()

    stale_doc = {
        "stale_marker": True,
        "spec_bundle_hash": STALE_SPEC_HASH,
        "provenance_hit": True,
        "verification_report": {"overall": "fail", "stale": True},
        "padding": PADDING,
    }
    stale_text = json.dumps(stale_doc, indent=2)
    gen_path, ver_path = manifest_paths(repo)
    for p in (gen_path, ver_path):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(stale_text, encoding="utf-8")

    inputs = make_inputs(
        make_generation_result({"foo.py": "def bar():\n    return 1\n"}),
        make_verification_report(),
    )

    provenance_writer.write_provenance("comp-foo", inputs, repo)

    gen_bytes = gen_path.read_bytes()
    ver_bytes = ver_path.read_bytes()
    # Two copies of one logical artifact: byte-identical.
    assert gen_bytes == ver_bytes

    gen_manifest = json.loads(gen_bytes.decode("utf-8"))  # fails on leftover stale tail
    ver_manifest = json.loads(ver_bytes.decode("utf-8"))
    assert gen_manifest == ver_manifest
    assert isinstance(gen_manifest, dict)

    # Nothing of the stale content survives.
    assert "stale_marker" not in gen_manifest
    assert "padding" not in gen_manifest
    assert gen_manifest.get("spec_bundle_hash") != STALE_SPEC_HASH
    assert gen_manifest.get("provenance_hit") is False
    assert PADDING not in gen_bytes.decode("utf-8")

    # "Exactly the new manifest": same shape and content as a write of the
    # same inputs into a clean repo (ignoring per-run volatile fields).
    provenance_writer.write_provenance("comp-foo", inputs, fresh)
    fresh_gen, fresh_ver = manifest_paths(fresh)
    fresh_manifest = json.loads(fresh_gen.read_text(encoding="utf-8"))
    assert json.loads(fresh_ver.read_text(encoding="utf-8")) == fresh_manifest

    assert set(gen_manifest.keys()) == set(fresh_manifest.keys())
    for key in fresh_manifest:
        if key in VOLATILE:
            continue
        assert gen_manifest[key] == fresh_manifest[key], key

    assert gen_manifest.get("verification_report") is not None


# ---------------------------------------------------------------------------
# Scenario 2: stale .sealed-provenance.json is fully replaced, no extra file
# ---------------------------------------------------------------------------

SEALED_KEYS = {
    "kind", "version", "component_id", "owners", "source_path",
    "source_hash", "verifier_version", "characterization", "written_at",
}


def test_write_sealed_provenance_overwrites_stale_file_and_creates_no_second_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    sealed_dir = repo / "pipeline" / "foo"
    sealed_dir.mkdir(parents=True)
    sealed_path = sealed_dir / ".sealed-provenance.json"

    stale_doc = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-stale",
        "owners": ["stale-team"],
        "source_path": "pipeline/foo/",
        "source_hash": "sha256:" + "e" * 64,
        "verifier_version": "verifier-orchestrator@0.0.1",
        "characterization": {"overall": "fail", "criteria_passed": 0, "criteria_total": 9},
        "written_at": "2000-01-01T00:00:00Z",
        "padding": PADDING,
    }
    sealed_path.write_text(json.dumps(stale_doc, indent=2), encoding="utf-8")

    before = snapshot(repo)

    new_hash = "sha256:" + "0123456789abcdef" * 4
    inputs = {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": new_hash,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": make_verification_report(),
    }

    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo)

    text = sealed_path.read_text(encoding="utf-8")
    assert PADDING not in text
    manifest = json.loads(text)
    assert isinstance(manifest, dict)
    assert set(manifest.keys()) == SEALED_KEYS
    assert manifest["kind"] == "sealed-provenance"
    assert manifest["version"] == 1 and manifest["version"] is not True
    assert manifest["component_id"] == "comp-foo"
    assert manifest["owners"] == ["pipeline-team"]
    assert manifest["source_path"].rstrip("/") == "pipeline/foo"
    assert manifest["source_hash"] == new_hash
    assert manifest["verifier_version"] == "verifier-orchestrator@2.0.0"
    assert manifest["characterization"] == {
        "overall": "pass", "criteria_passed": 3, "criteria_total": 3,
    }
    assert re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", manifest["written_at"]
    )
    assert manifest["written_at"] != "2000-01-01T00:00:00Z"

    # No second file was created anywhere: same file set as before.
    after = snapshot(repo)
    assert set(after.keys()) == set(before.keys())
    assert sorted(os.listdir(sealed_dir)) == [".sealed-provenance.json"]


# ---------------------------------------------------------------------------
# Scenario 3: no files and no report -> manifest with null verification_report
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("files", [{}, None])
def test_write_provenance_with_no_files_and_no_report_writes_null_report(tmp_path, files):
    repo = tmp_path / "repo"
    repo.mkdir()

    inputs = make_inputs(
        make_generation_result(files, refused="sealed-component"),
        None,
    )

    provenance_writer.write_provenance("comp-foo", inputs, repo)

    gen_path, ver_path = manifest_paths(repo)
    assert gen_path.is_file()
    assert ver_path.is_file()
    assert gen_path.read_bytes() == ver_path.read_bytes()

    for p in (gen_path, ver_path):
        manifest = json.loads(p.read_text(encoding="utf-8"))
        assert isinstance(manifest, dict)
        assert "verification_report" in manifest
        assert manifest["verification_report"] is None


# ---------------------------------------------------------------------------
# Scenario 4: files present but no report -> MissingInputError, nothing written
# ---------------------------------------------------------------------------

def test_write_provenance_with_files_but_no_report_raises_and_writes_nothing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    before = snapshot(repo)

    inputs = make_inputs(
        make_generation_result({"foo.py": "def bar():\n    return 1\n"}),
        None,
    )

    with pytest.raises(provenance_writer.MissingInputError):
        provenance_writer.write_provenance("comp-foo", inputs, repo)

    gen_path, ver_path = manifest_paths(repo)
    assert not gen_path.exists()
    assert not ver_path.exists()
    assert snapshot(repo) == before