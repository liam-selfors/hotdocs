import dataclasses
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-provhitprobe"
SLUG = "provhitprobe"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        # Deliberately false: provenance_hit must NOT be inferred from any
        # gate's own cache_hit (R-PROV-004).
        "cache_hit": False,
        "files": {"provhitprobe.py": "def probe_value():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {
                "id": "AC-PROVHITPROBE-001",
                "covers": "R-PROVHITPROBE-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-PROVHITPROBE-001": "pass"},
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


def _inputs_dict():
    return {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": True,
        "attempts": 1,
        "gate_versions": {
            "generator": "generator@2.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        },
    }


def _build_inputs():
    data = _inputs_dict()
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and dataclasses.is_dataclass(cls):
        names = {f.name for f in dataclasses.fields(cls)}
        try:
            return cls(**{k: v for k, v in data.items() if k in names})
        except TypeError:
            return data
    return data


def _read_manifest(path: Path):
    assert path.is_file(), f"expected manifest at {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_provenance_hit_true_is_recorded_in_manifest(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    inputs = _build_inputs()
    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    gen_manifest = _read_manifest(repo_root / "gen" / SLUG / ".provenance.json")
    ver_manifest = _read_manifest(
        repo_root / "verification" / SLUG / ".provenance.json"
    )

    for manifest in (gen_manifest, ver_manifest):
        assert field(manifest, "provenance_hit") is True