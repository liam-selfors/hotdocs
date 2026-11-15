import dataclasses
import json
from pathlib import Path

import pytest

import provenance_writer


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _clean_license_scan_result():
    return {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.05,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _clean_secret_scan_result():
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


def _generated_case():
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"widget_maker.py": "def make_widget(x):\n    return x\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    verification_report = {
        "component_id": COMPONENT_ID,
        "criteria": [
            {
                "id": "AC-WIDGET-MAKER-001",
                "covers": "R-WIDGET-MAKER-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-WIDGET-MAKER-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }
    return generation_result, verification_report


def _refused_case():
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "b" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {},
        "model_call_error": None,
        "refused": "pinned-override",
        "retry_feedback": None,
    }
    return generation_result, None


def _make_inputs(data):
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and dataclasses.is_dataclass(cls):
        try:
            return cls(**data)
        except TypeError:
            return data
    return data


@pytest.mark.parametrize("case", [_generated_case, _refused_case], ids=["generated", "refused"])
def test_clean_scans_are_always_recorded_in_manifest(tmp_path, case):
    repo_root = Path(tmp_path)
    generation_result, verification_report = case()
    license_scan_result = _clean_license_scan_result()
    secret_scan_result = _clean_secret_scan_result()

    inputs = _make_inputs(
        {
            "component_id": COMPONENT_ID,
            "generation_result": generation_result,
            "verification_report": verification_report,
            "license_scan_result": license_scan_result,
            "secret_scan_result": secret_scan_result,
            "provenance_hit": False,
            "attempts": 1,
            "gate_versions": {
                "compiler": "1.0.0",
                "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
                "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            },
        }
    )

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    manifest_paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]

    for path in manifest_paths:
        assert path.is_file(), f"manifest not written at {path}"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(manifest, dict)

        assert "license_scan" in manifest, f"license_scan missing from {path}"
        assert "secret_scan" in manifest, f"secret_scan missing from {path}"

        license_scan = manifest["license_scan"]
        secret_scan = manifest["secret_scan"]

        assert license_scan is not None, f"license_scan is null in {path}"
        assert secret_scan is not None, f"secret_scan is null in {path}"
        assert license_scan != {}, f"license_scan is empty in {path}"
        assert secret_scan != {}, f"secret_scan is empty in {path}"

        # The recorded scans are the clean results handed in, not a "not-run" placeholder.
        assert field(license_scan, "blocked") is False
        assert field(license_scan, "evaluated") is True
        assert field(license_scan, "matches") == []
        assert field(license_scan, "gate_version") == license_scan_result["gate_version"]

        assert field(secret_scan, "flagged") is False
        assert field(secret_scan, "matches") == []
        assert field(secret_scan, "gate_version") == secret_scan_result["gate_version"]