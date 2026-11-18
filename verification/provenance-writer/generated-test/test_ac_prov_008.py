# hotdocs-criterion: sha256:3426d62d0e94abd08fb100461021cf6a6552afe799e6442ddd56b233dfa4cc37
import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path

import provenance_writer


INTERNAL_TIMESTAMP = "2001-02-03T04:05:06Z"
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
        # Unrelated internal timestamps carried by the upstream result.
        "generated_at": INTERNAL_TIMESTAMP,
        "stored_at": INTERNAL_TIMESTAMP,
        "timestamp": INTERNAL_TIMESTAMP,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
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
    data = {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and dataclasses.is_dataclass(cls):
        names = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})
    return data


def _parse(ts):
    assert isinstance(ts, str), "generated_at must be a string, got " + repr(ts)
    text = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
    parsed = datetime.fromisoformat(text)
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
        assert path.is_file(), "missing manifest at " + str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        generated_at = field(manifest, "generated_at")

        assert generated_at != INTERNAL_TIMESTAMP, (
            "generated_at was copied from the upstream internal timestamp in " + str(path)
        )
        parsed = _parse(generated_at)
        assert parsed != _parse(INTERNAL_TIMESTAMP)
        assert before <= parsed <= after, (
            "generated_at "
            + repr(generated_at)
            + " not within write window ["
            + before.isoformat()
            + ", "
            + after.isoformat()
            + "] in "
            + str(path)
        )