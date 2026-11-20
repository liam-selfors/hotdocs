# hotdocs-criterion: sha256:054c961092aed10f36514cb0dd614effa78944e99889633faa173585ff2c721a
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


def read_manifests(repo_root):
    gen_path = Path(repo_root) / "gen" / "foo" / ".provenance.json"
    ver_path = Path(repo_root) / "verification" / "foo" / ".provenance.json"
    assert gen_path.is_file(), "missing " + str(gen_path)
    assert ver_path.is_file(), "missing " + str(ver_path)
    return (
        json.loads(gen_path.read_text(encoding="utf-8")),
        json.loads(ver_path.read_text(encoding="utf-8")),
    )


def test_ac_prov_013_verification_run_id_is_deterministic(tmp_path):
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()

    provenance_writer.write_provenance("comp-foo", make_inputs(), root_a)
    gen_a, ver_a = read_manifests(root_a)
    assert field(gen_a, "verification_run_id") == "foo-attempt-2"
    assert field(ver_a, "verification_run_id") == "foo-attempt-2"

    provenance_writer.write_provenance("comp-foo", make_inputs(), root_b)
    gen_b, ver_b = read_manifests(root_b)
    assert field(gen_b, "verification_run_id") == field(gen_a, "verification_run_id")
    assert field(ver_b, "verification_run_id") == field(ver_a, "verification_run_id")

    # Running again into the same repo_root also yields the identical id.
    provenance_writer.write_provenance("comp-foo", make_inputs(), root_a)
    gen_a2, ver_a2 = read_manifests(root_a)
    assert field(gen_a2, "verification_run_id") == "foo-attempt-2"
    assert field(ver_a2, "verification_run_id") == "foo-attempt-2"