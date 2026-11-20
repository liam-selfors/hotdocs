# hotdocs-criterion: sha256:e54f674b2bb06c684b6f376adce1ef9b99e8d1b21e6f49d37461ae028fccc7a3
import json
import re
from datetime import datetime, timezone

import provenance_writer


INTERNAL_TIMESTAMP = "2001-02-03T04:05:06Z"
TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _inputs():
    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "environment", "message": "no python"},
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
        # Unrelated upstream-internal timestamps that must never be copied.
        "generated_at": INTERNAL_TIMESTAMP,
        "stored_at": INTERNAL_TIMESTAMP,
        "timestamp": INTERNAL_TIMESTAMP,
    }
    return {
        "component_id": "comp-foo",
        "generation_result": generation_result,
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {},
    }


def _parse(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def test_generated_at_is_own_write_time_not_upstream_timestamp(tmp_path):
    before = datetime.now(timezone.utc).replace(microsecond=0)
    provenance_writer.write_provenance("comp-foo", _inputs(), tmp_path)
    after = datetime.now(timezone.utc).replace(microsecond=0)

    paths = [
        tmp_path / "gen" / "foo" / ".provenance.json",
        tmp_path / "verification" / "foo" / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest missing at " + str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        generated_at = field(manifest, "generated_at")
        assert isinstance(generated_at, str)
        assert TIMESTAMP_RE.match(generated_at), generated_at
        assert generated_at != INTERNAL_TIMESTAMP
        written = _parse(generated_at)
        assert before <= written <= after, (
            "generated_at " + generated_at + " not within write window "
            + before.isoformat() + " .. " + after.isoformat()
        )