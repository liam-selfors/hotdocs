from pathlib import Path

import provenance_tracker


def _get(obj, field):
    return obj[field] if isinstance(obj, dict) else getattr(obj, field)


def _find_repo_root():
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "specs" / "components").is_dir():
            return current
        if current.parent == current:
            break
        current = current.parent
    raise RuntimeError("could not locate repo root from test file location")


def _parse_depends_on(component_md_text):
    lines = component_md_text.splitlines()
    assert lines and lines[0].strip() == "---", "expected frontmatter delimiter"
    end = lines.index("---", 1)
    for line in lines[1:end]:
        stripped = line.strip()
        if stripped.startswith("depends_on:"):
            value = stripped[len("depends_on:"):].strip()
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                if not inner:
                    return []
                return [item.strip().strip('"\'') for item in inner.split(",")]
            return []
    return []


def test_write_attempt_record_persists_plain_parameters_directly(tmp_path):
    component_id = "comp-foo"
    generation_result = {
        "model": "gpt-5",
        "seed": 0,
        "prompt_version": "v1",
        "model_call_error": None,
        "candidate_path": "gen/foo/foo.py",
    }
    verification_report = {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
    spec_bundle_hash = "sha256:deadbeef"

    # gen/component-gate-runner does not exist anywhere under this repo_root;
    # if write_attempt_record resolved a dependency on component-gate-runner's
    # own result type, this call would fail trying to load a missing module.
    record = provenance_tracker.write_attempt_record(
        component_id,
        generation_result,
        verification_report,
        spec_bundle_hash,
        tmp_path,
    )

    assert _get(record, "component_id") == component_id
    assert _get(record, "spec_bundle_hash") == spec_bundle_hash
    assert _get(record, "generation") == generation_result
    assert _get(record, "verification") == verification_report
    assert _get(record, "attempt_id")

    attempts_dir = tmp_path / ".hotdocs" / "attempts" / component_id
    assert attempts_dir.is_dir()
    written_files = list(attempts_dir.glob("*"))
    assert len(written_files) == 1


def test_provenance_tracker_depends_on_excludes_component_gate_runner():
    repo_root = _find_repo_root()
    component_md_path = repo_root / "specs" / "components" / "provenance-tracker" / "component.md"
    assert component_md_path.is_file(), f"expected component.md at {component_md_path}"

    depends_on = _parse_depends_on(component_md_path.read_text())

    assert depends_on, "expected comp-provenance-tracker to declare at least one real dependency"
    assert "comp-component-gate-runner" not in depends_on