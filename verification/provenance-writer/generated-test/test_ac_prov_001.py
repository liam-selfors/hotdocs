import dataclasses
import json
from pathlib import Path

import provenance_writer


# SPEC_GUIDELINES.md §7's provenance manifest field list (reproduced in
# provenance-writer's interface/data provenance manifest document).
EXPECTED_KEYS = {
    "spec_bundle_hash",
    "model_pin",
    "prompt_version",
    "retry_feedback",
    "pipeline_version",
    "gate_versions",
    "provenance_hit",
    "generated_at",
    "verification_run_id",
    "verification_report",
    "license_scan",
    "secret_scan",
}

COMPONENT_ID = "comp-prov-sample"
SLUG = "prov-sample"


def _field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"prov_sample.py": "def compute_widget(x):\n    return x\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {
                "id": "AC-PROV-SAMPLE-001",
                "covers": "R-PROV-SAMPLE-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-PROV-SAMPLE-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }


def _license_scan_result():
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
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        },
    }


def _build_inputs():
    fields = _inputs_fields()
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if isinstance(cls, type):
        if dataclasses.is_dataclass(cls):
            names = {f.name for f in dataclasses.fields(cls)}
            return cls(**{k: v for k, v in fields.items() if k in names})
        try:
            return cls(**fields)
        except TypeError:
            return fields
    return fields


def _read_manifest(path: Path):
    assert path.is_file(), f"expected manifest at {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"manifest at {path} is not a JSON object"
    return data


def test_ac_prov_001_manifest_top_level_keys_match_spec_guidelines_section_7(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True)
    (gen_dir / "prov_sample.py").write_text(
        "def compute_widget(x):\n    return x\n", encoding="utf-8"
    )

    inputs = _build_inputs()

    result = provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)
    assert result is None

    gen_manifest = _read_manifest(repo_root / "gen" / SLUG / ".provenance.json")
    ver_manifest = _read_manifest(
        repo_root / "verification" / SLUG / ".provenance.json"
    )

    for label, manifest in (("gen", gen_manifest), ("verification", ver_manifest)):
        keys = set(manifest.keys())
        extra = keys - EXPECTED_KEYS
        missing = EXPECTED_KEYS - keys
        assert not extra, f"{label} manifest has extra keys: {sorted(extra)}"
        assert not missing, f"{label} manifest is missing keys: {sorted(missing)}"
        assert keys == EXPECTED_KEYS
        assert len(manifest) == len(EXPECTED_KEYS)