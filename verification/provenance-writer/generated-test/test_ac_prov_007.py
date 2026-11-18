# hotdocs-criterion: sha256:593c06c02efc592f6ed62eccf6a3a37f26a02769677c19b4f5657d95ae33272c
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"foo.py": "def foo():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "overall": "pass",
    }


def _clean_license_scan():
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


def _clean_secret_scan():
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


def _inputs():
    data = {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _clean_license_scan(),
        "secret_scan_result": _clean_secret_scan(),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        },
    }
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None:
        try:
            return cls(**data)
        except TypeError:
            pass
    return data


def _read_manifest(path):
    assert path.is_file(), "manifest missing at " + str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def test_clean_scans_are_still_recorded(tmp_path):
    repo_root = Path(tmp_path)
    (repo_root / "gen" / SLUG).mkdir(parents=True, exist_ok=True)
    (repo_root / "verification" / SLUG).mkdir(parents=True, exist_ok=True)

    provenance_writer.write_provenance(COMPONENT_ID, _inputs(), repo_root)

    paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]
    for path in paths:
        manifest = _read_manifest(path)
        assert isinstance(manifest, dict)

        assert "license_scan" in manifest
        license_scan = manifest["license_scan"]
        assert license_scan is not None
        assert isinstance(license_scan, dict)
        assert license_scan != {}
        assert field(license_scan, "blocked") is False
        assert field(license_scan, "evaluated") is True
        assert field(license_scan, "matches") == []

        assert "secret_scan" in manifest
        secret_scan = manifest["secret_scan"]
        assert secret_scan is not None
        assert isinstance(secret_scan, dict)
        assert secret_scan != {}
        assert field(secret_scan, "flagged") is False
        assert field(secret_scan, "matches") == []