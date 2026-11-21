# hotdocs-criterion: sha256:38a55f5dddd627fa738b85f0d42f8fcc1282499fa6a40251d46d9c5a3739fe37
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def clean_license_scan_result():
    return {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.0,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def clean_secret_scan_result():
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


def generation_result():
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "unreachable"},
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def read_manifest(path):
    assert path.is_file(), "manifest not written at " + str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def test_clean_scans_are_still_recorded_in_manifest(tmp_path):
    repo_root = Path(tmp_path)
    license_result = clean_license_scan_result()
    secret_result = clean_secret_scan_result()
    inputs = {
        "component_id": "comp-foo",
        "generation_result": generation_result(),
        "verification_report": None,
        "license_scan_result": license_result,
        "secret_scan_result": secret_result,
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {},
    }

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    paths = [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]
    for path in paths:
        manifest = read_manifest(path)
        assert isinstance(manifest, dict)

        assert "license_scan" in manifest, "license_scan missing from " + str(path)
        assert "secret_scan" in manifest, "secret_scan missing from " + str(path)

        license_scan = field(manifest, "license_scan")
        secret_scan = field(manifest, "secret_scan")

        assert license_scan is not None, "license_scan is null in " + str(path)
        assert secret_scan is not None, "secret_scan is null in " + str(path)

        assert license_scan == license_result
        assert secret_scan == secret_result

        assert field(license_scan, "blocked") is False
        assert field(license_scan, "matches") == []
        assert field(secret_scan, "flagged") is False
        assert field(secret_scan, "matches") == []