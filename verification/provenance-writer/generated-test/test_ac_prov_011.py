"""AC-PROV-011 (Covers: R-PROV-011).

Given a completed write_provenance call
When the written file is parsed as JSON
Then parsing succeeds and its key set matches the schema exactly
"""

import dataclasses
import json
from pathlib import Path

import pytest

import provenance_writer


COMPONENT_ID = "comp-widget"
SLUG = "widget"

# SPEC_GUIDELINES.md section 7's provenance manifest field set.
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

SPEC_HASH = "sha256:" + "ab" * 32


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


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {
                "id": "AC-WIDGET-001",
                "covers": "R-WIDGET-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-WIDGET-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }


def _generation_result(with_files):
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": SPEC_HASH,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"widget.py": "def make_widget():\n    return 1\n"} if with_files else {},
        "model_call_error": None,
        "refused": None if with_files else "sealed-component",
        "retry_feedback": None,
    }


def _inputs_dict(with_files):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(with_files),
        "verification_report": _verification_report() if with_files else None,
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        },
    }


def _make_inputs(data):
    """Build a ProvenanceInputs dataclass if the module defines one, else a dict."""
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if isinstance(cls, type) and dataclasses.is_dataclass(cls):
        names = {f.name for f in dataclasses.fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in names}
        try:
            return cls(**kwargs)
        except TypeError:
            return data
    return data


def _reject_constant(name):
    raise ValueError(f"non-standard JSON constant {name!r}")


def _parse_strict(path: Path):
    text = path.read_text(encoding="utf-8")
    return json.loads(text, parse_constant=_reject_constant)


@pytest.mark.parametrize("with_files", [True, False], ids=["verified", "never-verified"])
def test_written_manifest_is_valid_json_with_exact_schema_keys(tmp_path, with_files):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    inputs = _make_inputs(_inputs_dict(with_files))
    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    manifest_paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]

    for path in manifest_paths:
        assert path.is_file(), f"expected manifest at {path}"
        try:
            parsed = _parse_strict(path)
        except ValueError as exc:  # json.JSONDecodeError is a ValueError
            pytest.fail(f"{path} is not valid JSON: {exc}")

        assert isinstance(parsed, dict), (
            f"{path} top-level JSON value must be an object, got {type(parsed).__name__}"
        )
        keys = set(parsed.keys())
        extra = keys - EXPECTED_KEYS
        missing = EXPECTED_KEYS - keys
        assert not extra, f"{path} has extra keys: {sorted(extra)}"
        assert not missing, f"{path} is missing keys: {sorted(missing)}"
        assert keys == EXPECTED_KEYS