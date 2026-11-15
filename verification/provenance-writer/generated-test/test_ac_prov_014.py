import provenance_writer

import copy
import json
from datetime import datetime
from pathlib import Path

import pytest


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"

# Fields whose value is legitimately produced from the writer's own clock or
# run identity rather than from `inputs`; they are compared for presence and
# shape, plus closeness for the timestamp, instead of strict equality.
_VOLATILE_FIELDS = ("generated_at", "verification_run_id")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result_with_files():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "model": "anthropic:claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"widget_maker.py": "def build_widget(x):\n    return x + 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": ["R-WIDGET-003"],
    }


def _generation_result_model_error():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "cd" * 32,
        "model": "anthropic:claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "connection reset"},
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-WIDGET-001", "covers": "R-WIDGET-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-WIDGET-002", "covers": "R-WIDGET-002", "kind": "llm-judge",
             "result": "skipped", "rationale": None},
            {"id": "AC-WIDGET-003", "covers": "R-WIDGET-003", "kind": "generated-test", "result": "pass",
             "test_authoring": {"model": "anthropic:claude-sonnet-5", "seed": 0,
                                "prompt_version": "v1", "cache_hit": False}},
        ],
        "requirement_results": {"R-WIDGET-001": "pass", "R-WIDGET-002": "fail", "R-WIDGET-003": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "overall": "pass",
    }


def _license_scan_result():
    return {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.12,
        "block_threshold": 0.70,
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


def _inputs_fields(variant):
    if variant == "verified":
        generation_result = _generation_result_with_files()
        verification_report = _verification_report()
        attempts = 2
    else:
        generation_result = _generation_result_model_error()
        verification_report = None
        attempts = 1
    return {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": attempts,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        },
    }


def _prepare_repo(root: Path, fields) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    files = fields["generation_result"]["files"] or {}
    gen_dir = root / "gen" / SLUG
    gen_dir.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        target = gen_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def _manifest_paths(repo_root: Path):
    # Exact paths, never a glob: `.provenance.json` is a hidden file.
    return (
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    )


def _read_manifests(repo_root: Path):
    manifests = []
    for path in _manifest_paths(repo_root):
        assert path.is_file(), f"manifest not written at exact path {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict) and data, f"manifest at {path} is not a non-empty JSON object"
        manifests.append(data)
    return manifests


def _parse_ts(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _assert_volatile_equivalent(name, a, b):
    if a == b:
        return
    if name == "generated_at":
        ta, tb = _parse_ts(a), _parse_ts(b)
        assert ta is not None and tb is not None, f"generated_at differs and is unparsable: {a!r} vs {b!r}"
        assert abs((ta - tb).total_seconds()) <= 5, f"generated_at differs: {a!r} vs {b!r}"
    else:
        # A per-run identifier may legitimately differ between two runs; it
        # must still be the same kind of value in both manifests.
        assert type(a) is type(b), f"{name} differs in shape: {a!r} vs {b!r}"


def _assert_manifests_identical(from_dict, from_instance):
    assert set(from_dict.keys()) == set(from_instance.keys()), (
        f"manifest keys differ: {sorted(from_dict)} vs {sorted(from_instance)}"
    )
    for key in from_dict:
        if key in _VOLATILE_FIELDS:
            _assert_volatile_equivalent(key, from_dict[key], from_instance[key])
        else:
            assert from_dict[key] == from_instance[key], (
                f"manifest field {key!r} differs: {from_dict[key]!r} vs {from_instance[key]!r}"
            )


@pytest.mark.parametrize("variant", ["verified", "never-verified"])
def test_dict_shaped_inputs_write_same_manifest_as_instance(tmp_path, variant):
    fields = _inputs_fields(variant)

    dict_root = _prepare_repo(tmp_path / "dict_repo", fields)
    instance_root = _prepare_repo(tmp_path / "instance_repo", fields)

    dict_inputs = copy.deepcopy(fields)
    assert isinstance(dict_inputs, dict)
    assert not isinstance(dict_inputs, provenance_writer.ProvenanceInputs)

    instance_inputs = provenance_writer.ProvenanceInputs(**copy.deepcopy(fields))
    assert not isinstance(instance_inputs, dict)

    # Dict-shaped inputs: must not raise.
    provenance_writer.write_provenance(COMPONENT_ID, dict_inputs, dict_root)
    # Equivalent instance built from the same values.
    provenance_writer.write_provenance(COMPONENT_ID, instance_inputs, instance_root)

    dict_gen, dict_verif = _read_manifests(dict_root)
    inst_gen, inst_verif = _read_manifests(instance_root)

    _assert_manifests_identical(dict_gen, inst_gen)
    _assert_manifests_identical(dict_verif, inst_verif)


@pytest.mark.parametrize("variant", ["verified", "never-verified"])
def test_instance_inputs_write_manifest(tmp_path, variant):
    fields = _inputs_fields(variant)
    repo_root = _prepare_repo(tmp_path / "repo", fields)

    inputs = provenance_writer.ProvenanceInputs(**copy.deepcopy(fields))
    assert not isinstance(inputs, dict)
    for name in (
        "generation_result",
        "verification_report",
        "license_scan_result",
        "secret_scan_result",
        "provenance_hit",
        "attempts",
        "gate_versions",
    ):
        assert field(inputs, name) == fields[name]

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    gen_manifest, verif_manifest = _read_manifests(repo_root)
    assert gen_manifest
    assert verif_manifest