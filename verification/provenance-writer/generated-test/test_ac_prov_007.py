import dataclasses
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-prov-clean-demo"
SLUG = "prov-clean-demo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"prov_clean_demo.py": "def bar(x):\n    return x\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {
                "id": "AC-PROV-CLEAN-DEMO-001",
                "covers": "R-PROV-CLEAN-DEMO-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-PROV-CLEAN-DEMO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }


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


def _build_inputs():
    data = {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _clean_license_scan_result(),
        "secret_scan_result": _clean_secret_scan_result(),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        },
    }
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and dataclasses.is_dataclass(cls):
        try:
            return cls(**data)
        except TypeError:
            return data
    return data


def _assert_scans_present(manifest_path: Path):
    assert manifest_path.is_file(), f"manifest missing: {manifest_path}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)

    assert "license_scan" in manifest, "license_scan absent from manifest"
    assert "secret_scan" in manifest, "secret_scan absent from manifest"

    license_scan = manifest["license_scan"]
    secret_scan = manifest["secret_scan"]

    # Present and populated even though neither scan flagged anything.
    assert license_scan is not None
    assert secret_scan is not None
    assert license_scan != {}
    assert secret_scan != {}

    # They carry the clean results handed in, not a placeholder.
    assert field(license_scan, "blocked") is False
    assert field(license_scan, "matches") == []
    assert field(license_scan, "gate_version") == "license_scanner@4.0.3+9f2c41ab07de"
    assert field(secret_scan, "flagged") is False
    assert field(secret_scan, "matches") == []
    assert field(secret_scan, "gate_version") == "secret_scanner@3.1.0+detect-secrets.1.5.0"


def test_ac_prov_007_clean_scans_always_present_in_manifest(tmp_path):
    repo_root = Path(tmp_path)
    inputs = _build_inputs()

    result = provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)
    assert result is None

    _assert_scans_present(repo_root / "gen" / SLUG / ".provenance.json")
    _assert_scans_present(repo_root / "verification" / SLUG / ".provenance.json")