# hotdocs-criterion: sha256:e51a5c71a04aaf9d4b8a5649f143727b38995994e1aa1e3a78f83ce3c1c26e1c
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _read_manifests(repo_root, component_id):
    slug = component_id[len("comp-"):]
    gen_path = Path(repo_root) / "gen" / slug / ".provenance.json"
    ver_path = Path(repo_root) / "verification" / slug / ".provenance.json"
    assert gen_path.is_file(), "missing manifest at " + str(gen_path)
    assert ver_path.is_file(), "missing manifest at " + str(ver_path)
    return (
        json.loads(gen_path.read_text(encoding="utf-8")),
        json.loads(ver_path.read_text(encoding="utf-8")),
    )


def test_ac_prov_012_pipeline_version_is_module_constant(tmp_path):
    constant = provenance_writer.PIPELINE_VERSION

    root_a = tmp_path / "repo_a"
    root_b = tmp_path / "repo_b"
    root_a.mkdir()
    root_b.mkdir()

    inputs_a = {
        "component_id": "comp-alpha",
        "generation_result": {
            "files": {},
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "retry_feedback": None,
        },
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {},
    }

    # Different inputs throughout, including values that look like a
    # pipeline version, which must never be used as pipeline_version.
    inputs_b = {
        "component_id": "comp-beta-gamma",
        "generation_result": {
            "files": {},
            "spec_bundle_hash": "sha256:" + "b" * 64,
            "model": "anthropic:claude-opus-5-5",
            "prompt_version": "v99-not-the-pipeline",
            "retry_feedback": ["R-BETA-001"],
            "pipeline_version": "from-generation-result",
        },
        "verification_report": None,
        "license_scan_result": {"gate_version": "license_scanner@4.0.0-no-reference-corpus"},
        "secret_scan_result": {"scope": "full", "flagged": False},
        "provenance_hit": True,
        "attempts": 3,
        "attempt_history": [],
        "gate_versions": {
            "compiler": "9.9.9",
            "pipeline": "pipeline@123.0.0",
            "pipeline_version": "from-gate-versions",
        },
        "spec_bundle_parts": {"spec": "sha256:" + "c" * 64},
        "pipeline_version": "from-inputs",
    }

    result_a = provenance_writer.write_provenance("comp-alpha", inputs_a, root_a)
    result_b = provenance_writer.write_provenance("comp-beta-gamma", inputs_b, root_b)
    assert result_a is None
    assert result_b is None

    gen_a, ver_a = _read_manifests(root_a, "comp-alpha")
    gen_b, ver_b = _read_manifests(root_b, "comp-beta-gamma")

    versions = [
        field(gen_a, "pipeline_version"),
        field(ver_a, "pipeline_version"),
        field(gen_b, "pipeline_version"),
        field(ver_b, "pipeline_version"),
    ]

    # Both manifests' pipeline_version fields are identical...
    assert versions[0] == versions[2]
    assert all(v == versions[0] for v in versions)
    # ...and equal this component's own version constant.
    assert versions[0] == constant
    for bogus in (
        "from-generation-result",
        "from-gate-versions",
        "from-inputs",
        "pipeline@123.0.0",
        "v99-not-the-pipeline",
    ):
        assert versions[2] != bogus