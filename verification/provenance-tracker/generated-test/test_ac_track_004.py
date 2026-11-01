import json
import re
from datetime import datetime, timezone
from pathlib import Path

import provenance_tracker

ATTEMPT_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z-[0-9a-f]+$")
TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _assert_timestamp_in_window(record, before, after):
    ts = _get(record, "timestamp")
    assert isinstance(ts, str)
    ts_dt = datetime.strptime(ts, TIMESTAMP_FMT).replace(tzinfo=timezone.utc)
    assert before <= ts_dt <= after


def _persisted_record(repo_root, component_id):
    attempts_dir = repo_root / ".hotdocs" / "attempts" / component_id
    files = sorted(p for p in attempts_dir.iterdir() if p.is_file())
    assert len(files) == 1
    return json.loads(files[0].read_text())


def test_write_attempt_record_uses_plain_parameters_directly_success_path(tmp_path):
    repo_root = tmp_path
    component_id = "comp-widget"
    generation_result = {"model_call_error": None}
    verification_report = {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-WIDGET-001", "covers": "R-WIDGET-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-WIDGET-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
    spec_bundle_hash = "sha256:" + "a" * 64

    # Capture before/after at whole-second precision to match the record's own timestamp format.
    before = datetime.now(timezone.utc).replace(microsecond=0)
    record = provenance_tracker.write_attempt_record(
        component_id, generation_result, verification_report, spec_bundle_hash, repo_root
    )
    after = datetime.now(timezone.utc).replace(microsecond=0)

    assert _get(record, "component_id") == component_id
    assert _get(record, "spec_bundle_hash") == spec_bundle_hash
    assert _get(record, "generation") == generation_result
    assert _get(record, "verification") == verification_report

    attempt_id = _get(record, "attempt_id")
    assert isinstance(attempt_id, str) and ATTEMPT_ID_RE.match(attempt_id)
    _assert_timestamp_in_window(record, before, after)

    persisted = _persisted_record(repo_root, component_id)
    assert persisted["component_id"] == component_id
    assert persisted["spec_bundle_hash"] == spec_bundle_hash
    assert persisted["generation"] == generation_result
    assert persisted["verification"] == verification_report


def test_write_attempt_record_uses_plain_parameters_directly_generation_failure_path(tmp_path):
    repo_root = tmp_path
    component_id = "comp-widget-failed"
    generation_result = {"model_call_error": "LLM request timed out"}
    spec_bundle_hash = "sha256:" + "b" * 64

    record = provenance_tracker.write_attempt_record(
        component_id, generation_result, None, spec_bundle_hash, repo_root
    )

    assert _get(record, "component_id") == component_id
    assert _get(record, "spec_bundle_hash") == spec_bundle_hash
    assert _get(record, "generation") == generation_result
    assert _get(record, "verification") is None

    persisted = _persisted_record(repo_root, component_id)
    assert persisted["generation"] == generation_result
    assert persisted["verification"] is None


def _parse_depends_on(frontmatter_text):
    for line in frontmatter_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("depends_on:"):
            value = stripped[len("depends_on:"):].strip()
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                if not inner:
                    return []
                return [item.strip() for item in inner.split(",")]
            return []
    return []


def test_depends_on_excludes_component_gate_runner():
    component_md = (
        Path(__file__).resolve().parents[3]
        / "specs"
        / "components"
        / "provenance-tracker"
        / "component.md"
    )
    assert component_md.is_file(), f"expected component spec at {component_md}"
    text = component_md.read_text()
    assert text.startswith("---"), "component.md must open with a frontmatter block"
    end = text.index("---", 3)
    frontmatter = text[3:end]
    depends_on = _parse_depends_on(frontmatter)
    assert "comp-component-gate-runner" not in depends_on