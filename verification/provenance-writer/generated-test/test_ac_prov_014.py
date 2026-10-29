import glob
import json
import re
import tempfile
from pathlib import Path

import provenance_writer


GENERATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _fixture_values():
    return {
        "component_id": "comp-foo",
        "generation_result": {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"spec_linter.py": "# generated content\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
        "verification_report": {
            "component_id": "comp-foo",
            "criteria": [
                {
                    "id": "AC-FOO-001",
                    "covers": "R-FOO-001",
                    "kind": "compiled",
                    "result": "pass",
                },
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.92,
            "overall": "pass",
        },
        "license_scan_result": {
            "component_id": "comp-foo",
            "gate_version": "license_scanner@3.1.0",
            "similarity_score": 0.1,
            "block_threshold": 0.70,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan_result": {
            "scope": "full",
            "gate_version": "secret_scanner@2.0.0",
            "flagged": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "provenance_hit": False,
        "attempts": 2,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "k-gram@1.0.0",
        },
    }


def _find_manifests(repo_root):
    pattern = str(Path(repo_root) / "**" / ".provenance.json")
    paths = sorted(glob.glob(pattern, recursive=True))
    assert paths, f"no .provenance.json manifest written under {repo_root}"
    return paths


def _load_canonical_manifest(repo_root):
    paths = _find_manifests(repo_root)
    manifests = [json.loads(Path(p).read_text()) for p in paths]
    first = manifests[0]
    for other in manifests[1:]:
        assert other == first, (
            "manifest content differs between the two required write locations"
        )
    return first


def _assert_manifests_equivalent(manifest_a, manifest_b):
    assert set(manifest_a.keys()) == set(manifest_b.keys())
    for key in manifest_a:
        if key == "generated_at":
            # separate calls may legitimately land on different wall-clock
            # seconds; only the format is asserted, not bit-identical equality
            assert GENERATED_AT_RE.match(manifest_a[key])
            assert GENERATED_AT_RE.match(manifest_b[key])
            continue
        assert manifest_a[key] == manifest_b[key], (
            f"field {key!r} differs: {manifest_a[key]!r} != {manifest_b[key]!r}"
        )


def test_write_provenance_dict_inputs_matches_instance_inputs():
    values = _fixture_values()

    dict_repo_root = Path(tempfile.mkdtemp())
    provenance_writer.write_provenance("comp-foo", values, dict_repo_root)
    dict_manifest = _load_canonical_manifest(dict_repo_root)

    instance_repo_root = Path(tempfile.mkdtemp())
    inputs_instance = provenance_writer.ProvenanceInputs(**values)
    provenance_writer.write_provenance(
        "comp-foo", inputs_instance, instance_repo_root
    )
    instance_manifest = _load_canonical_manifest(instance_repo_root)

    _assert_manifests_equivalent(dict_manifest, instance_manifest)


def test_write_provenance_with_instance_inputs_does_not_raise():
    values = _fixture_values()
    values["generation_result"] = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "b" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": None,
        "refused": "sealed-component",
        "retry_feedback": None,
    }
    values["verification_report"] = None

    inputs_instance = provenance_writer.ProvenanceInputs(**values)

    repo_root = Path(tempfile.mkdtemp())
    provenance_writer.write_provenance("comp-foo", inputs_instance, repo_root)

    _load_canonical_manifest(repo_root)