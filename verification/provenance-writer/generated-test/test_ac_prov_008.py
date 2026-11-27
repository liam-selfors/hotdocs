# hotdocs-criterion: sha256:35c19fed0b9284e3790b59b8bc86b575baef56334f788ae6a0740f76262367d6
"""AC-PROV-008: generated_at is this component's own write time, never an
upstream component's internal timestamp (R-PROV-008)."""

import json
import re
from datetime import datetime, timezone

import provenance_writer


INTERNAL_TIMESTAMP = "1999-01-02T03:04:05Z"
GENERATED_AT_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": {},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
        # Unrelated internal timestamps an upstream component might carry.
        "generated_at": INTERNAL_TIMESTAMP,
        "timestamp": INTERNAL_TIMESTAMP,
        "created_at": INTERNAL_TIMESTAMP,
        "stored_at": INTERNAL_TIMESTAMP,
    }


def _inputs():
    return {
        "component_id": "comp-foo",
        "generation_result": _generation_result(),
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {},
    }


def _parse(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def test_generated_at_is_own_write_time_not_internal_timestamp(tmp_path):
    repo_root = tmp_path

    before = datetime.now(timezone.utc).replace(microsecond=0)
    provenance_writer.write_provenance("comp-foo", _inputs(), repo_root)
    after = datetime.now(timezone.utc).replace(microsecond=0)

    paths = [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest missing at " + str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        generated_at = field(manifest, "generated_at")

        assert isinstance(generated_at, str)
        assert GENERATED_AT_RE.match(generated_at), generated_at
        assert generated_at != INTERNAL_TIMESTAMP

        written = _parse(generated_at)
        assert before <= written <= after, (
            "generated_at " + generated_at + " not within write window "
            + before.isoformat() + " .. " + after.isoformat()
        )