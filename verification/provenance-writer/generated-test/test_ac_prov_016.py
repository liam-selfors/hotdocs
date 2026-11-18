# hotdocs-criterion: sha256:0ad2555e6fd5b3d5331ccfd68ff126ed2714a1c63b8bed9bf3970f1dec812133
import json
import types
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def license_fields():
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


def secret_fields():
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
            {
                "rule_id": "AWS Access Key",
                "file": "verification/foo/test_x.py",
                "line": 3,
            }
        ],
        "unused_allowlist_entries": [
            {"file": "verification/foo/old.py", "type": "AWS Access Key"}
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"foo.py": "x = 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def verification_report():
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
        "mutation_score": 0.92,
        "mutation_error": None,
        "overall": "pass",
    }


def make_inputs(license_scan_result, secret_scan_result):
    data = {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result(),
        "verification_report": verification_report(),
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
            return cls(**data)
        except TypeError:
            pass
    return data


def manifest_paths(repo_root):
    return [
        Path(repo_root) / "gen" / SLUG / ".provenance.json",
        Path(repo_root) / "verification" / SLUG / ".provenance.json",
    ]


def read_manifests(repo_root):
    manifests = []
    for path in manifest_paths(repo_root):
        assert path.is_file(), "manifest not written at " + str(path)
        manifests.append(json.loads(path.read_text(encoding="utf-8")))
    return manifests


def test_simple_namespace_scan_results_are_serialized(tmp_path):
    lic = license_fields()
    sec = secret_fields()
    inputs = make_inputs(
        types.SimpleNamespace(**lic), types.SimpleNamespace(**sec)
    )

    provenance_writer.write_provenance(COMPONENT_ID, inputs, tmp_path)

    for manifest in read_manifests(tmp_path):
        license_scan = field(manifest, "license_scan")
        secret_scan = field(manifest, "secret_scan")
        assert isinstance(license_scan, dict)
        assert isinstance(secret_scan, dict)
        for name, value in lic.items():
            assert name in license_scan, "license_scan missing " + name
            assert license_scan[name] == value, name
        for name, value in sec.items():
            assert name in secret_scan, "secret_scan missing " + name
            assert secret_scan[name] == value, name


class AttrLicenseScan:
    def __init__(self, fields):
        for name, value in fields.items():
            setattr(self, name, value)
        self._cache = {"hidden": "value"}

    def describe(self):
        return "license scan for " + str(self.component_id)


def test_plain_object_uses_public_non_callable_attributes(tmp_path):
    lic = license_fields()
    lic["blocked"] = True
    obj = AttrLicenseScan(lic)
    inputs = make_inputs(obj, types.SimpleNamespace(**secret_fields()))

    provenance_writer.write_provenance(COMPONENT_ID, inputs, tmp_path)

    for manifest in read_manifests(tmp_path):
        license_scan = field(manifest, "license_scan")
        assert isinstance(license_scan, dict)
        assert "blocked" in license_scan
        assert license_scan["blocked"] is True
        assert "describe" not in license_scan
        assert "_cache" not in license_scan