"""AC-TRACK-004 (Covers: R-TRACK-004).

write_attempt_record receives generation_result / verification_report as
plain-value parameters and writes the AttemptRecord from them directly. The
check of record is that provenance-tracker's own component.md `depends_on` list
does not include comp-component-gate-runner.
"""

import json
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_root():
    here = Path(provenance_tracker.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    # Fallback: walk up looking for the component's own spec file.
    for parent in here.parents:
        if (parent / "specs" / "components" / "provenance-tracker" / "component.md").is_file():
            return parent
    raise AssertionError("could not locate tool root above %s" % here)


def _frontmatter(text):
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---", "component.md must open with frontmatter"
    fm = []
    for line in lines[1:]:
        if line.strip() == "---":
            return fm
        fm.append(line)
    raise AssertionError("unterminated frontmatter in component.md")


def _flow_list(value):
    value = value.strip()
    if not value:
        return []
    assert value.startswith("[") and value.endswith("]"), (
        "depends_on must be a YAML flow-style list, got %r" % value
    )
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]


def _depends_on():
    root = _tool_root()
    path = root / "specs" / "components" / "provenance-tracker" / "component.md"
    assert path.is_file(), "missing %s" % path
    fm = _frontmatter(path.read_text(encoding="utf-8"))
    ident = None
    deps = []
    for line in fm:
        stripped = line.strip()
        if stripped.startswith("id:"):
            ident = stripped[len("id:"):].strip().strip("'\"")
        if stripped.startswith("depends_on:"):
            deps = _flow_list(stripped[len("depends_on:"):])
    return ident, deps


def test_depends_on_excludes_component_gate_runner():
    ident, deps = _depends_on()
    assert ident == "comp-provenance-tracker"
    normalized = {d if d.startswith("comp-") else "comp-" + d for d in deps}
    assert "comp-component-gate-runner" not in normalized, (
        "provenance-tracker must not depend on component-gate-runner; depends_on=%r" % deps
    )


def test_write_attempt_record_accepts_plain_value_parameters(tmp_path):
    generation_result = {
        "component_id": "comp-foo",
        "model_call_error": None,
        "files": [],
    }
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail",
             "failure_detail": {"message": "x", "expected": 1, "actual": 2}},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "fail",
    }
    spec_bundle_hash = "sha256:" + "ab" * 32

    record = provenance_tracker.write_attempt_record(
        "comp-foo",
        generation_result,
        verification_report,
        spec_bundle_hash,
        tmp_path,
    )

    assert field(record, "component_id") == "comp-foo"
    assert field(record, "spec_bundle_hash") == spec_bundle_hash
    assert field(record, "generation") == generation_result
    assert field(record, "verification") == verification_report

    attempts = tmp_path / ".hotdocs" / "attempts"
    candidates = [attempts / "comp-foo", attempts / "foo"]
    written = [p for d in candidates if d.is_dir() for p in d.iterdir() if p.is_file()]
    assert len(written) == 1, "expected exactly one attempt file, found %r" % written
    on_disk = json.loads(written[0].read_text(encoding="utf-8"))
    assert on_disk["component_id"] == "comp-foo"
    assert on_disk["spec_bundle_hash"] == spec_bundle_hash
    assert on_disk["generation"] == generation_result
    assert on_disk["verification"] == verification_report