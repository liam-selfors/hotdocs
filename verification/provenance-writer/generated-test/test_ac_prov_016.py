# hotdocs-criterion: sha256:5b94943a568414afdc08f96ae8d0043890ae3d9a3c71702bedf19801016604a5
import json
import types

import provenance_writer


COMPONENT_ID = "comp-nsfoo"
SLUG = "nsfoo"


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
                "file": "gen/nsfoo/config.py",
                "line": 12,
            }
        ],
        "allowed": [
            {
                "rule_id": "AWS Access Key",
                "file": "verification/nsfoo/test_x.py",
                "line": 3,
            }
        ],
        "unused_allowlist_entries": [
            {"file": "verification/nsfoo/old.py", "type": "AWS Access Key"}
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _make_inputs(license_scan_result, secret_scan_result):
    data = {
        "component_id": COMPONENT_ID,
        "generation_result": {"files": {}},
        "verification_report": None,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {},
    }
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None:
        try:
            return cls(**data)
        except Exception:
            pass
    return data


def _read_manifests(repo_root):
    gen_path = repo_root / "gen" / SLUG / ".provenance.json"
    ver_path = repo_root / "verification" / SLUG / ".provenance.json"
    assert gen_path.is_file(), "manifest missing at " + str(gen_path)
    assert ver_path.is_file(), "manifest missing at " + str(ver_path)
    return [
        json.loads(gen_path.read_text(encoding="utf-8")),
        json.loads(ver_path.read_text(encoding="utf-8")),
    ]


def test_simplenamespace_scan_results_are_written_with_all_fields(tmp_path):
    license_fields = _license_fields()
    secret_fields = _secret_fields()
    license_ns = types.SimpleNamespace(**_license_fields())
    secret_ns = types.SimpleNamespace(**_secret_fields())

    inputs = _make_inputs(license_ns, secret_ns)
    provenance_writer.write_provenance(COMPONENT_ID, inputs, tmp_path)

    for manifest in _read_manifests(tmp_path):
        license_scan = manifest["license_scan"]
        secret_scan = manifest["secret_scan"]
        assert isinstance(license_scan, dict)
        assert isinstance(secret_scan, dict)
        for name, value in license_fields.items():
            assert name in license_scan, "license_scan lacks " + name
            assert license_scan[name] == value, "license_scan." + name
        for name, value in secret_fields.items():
            assert name in secret_scan, "secret_scan lacks " + name
            assert secret_scan[name] == value, "secret_scan." + name


class _ScanObject:
    def __init__(self):
        self.blocked = True
        self._cache = {"hidden": 1}

    def describe(self):
        return "a license scan"


def test_plain_object_converted_from_public_non_callable_attributes(tmp_path):
    license_obj = _ScanObject()
    secret_ns = types.SimpleNamespace(**_secret_fields())

    inputs = _make_inputs(license_obj, secret_ns)
    provenance_writer.write_provenance(COMPONENT_ID, inputs, tmp_path)

    for manifest in _read_manifests(tmp_path):
        license_scan = manifest["license_scan"]
        assert isinstance(license_scan, dict)
        assert "blocked" in license_scan
        assert license_scan["blocked"] is True
        assert "describe" not in license_scan
        assert "_cache" not in license_scan