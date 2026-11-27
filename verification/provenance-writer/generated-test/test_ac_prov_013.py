# hotdocs-criterion: sha256:5eb5c9e4a8b4ba95916a14ae76e6f2a6d4f3b9467bdae4e47d0557df9f49ccc7
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_inputs():
    return {
        "component_id": "comp-foo",
        "generation_result": {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {},
            "model_call_error": {"category": "network", "message": "boom"},
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 2,
        "attempt_history": [],
        "gate_versions": {},
    }


def read_manifests(repo_root):
    gen_path = repo_root / "gen" / "foo" / ".provenance.json"
    ver_path = repo_root / "verification" / "foo" / ".provenance.json"
    assert gen_path.is_file(), "missing " + str(gen_path)
    assert ver_path.is_file(), "missing " + str(ver_path)
    return (
        json.loads(gen_path.read_text(encoding="utf-8")),
        json.loads(ver_path.read_text(encoding="utf-8")),
    )


def test_ac_prov_013_verification_run_id_is_deterministic(tmp_path):
    root_one = tmp_path / "run1"
    root_two = tmp_path / "run2"
    root_one.mkdir()
    root_two.mkdir()

    provenance_writer.write_provenance("comp-foo", make_inputs(), root_one)
    gen_one, ver_one = read_manifests(root_one)

    assert field(gen_one, "verification_run_id") == "foo-attempt-2"
    assert field(ver_one, "verification_run_id") == "foo-attempt-2"

    provenance_writer.write_provenance("comp-foo", make_inputs(), root_two)
    gen_two, ver_two = read_manifests(root_two)

    assert field(gen_two, "verification_run_id") == field(gen_one, "verification_run_id")
    assert field(ver_two, "verification_run_id") == field(ver_one, "verification_run_id")
    assert field(gen_two, "verification_run_id") == "foo-attempt-2"


def test_ac_prov_013_same_root_rerun_identical_run_id(tmp_path):
    provenance_writer.write_provenance("comp-foo", make_inputs(), tmp_path)
    first_gen, _ = read_manifests(tmp_path)
    first_id = field(first_gen, "verification_run_id")

    provenance_writer.write_provenance("comp-foo", make_inputs(), tmp_path)
    second_gen, second_ver = read_manifests(tmp_path)

    assert first_id == "foo-attempt-2"
    assert field(second_gen, "verification_run_id") == first_id
    assert field(second_ver, "verification_run_id") == first_id