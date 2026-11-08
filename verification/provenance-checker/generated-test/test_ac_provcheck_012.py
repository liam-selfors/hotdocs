import json
import os
from pathlib import Path

import provenance_checker


def get_field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def snapshot(repo_root):
    state = {}
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            path = Path(root) / name
            rel = path.relative_to(repo_root)
            state[str(rel)] = path.read_bytes()
    return state


def build_base_repo(tmp_path):
    repo_root = tmp_path

    foo_dir = repo_root / "specs" / "components" / "foo"
    foo_dir.mkdir(parents=True)
    (foo_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team, alice]\n"
        "sealed: true\n"
        "source_path: pipeline/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A sealed fixture component for provenance-checker tests.\n"
    )

    bar_dir = repo_root / "specs" / "components" / "bar"
    bar_dir.mkdir(parents=True)
    (bar_dir / "component.md").write_text(
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Bar\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A non-sealed fixture component for provenance-checker tests.\n"
    )

    verifier_dir = repo_root / "gen" / "verifier-orchestrator"
    verifier_dir.mkdir(parents=True)
    (verifier_dir / "verifier_orchestrator.py").write_text(
        'GATE_VERSION = "verifier-orchestrator@2.0.0"\n'
    )

    source_dir = repo_root / "pipeline" / "foo"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text("def foo():\n    return 1\n")

    return repo_root


def current_source_hash(repo_root):
    key = provenance_checker.current_sealed_key("comp-foo", repo_root)
    return get_field(key, "source_hash")


def baseline_manifest(source_hash):
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-foo",
        "owners": ["pipeline-team", "alice"],
        "source_path": "pipeline/foo/",
        "source_hash": source_hash,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "characterization": {
            "overall": "pass",
            "criteria_passed": 2,
            "criteria_total": 2,
        },
        "written_at": "2026-11-02T00:00:00Z",
    }


def write_manifest_text(repo_root, text):
    manifest_dir = repo_root / "pipeline" / "foo"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / ".sealed-provenance.json"
    manifest_path.write_text(text)
    return manifest_path


def write_manifest(repo_root, data):
    return write_manifest_text(repo_root, json.dumps(data))


def call_checked(repo_root, component_id="comp-foo"):
    before = snapshot(repo_root)
    result = provenance_checker.check_sealed_provenance(component_id, repo_root)
    after = snapshot(repo_root)
    assert before == after
    return result


def assert_miss(result, reason):
    assert get_field(result, "reason") == reason
    assert get_field(result, "hit") is False
    assert get_field(result, "verification_report") is None
    assert get_field(result, "owners") is None
    assert get_field(result, "source_hash") is None
    assert get_field(result, "written_at") is None
    assert get_field(result, "license_scan") is None
    assert get_field(result, "secret_scan") is None


def test_valid_current_manifest_is_a_hit(tmp_path):
    repo_root = build_base_repo(tmp_path)
    source_hash = current_source_hash(repo_root)
    write_manifest(repo_root, baseline_manifest(source_hash))

    result = call_checked(repo_root)

    assert get_field(result, "hit") is True
    assert get_field(result, "reason") is None
    assert get_field(result, "sealed") is True
    assert get_field(result, "verification_report") == {"overall": "pass"}
    assert get_field(result, "owners") == ["pipeline-team", "alice"]
    assert get_field(result, "written_at") == "2026-11-02T00:00:00Z"
    assert get_field(result, "license_scan") is None
    assert get_field(result, "secret_scan") is None


def test_manifest_missing(tmp_path):
    repo_root = build_base_repo(tmp_path)

    result = call_checked(repo_root)

    assert_miss(result, "manifest_missing")


def test_manifest_invalid_not_json(tmp_path):
    repo_root = build_base_repo(tmp_path)
    write_manifest_text(repo_root, "this is not json at all")

    result = call_checked(repo_root)

    assert_miss(result, "manifest_invalid")


def test_manifest_invalid_extra_key(tmp_path):
    repo_root = build_base_repo(tmp_path)
    source_hash = current_source_hash(repo_root)
    manifest = baseline_manifest(source_hash)
    manifest["extra_field"] = "unexpected"
    write_manifest(repo_root, manifest)

    result = call_checked(repo_root)

    assert_miss(result, "manifest_invalid")


def test_manifest_invalid_missing_key(tmp_path):
    repo_root = build_base_repo(tmp_path)
    source_hash = current_source_hash(repo_root)
    manifest = baseline_manifest(source_hash)
    del manifest["written_at"]
    write_manifest(repo_root, manifest)

    result = call_checked(repo_root)

    assert_miss(result, "manifest_invalid")


def test_manifest_invalid_version_true(tmp_path):
    repo_root = build_base_repo(tmp_path)
    source_hash = current_source_hash(repo_root)
    manifest = baseline_manifest(source_hash)
    manifest["version"] = True
    write_manifest(repo_root, manifest)

    result = call_checked(repo_root)

    assert_miss(result, "manifest_invalid")


def test_manifest_invalid_bad_source_hash_format(tmp_path):
    repo_root = build_base_repo(tmp_path)
    manifest = baseline_manifest("sha256:abc")
    write_manifest(repo_root, manifest)

    result = call_checked(repo_root)

    assert_miss(result, "manifest_invalid")


def test_manifest_invalid_bad_owner_case(tmp_path):
    repo_root = build_base_repo(tmp_path)
    source_hash = current_source_hash(repo_root)
    manifest = baseline_manifest(source_hash)
    manifest["owners"] = ["Alice", "pipeline-team"]
    write_manifest(repo_root, manifest)

    result = call_checked(repo_root)

    assert_miss(result, "manifest_invalid")


def test_manifest_invalid_characterization_count_mismatch(tmp_path):
    repo_root = build_base_repo(tmp_path)
    source_hash = current_source_hash(repo_root)
    manifest = baseline_manifest(source_hash)
    manifest["characterization"] = {
        "overall": "pass",
        "criteria_passed": 1,
        "criteria_total": 2,
    }
    write_manifest(repo_root, manifest)

    result = call_checked(repo_root)

    assert_miss(result, "manifest_invalid")


def test_component_mismatch_component_id(tmp_path):
    repo_root = build_base_repo(tmp_path)
    source_hash = current_source_hash(repo_root)
    manifest = baseline_manifest(source_hash)
    manifest["component_id"] = "comp-bar"
    write_manifest(repo_root, manifest)

    result = call_checked(repo_root)

    assert_miss(result, "component_mismatch")


def test_component_mismatch_source_path(tmp_path):
    repo_root = build_base_repo(tmp_path)
    source_hash = current_source_hash(repo_root)
    manifest = baseline_manifest(source_hash)
    manifest["source_path"] = "pipeline/other/"
    write_manifest(repo_root, manifest)

    result = call_checked(repo_root)

    assert_miss(result, "component_mismatch")


def test_source_changed(tmp_path):
    repo_root = build_base_repo(tmp_path)
    manifest = baseline_manifest("sha256:" + "f" * 64)
    assert manifest["source_hash"] != current_source_hash(repo_root)
    write_manifest(repo_root, manifest)

    result = call_checked(repo_root)

    assert_miss(result, "source_changed")


def test_owners_changed_subset(tmp_path):
    repo_root = build_base_repo(tmp_path)
    source_hash = current_source_hash(repo_root)
    manifest = baseline_manifest(source_hash)
    manifest["owners"] = ["pipeline-team"]
    write_manifest(repo_root, manifest)

    result = call_checked(repo_root)

    assert_miss(result, "owners_changed")


def test_owners_changed_order(tmp_path):
    repo_root = build_base_repo(tmp_path)
    source_hash = current_source_hash(repo_root)
    manifest = baseline_manifest(source_hash)
    manifest["owners"] = ["alice", "pipeline-team"]
    write_manifest(repo_root, manifest)

    result = call_checked(repo_root)

    assert_miss(result, "owners_changed")


def test_verifier_changed(tmp_path):
    repo_root = build_base_repo(tmp_path)
    source_hash = current_source_hash(repo_root)
    manifest = baseline_manifest(source_hash)
    manifest["verifier_version"] = "verifier-orchestrator@1.0.0"
    write_manifest(repo_root, manifest)

    result = call_checked(repo_root)

    assert_miss(result, "verifier_changed")


def test_characterization_failed(tmp_path):
    repo_root = build_base_repo(tmp_path)
    source_hash = current_source_hash(repo_root)
    manifest = baseline_manifest(source_hash)
    manifest["characterization"] = {
        "overall": "fail",
        "criteria_passed": 1,
        "criteria_total": 2,
    }
    write_manifest(repo_root, manifest)

    result = call_checked(repo_root)

    assert_miss(result, "characterization_failed")


def test_not_sealed(tmp_path):
    repo_root = build_base_repo(tmp_path)

    result = call_checked(repo_root, component_id="comp-bar")

    assert_miss(result, "not_sealed")
    assert get_field(result, "sealed") is False