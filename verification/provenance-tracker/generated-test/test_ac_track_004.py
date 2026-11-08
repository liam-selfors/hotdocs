import json
import re
from pathlib import Path

import provenance_tracker


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _find_repo_root():
    start_candidates = [Path(__file__).resolve().parent, Path.cwd()]
    for start in start_candidates:
        current = start
        for _ in range(10):
            candidate = current / "specs" / "components" / "provenance-tracker" / "component.md"
            if candidate.is_file():
                return current, candidate
            parent = current.parent
            if parent == current:
                break
            current = parent
    return None, None


def test_write_attempt_record_uses_plain_params_and_excludes_gate_runner_dependency(tmp_path):
    real_repo_root, component_md_path = _find_repo_root()
    assert component_md_path is not None, (
        "could not locate specs/components/provenance-tracker/component.md "
        "to inspect this component's own depends_on list"
    )

    component_md_text = component_md_path.read_text()
    match = re.search(r"^depends_on:\s*\[(.*?)\]\s*$", component_md_text, re.MULTILINE)
    assert match is not None, "comp-provenance-tracker's component.md has no depends_on list"
    depends_on = [item.strip() for item in match.group(1).split(",") if item.strip()]
    assert "comp-component-gate-runner" not in depends_on, (
        "comp-provenance-tracker's depends_on list must never include "
        f"comp-component-gate-runner, found: {depends_on}"
    )

    # Fresh, empty repo_root: deliberately no gen/component-gate-runner/ anywhere
    # under it, so a hidden dependency on that component's own type would
    # surface as a failure (e.g. a missing-file/import error) when
    # write_attempt_record runs below.
    repo_root = tmp_path

    component_id = "comp-sample-widget"
    spec_bundle_hash = "sha256:" + ("0" * 64)
    generation_result = {
        "model_call_error": {"category": "network", "message": "generation failed"}
    }
    verification_report = None

    record = provenance_tracker.write_attempt_record(
        component_id,
        generation_result,
        verification_report,
        spec_bundle_hash,
        repo_root,
    )

    assert _field(record, "component_id") == component_id
    assert _field(record, "spec_bundle_hash") == spec_bundle_hash
    assert _field(record, "generation") == generation_result
    assert _field(record, "verification") is None
    assert _field(record, "attempt_id") is not None

    attempts_dir = repo_root / ".hotdocs" / "attempts" / component_id
    assert attempts_dir.is_dir(), f"expected attempt directory at {attempts_dir}"
    written_files = list(attempts_dir.glob("*"))
    assert len(written_files) == 1, f"expected exactly one attempt file, found {written_files}"

    persisted = json.loads(written_files[0].read_text())
    assert persisted["component_id"] == component_id
    assert persisted["spec_bundle_hash"] == spec_bundle_hash
    assert persisted["generation"] == generation_result
    assert persisted["verification"] is None