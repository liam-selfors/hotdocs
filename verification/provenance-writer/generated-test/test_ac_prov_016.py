import json
import types

import provenance_writer


def _slug(component_id):
    return component_id[len("comp-"):]


def _make_generation_result(component_id):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": None,
        "refused": "pinned-override",
        "retry_feedback": None,
    }


def _make_license_scan_fields(component_id):
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.55,
        "block_threshold": 0.70,
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


def _make_secret_scan_fields():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def test_simplenamespace_scan_results_convert_with_every_field(tmp_path):
    component_id = "comp-foo"
    slug = _slug(component_id)

    license_fields = _make_license_scan_fields(component_id)
    secret_fields = _make_secret_scan_fields()

    inputs = {
        "component_id": component_id,
        "generation_result": _make_generation_result(component_id),
        "verification_report": None,
        "license_scan_result": types.SimpleNamespace(**license_fields),
        "secret_scan_result": types.SimpleNamespace(**secret_fields),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }

    provenance_writer.write_provenance(component_id, inputs, tmp_path)

    gen_manifest_path = tmp_path / "gen" / slug / ".provenance.json"
    verif_manifest_path = tmp_path / "verification" / slug / ".provenance.json"

    assert gen_manifest_path.is_file()
    assert verif_manifest_path.is_file()

    for manifest_path in (gen_manifest_path, verif_manifest_path):
        manifest = json.loads(manifest_path.read_text())

        license_scan = manifest["license_scan"]
        for key, value in license_fields.items():
            assert license_scan[key] == value

        secret_scan = manifest["secret_scan"]
        for key, value in secret_fields.items():
            assert secret_scan[key] == value


class _WeirdLicenseScan:
    def __init__(self):
        self.blocked = True
        self._cache = {"should": "not-appear"}

    def describe(self):
        return "a description"


def test_license_scan_object_exposes_only_public_noncallable_attributes(tmp_path):
    component_id = "comp-bar"
    slug = _slug(component_id)

    secret_fields = _make_secret_scan_fields()

    inputs = {
        "component_id": component_id,
        "generation_result": _make_generation_result(component_id),
        "verification_report": None,
        "license_scan_result": _WeirdLicenseScan(),
        "secret_scan_result": types.SimpleNamespace(**secret_fields),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }

    provenance_writer.write_provenance(component_id, inputs, tmp_path)

    gen_manifest_path = tmp_path / "gen" / slug / ".provenance.json"
    verif_manifest_path = tmp_path / "verification" / slug / ".provenance.json"

    assert gen_manifest_path.is_file()
    assert verif_manifest_path.is_file()

    for manifest_path in (gen_manifest_path, verif_manifest_path):
        manifest = json.loads(manifest_path.read_text())
        license_scan = manifest["license_scan"]

        assert license_scan["blocked"] is True
        assert "describe" not in license_scan
        assert "_cache" not in license_scan