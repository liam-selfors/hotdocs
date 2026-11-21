# hotdocs-criterion: sha256:6abab43c57b3c91d850b80f7131f6198fd848eae1e3b47d7426af550e264fe41
import json
import types
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-prov-sixteen"
SLUG = "prov-sixteen"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _license_fields():
    return {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.55,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [
            {
                "reference_id": "ref-123",
                "license_family": "gpl-3.0",
                "risk_tier": "high",
                "score": 0.55,
            }
        ],
        "notified": True,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _secret_fields():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": True,
        "matches": [
            {
                "rule_id": "AWS Access Key",
                "risk_tier": "high",
                "file": "gen/foo/config.py",
                "line": 12,
            }
        ],
        "allowed": [
            {"rule_id": "AWS Access Key", "file": "verification/foo/test_x.py", "line": 3}
        ],
        "unused_allowlist_entries": [
            {"file": "verification/foo/old.py", "type": "AWS Access Key"}
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _inputs(license_scan_result, secret_scan_result):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": {
            "component_id": COMPONENT_ID,
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {},
            "model_call_error": {"category": "network", "message": "down"},
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification_report": None,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {},
    }


def _read_manifests(repo_root):
    gen_path = Path(repo_root) / "gen" / SLUG / ".provenance.json"
    ver_path = Path(repo_root) / "verification" / SLUG / ".provenance.json"
    assert gen_path.is_file()
    assert ver_path.is_file()
    gen_bytes = gen_path.read_bytes()
    ver_bytes = ver_path.read_bytes()
    assert gen_bytes == ver_bytes
    return json.loads(gen_bytes.decode("utf-8"))


def test_simplenamespace_scan_results_are_converted(tmp_path):
    license_fields = _license_fields()
    secret_fields = _secret_fields()
    license_ns = types.SimpleNamespace(**license_fields)
    secret_ns = types.SimpleNamespace(**secret_fields)

    provenance_writer.write_provenance(
        COMPONENT_ID, _inputs(license_ns, secret_ns), tmp_path
    )

    manifest = _read_manifests(tmp_path)
    license_scan = manifest["license_scan"]
    secret_scan = manifest["secret_scan"]
    assert isinstance(license_scan, dict)
    assert isinstance(secret_scan, dict)
    for name, value in license_fields.items():
        assert name in license_scan, name
        assert license_scan[name] == value, name
    for name, value in secret_fields.items():
        assert name in secret_scan, name
        assert secret_scan[name] == value, name


class _LicenseObject:
    def __init__(self):
        self.blocked = True
        self._cache = {"hidden": 1}

    def describe(self):
        return "license scan object"


def test_object_converted_from_public_noncallable_attributes(tmp_path):
    obj = _LicenseObject()

    provenance_writer.write_provenance(COMPONENT_ID, _inputs(obj, {}), tmp_path)

    manifest = _read_manifests(tmp_path)
    license_scan = manifest["license_scan"]
    assert isinstance(license_scan, dict)
    assert "blocked" in license_scan
    assert license_scan["blocked"] is True
    assert "describe" not in license_scan
    assert "_cache" not in license_scan