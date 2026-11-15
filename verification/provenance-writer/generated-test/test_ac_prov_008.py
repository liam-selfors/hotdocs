import json
from datetime import datetime, timezone
from pathlib import Path

import provenance_writer


INTERNAL_TIMESTAMP = "2001-02-03T04:05:06Z"
COMPONENT_ID = "comp-widget"
SLUG = "widget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"widget.py": "def make_widget(x):\n    return x\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
        # Unrelated upstream-internal timestamps the writer must not copy.
        "generated_at": INTERNAL_TIMESTAMP,
        "timestamp": INTERNAL_TIMESTAMP,
        "stored_at": INTERNAL_TIMESTAMP,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {
                "id": "AC-WIDGET-001",
                "covers": "R-WIDGET-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-WIDGET-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }


def _license_scan_result():
    return {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _secret_scan_result():
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
    return {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        },
    }


def _parse_ts(text):
    assert isinstance(text, str), f"generated_at is not a string: {text!r}"
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def test_generated_at_is_own_write_time_not_upstream_timestamp(tmp_path):
    repo_root = Path(tmp_path)

    before = datetime.now(timezone.utc).replace(microsecond=0)
    provenance_writer.write_provenance(COMPONENT_ID, _inputs(), repo_root)
    after = datetime.now(timezone.utc).replace(microsecond=0)

    manifest_paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]

    for path in manifest_paths:
        assert path.is_file(), f"manifest not written at {path}"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        generated_at = field(manifest, "generated_at")

        assert generated_at != INTERNAL_TIMESTAMP, (
            f"{path}: generated_at was copied from the upstream "
            f"GenerationResult's internal timestamp"
        )

        written = _parse_ts(generated_at)
        assert written != _parse_ts(INTERNAL_TIMESTAMP)
        assert before <= written <= after, (
            f"{path}: generated_at {generated_at!r} is not within this "
            f"component's write window [{before.isoformat()}, {after.isoformat()}]"
        )