# hotdocs-criterion: sha256:948af14e4b3e7c8a296ca94e1f47434841a69e6dd67304afd2659fea0f55fee6
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
            "model_call_error": {"category": "network", "message": "down"},
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
    gen_path = Path(repo_root) / "gen" / "foo" / ".provenance.json"
    ver_path = Path(repo_root) / "verification" / "foo" / ".provenance.json"
    assert gen_path.is_file(), "missing " + str(gen_path)
    assert ver_path.is_file(), "missing " + str(ver_path)
    return (
        json.loads(gen_path.read_text(encoding="utf-8")),
        json.loads(ver_path.read_text(encoding="utf-8")),
    )


def test_verification_run_id_is_deterministic_slug_attempt(tmp_path):
    root_a = tmp_path / "a"
    root_a.mkdir()
    provenance_writer.write_provenance("comp-foo", make_inputs(), root_a)
    gen_a, ver_a = read_manifests(root_a)

    assert field(gen_a, "verification_run_id") == "foo-attempt-2"
    assert field(ver_a, "verification_run_id") == "foo-attempt-2"

    root_b = tmp_path / "b"
    root_b.mkdir()
    provenance_writer.write_provenance("comp-foo", make_inputs(), root_b)
    gen_b, ver_b = read_manifests(root_b)

    assert field(gen_b, "verification_run_id") == field(gen_a, "verification_run_id")
    assert field(ver_b, "verification_run_id") == field(ver_a, "verification_run_id")
    assert field(gen_b, "verification_run_id") == "foo-attempt-2"


def test_verification_run_id_identical_on_rewrite_same_root(tmp_path):
    provenance_writer.write_provenance("comp-foo", make_inputs(), tmp_path)
    first, _ = read_manifests(tmp_path)
    provenance_writer.write_provenance("comp-foo", make_inputs(), tmp_path)
    second, _ = read_manifests(tmp_path)

    assert field(first, "verification_run_id") == "foo-attempt-2"
    assert field(second, "verification_run_id") == field(first, "verification_run_id")