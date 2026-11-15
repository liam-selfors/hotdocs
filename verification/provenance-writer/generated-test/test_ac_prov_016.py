import json
import types
from pathlib import Path

import pytest

import provenance_writer


COMPONENT_ID = "comp-ns-widget"
SLUG = "ns-widget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    # A refused generation: no files, so verification_report may be null
    # without being a missing upstream result.
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {},
        "model_call_error": None,
        "refused": "sealed-component",
        "retry_feedback": None,
    }


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
                "file": "gen/ns-widget/config.py",
                "line": 12,
            }
        ],
        "allowed": [
            {
                "rule_id": "AWS Access Key",
                "file": "verification/ns-widget/test_x.py",
                "line": 3,
            }
        ],
        "unused_allowlist_entries": [
            {"file": "verification/ns-widget/old.py", "type": "AWS Access Key"}
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _make_inputs(license_scan_result, secret_scan_result):
    fields = {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": None,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "k-gram@1.0.0",
        },
    }
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None:
        try:
            return cls(**fields)
        except TypeError:
            pass
    return dict(fields)


def _manifest_paths(repo_root):
    return [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]


def _read_manifests(repo_root):
    manifests = []
    for path in _manifest_paths(repo_root):
        assert path.is_file(), f"manifest not written at {path}"
        manifests.append(json.loads(path.read_text(encoding="utf-8")))
    return manifests


def test_simplenamespace_scan_results_are_serialized_with_all_fields(tmp_path):
    repo_root = Path(tmp_path)
    license_fields = _license_fields()
    secret_fields = _secret_fields()
    license_ns = types.SimpleNamespace(**license_fields)
    secret_ns = types.SimpleNamespace(**secret_fields)

    inputs = _make_inputs(license_ns, secret_ns)

    # Must not raise.
    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    for manifest in _read_manifests(repo_root):
        license_scan = manifest["license_scan"]
        secret_scan = manifest["secret_scan"]
        assert isinstance(license_scan, dict)
        assert isinstance(secret_scan, dict)
        for name, value in license_fields.items():
            assert name in license_scan, f"license_scan missing {name!r}"
            assert license_scan[name] == value, (
                f"license_scan[{name!r}] = {license_scan[name]!r}, expected {value!r}"
            )
        for name, value in secret_fields.items():
            assert name in secret_scan, f"secret_scan missing {name!r}"
            assert secret_scan[name] == value, (
                f"secret_scan[{name!r}] = {secret_scan[name]!r}, expected {value!r}"
            )


class _PlainLicenseResult:
    """A plain (non-dict, non-dataclass) object exposing fields as attributes."""

    def __init__(self, fields):
        for name, value in fields.items():
            setattr(self, name, value)
        self._cache = {"private": "state"}

    def describe(self):
        return "license scan result"


def test_plain_object_converted_from_public_non_callable_attributes(tmp_path):
    repo_root = Path(tmp_path)
    license_fields = _license_fields()
    license_obj = _PlainLicenseResult(license_fields)
    secret_ns = types.SimpleNamespace(**_secret_fields())

    inputs = _make_inputs(license_obj, secret_ns)

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    for manifest in _read_manifests(repo_root):
        license_scan = manifest["license_scan"]
        assert isinstance(license_scan, dict)
        assert "blocked" in license_scan
        assert license_scan["blocked"] == license_fields["blocked"]
        assert "describe" not in license_scan
        assert "_cache" not in license_scan