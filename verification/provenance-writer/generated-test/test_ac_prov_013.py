# hotdocs-criterion: sha256:97f29210e39508abbff9def5544970ac3e00feb860a6970b8251bedba3cbf61c
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    # No candidate produced (a model call error), so verification_report is
    # legitimately null and no upstream report is missing.
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {},
        "model_call_error": "simulated API failure",
        "refused": None,
        "retry_feedback": None,
    }


def _license_scan_result():
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


def _secret_scan_result():
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


def _inputs_fields():
    return {
        "component_id": "comp-foo",
        "generation_result": _generation_result(),
        "verification_report": None,
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 2,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def _make_inputs():
    fields = _inputs_fields()
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None:
        try:
            return cls(**fields)
        except TypeError:
            pass
    return fields


def _read_manifests(repo_root):
    gen_path = Path(repo_root) / "gen" / "foo" / ".provenance.json"
    ver_path = Path(repo_root) / "verification" / "foo" / ".provenance.json"
    assert gen_path.is_file(), "missing manifest at " + str(gen_path)
    assert ver_path.is_file(), "missing manifest at " + str(ver_path)
    return (
        json.loads(gen_path.read_text(encoding="utf-8")),
        json.loads(ver_path.read_text(encoding="utf-8")),
    )


def test_verification_run_id_is_slug_attempt_n(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    provenance_writer.write_provenance("comp-foo", _make_inputs(), repo_root)

    gen_manifest, ver_manifest = _read_manifests(repo_root)
    assert field(gen_manifest, "verification_run_id") == "foo-attempt-2"
    assert field(ver_manifest, "verification_run_id") == "foo-attempt-2"


def test_verification_run_id_is_identical_across_runs(tmp_path):
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_a.mkdir()
    repo_b.mkdir()

    provenance_writer.write_provenance("comp-foo", _make_inputs(), repo_a)
    first_gen, first_ver = _read_manifests(repo_a)

    provenance_writer.write_provenance("comp-foo", _make_inputs(), repo_b)
    second_gen, second_ver = _read_manifests(repo_b)

    assert field(first_gen, "verification_run_id") == field(
        second_gen, "verification_run_id"
    )
    assert field(first_ver, "verification_run_id") == field(
        second_ver, "verification_run_id"
    )
    assert field(first_gen, "verification_run_id") == "foo-attempt-2"

    # Same repo_root, run again: still identical.
    provenance_writer.write_provenance("comp-foo", _make_inputs(), repo_a)
    third_gen, third_ver = _read_manifests(repo_a)
    assert field(third_gen, "verification_run_id") == field(
        first_gen, "verification_run_id"
    )
    assert field(third_ver, "verification_run_id") == field(
        first_ver, "verification_run_id"
    )