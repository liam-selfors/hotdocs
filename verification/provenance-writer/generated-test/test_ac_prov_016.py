import json
import types
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-widget"
SLUG = "widget"


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
        "flagged": False,
        "matches": [],
        "allowed": [
            {"rule_id": "AWS Access Key", "file": "verification/widget/test_x.py", "line": 3}
        ],
        "unused_allowlist_entries": [
            {"file": "verification/widget/old.py", "type": "AWS Access Key"}
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"widget.py": "def bar(x):\n    return x\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-WIDGET-001", "covers": "R-WIDGET-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-WIDGET-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }


def _inputs(license_scan_result, secret_scan_result):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
        },
    }


def _manifest_paths(repo_root: Path):
    return [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]


def _read_manifests(repo_root: Path):
    manifests = []
    for path in _manifest_paths(repo_root):
        assert path.is_file(), f"manifest not written at {path}"
        manifests.append(json.loads(path.read_text(encoding="utf-8")))
    return manifests


def test_simplenamespace_scan_results_are_serialized_with_all_fields(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    license_fields = _license_fields()
    secret_fields = _secret_fields()
    license_ns = types.SimpleNamespace(**license_fields)
    secret_ns = types.SimpleNamespace(**secret_fields)

    # Must not raise.
    provenance_writer.write_provenance(
        COMPONENT_ID, _inputs(license_ns, secret_ns), repo_root
    )

    for manifest in _read_manifests(repo_root):
        license_scan = manifest["license_scan"]
        secret_scan = manifest["secret_scan"]
        assert isinstance(license_scan, dict)
        assert isinstance(secret_scan, dict)
        for key, value in license_fields.items():
            assert key in license_scan, f"license_scan missing {key!r}"
            assert license_scan[key] == value, f"license_scan[{key!r}] mismatch"
        for key, value in secret_fields.items():
            assert key in secret_scan, f"secret_scan missing {key!r}"
            assert secret_scan[key] == value, f"secret_scan[{key!r}] mismatch"


class _PlainLicenseResult:
    def __init__(self, fields):
        for key, value in fields.items():
            setattr(self, key, value)
        self._cache = {"secret": "internal"}

    def describe(self):
        return "license scan result"


def test_plain_object_converted_from_public_non_callable_attributes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    license_fields = _license_fields()
    license_obj = _PlainLicenseResult(license_fields)
    secret_ns = types.SimpleNamespace(**_secret_fields())

    provenance_writer.write_provenance(
        COMPONENT_ID, _inputs(license_obj, secret_ns), repo_root
    )

    for manifest in _read_manifests(repo_root):
        license_scan = manifest["license_scan"]
        assert isinstance(license_scan, dict)
        assert "blocked" in license_scan
        assert license_scan["blocked"] == license_fields["blocked"]
        assert "describe" not in license_scan
        assert "_cache" not in license_scan