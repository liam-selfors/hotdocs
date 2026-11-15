import json
from pathlib import Path

import pytest

import provenance_tracker


GATE_RUNNER_IDS = {"comp-component-gate-runner", "component-gate-runner"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _find_own_component_md():
    """Locate provenance-tracker's own component.md in the live spec corpus.

    The tool root is the parent of the nearest directory named `gen` above
    the module under test; fall back to walking every ancestor looking for
    the spec file, in case the module is laid out elsewhere.
    """
    module_path = Path(provenance_tracker.__file__).resolve()
    rel = Path("specs") / "components" / "provenance-tracker" / "component.md"

    for parent in module_path.parents:
        if parent.name == "gen":
            candidate = parent.parent / rel
            if candidate.is_file():
                return candidate
            break

    for parent in module_path.parents:
        candidate = parent / rel
        if candidate.is_file():
            return candidate

    pytest.fail(
        "could not locate specs/components/provenance-tracker/component.md "
        f"above {module_path}"
    )


def _frontmatter_lines(text):
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---", "component.md has no frontmatter"
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            return out
        out.append(line)
    pytest.fail("component.md frontmatter is not terminated")


def _parse_flow_list(raw):
    raw = raw.strip()
    if not raw:
        return []
    assert raw.startswith("[") and raw.endswith("]"), (
        f"depends_on is not a YAML flow-style list: {raw!r}"
    )
    inner = raw[1:-1].strip()
    if not inner:
        return []
    items = []
    for part in inner.split(","):
        item = part.strip().strip("'\"").strip()
        if item:
            items.append(item)
    return items


def _own_depends_on():
    text = _find_own_component_md().read_text(encoding="utf-8")
    fm = _frontmatter_lines(text)
    id_value = None
    depends_on = []
    for line in fm:
        if line.startswith("id:"):
            id_value = line.split(":", 1)[1].strip().strip("'\"")
        if line.startswith("depends_on:"):
            depends_on = _parse_flow_list(line.split(":", 1)[1])
    assert id_value == "comp-provenance-tracker", (
        f"located component.md is not provenance-tracker's own (id={id_value!r})"
    )
    return depends_on


def test_depends_on_excludes_component_gate_runner():
    depends_on = _own_depends_on()
    offending = [d for d in depends_on if d in GATE_RUNNER_IDS]
    assert offending == [], (
        "provenance-tracker must not depend on component-gate-runner "
        f"(R-TRACK-004); depends_on = {depends_on}"
    )


@pytest.mark.parametrize("failed_generation", [False, True])
def test_write_attempt_record_takes_plain_parameters(tmp_path, failed_generation):
    # The criterion's precondition holds for the live spec too.
    assert not any(d in GATE_RUNNER_IDS for d in _own_depends_on())

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_id = "comp-foo"
    spec_bundle_hash = "sha256:" + "ab" * 32

    if failed_generation:
        generation_result = {
            "component_id": component_id,
            "model": "anthropic:claude-sonnet-5",
            "seed": 0,
            "model_call_error": {"category": "network", "message": "boom"},
            "files": [],
        }
        verification_report = None
    else:
        generation_result = {
            "component_id": component_id,
            "model": "anthropic:claude-sonnet-5",
            "seed": 0,
            "model_call_error": None,
            "files": [],
        }
        verification_report = {
            "component_id": component_id,
            "criteria": [
                {"id": "AC-FOO-001", "covers": "R-FOO-001",
                 "kind": "compiled", "result": "pass"},
                {"id": "AC-FOO-002", "covers": "R-FOO-002",
                 "kind": "compiled", "result": "fail"},
            ],
            "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": "fail",
        }

    expected_generation = json.loads(json.dumps(generation_result))
    expected_verification = json.loads(json.dumps(verification_report))

    record = provenance_tracker.write_attempt_record(
        component_id,
        generation_result,
        verification_report,
        spec_bundle_hash,
        repo_root,
    )

    # The returned record is built from the plain parameters directly.
    assert field(record, "component_id") == component_id
    assert field(record, "spec_bundle_hash") == spec_bundle_hash
    assert field(record, "generation") == expected_generation
    assert field(record, "verification") == expected_verification

    # And it was written to disk from those same parameters.
    attempt_dir = repo_root / ".hotdocs" / "attempts" / component_id
    assert attempt_dir.is_dir(), f"no attempt directory at {attempt_dir}"
    files = [p for p in attempt_dir.iterdir() if p.is_file()]
    assert len(files) == 1, f"expected exactly one attempt file, got {files}"
    on_disk = json.loads(files[0].read_text(encoding="utf-8"))
    assert on_disk["component_id"] == component_id
    assert on_disk["spec_bundle_hash"] == spec_bundle_hash
    assert on_disk["generation"] == expected_generation
    assert on_disk["verification"] == expected_verification
    assert on_disk["attempt_id"] == field(record, "attempt_id")