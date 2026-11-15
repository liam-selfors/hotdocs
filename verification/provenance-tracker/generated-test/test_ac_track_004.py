"""AC-TRACK-004 (Covers: R-TRACK-004).

write_attempt_record receives generation_result / verification_report as
plain-value parameters from component-gate-runner and writes the
AttemptRecord from them directly; this component never depends on
component-gate-runner's own ComponentPipelineResult type, confirmed by its
own depends_on list excluding comp-component-gate-runner.
"""

import inspect
import json
from pathlib import Path

import pytest

import provenance_tracker


FORBIDDEN_IDS = {"comp-component-gate-runner", "component-gate-runner"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_root() -> Path:
    here = Path(provenance_tracker.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    pytest.fail(
        "could not locate a 'gen' directory above provenance_tracker.__file__ "
        f"({here}) to derive the tool root"
    )


def _component_md() -> Path:
    root = _tool_root()
    path = root / "specs" / "components" / "provenance-tracker" / "component.md"
    assert path.is_file(), f"provenance-tracker's component.md not found at {path}"
    return path


def _frontmatter_lines(text: str) -> list[str]:
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---", "component.md has no frontmatter"
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            return out
        out.append(line)
    pytest.fail("component.md frontmatter is not terminated")


def _strip_item(item: str) -> str:
    item = item.strip()
    if "#" in item:
        item = item.split("#", 1)[0].strip()
    return item.strip().strip("'\"").strip()


def _depends_on(text: str) -> list[str] | None:
    """Return depends_on entries (flow or block style), or None if absent."""
    lines = _frontmatter_lines(text)
    for idx, line in enumerate(lines):
        if not line.startswith("depends_on"):
            continue
        key, _, rest = line.partition(":")
        if key.strip() != "depends_on":
            continue
        rest = rest.strip()
        if rest.startswith("["):
            inner = rest[1:]
            # allow flow lists continuing over following lines
            j = idx + 1
            while "]" not in inner and j < len(lines):
                inner += " " + lines[j].strip()
                j += 1
            inner = inner.split("]", 1)[0]
            return [s for s in (_strip_item(p) for p in inner.split(",")) if s]
        if rest in ("", "null", "~"):
            items = []
            for follow in lines[idx + 1:]:
                stripped = follow.strip()
                if stripped.startswith("- "):
                    items.append(_strip_item(stripped[2:]))
                elif stripped == "" or follow.startswith((" ", "\t")):
                    continue
                else:
                    break
            return [s for s in items if s]
        return [_strip_item(rest)] if _strip_item(rest) else []
    return None


def test_depends_on_excludes_component_gate_runner():
    text = _component_md().read_text(encoding="utf-8")
    deps = _depends_on(text)
    # An absent depends_on trivially excludes comp-component-gate-runner.
    deps = deps or []
    offending = [d for d in deps if d in FORBIDDEN_IDS]
    assert offending == [], (
        "provenance-tracker must not depend on component-gate-runner "
        f"(R-TRACK-004); depends_on = {deps}"
    )
    # Also guard against the dependency appearing anywhere in frontmatter
    # under some other spelling within the depends_on value line(s).
    for line in _frontmatter_lines(text):
        if line.strip().startswith("depends_on"):
            assert "component-gate-runner" not in line, line


def test_write_attempt_record_signature_takes_plain_parameters():
    sig = inspect.signature(provenance_tracker.write_attempt_record)
    names = list(sig.parameters)
    for expected in (
        "component_id",
        "generation_result",
        "verification_report",
        "spec_bundle_hash",
        "repo_root",
    ):
        assert expected in names, f"missing parameter {expected!r}: {names}"
    # No parameter carries a ComponentPipelineResult.
    for name in names:
        assert "pipeline" not in name.lower(), names


def _attempt_files(repo_root: Path) -> list[Path]:
    base = repo_root / ".hotdocs" / "attempts"
    if not base.exists():
        return []
    return sorted(p for p in base.rglob("*") if p.is_file())


def test_write_attempt_record_writes_from_plain_parameters(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    generation_result = {
        "component_id": "comp-foo",
        "model": "anthropic:claude-sonnet-5",
        "seed": 0,
        "model_call_error": None,
        "files": ["gen/foo/foo.py"],
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
        repo_root,
    )

    assert field(record, "component_id") == "comp-foo"
    assert field(record, "spec_bundle_hash") == spec_bundle_hash
    generation = field(record, "generation")
    verification = field(record, "verification")
    # Written from the parameters directly, in plain JSON-equivalent form.
    assert isinstance(generation, dict)
    assert isinstance(verification, dict)
    assert generation == generation_result
    assert verification == verification_report
    assert generation is not generation_result
    assert verification is not verification_report

    files = _attempt_files(repo_root)
    assert len(files) == 1, files
    on_disk = json.loads(files[0].read_text(encoding="utf-8"))
    assert on_disk["component_id"] == "comp-foo"
    assert on_disk["spec_bundle_hash"] == spec_bundle_hash
    assert on_disk["generation"] == generation_result
    assert on_disk["verification"] == verification_report


def test_write_attempt_record_accepts_null_verification(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    generation_result = {
        "component_id": "comp-foo",
        "model": "anthropic:claude-sonnet-5",
        "seed": 0,
        "model_call_error": {"category": "network", "message": "unreachable"},
        "files": [],
    }
    spec_bundle_hash = "sha256:" + "cd" * 32

    record = provenance_tracker.write_attempt_record(
        "comp-foo",
        generation_result,
        None,
        spec_bundle_hash,
        repo_root,
    )

    assert field(record, "verification") is None
    assert field(record, "generation") == generation_result

    files = _attempt_files(repo_root)
    assert len(files) == 1, files
    on_disk = json.loads(files[0].read_text(encoding="utf-8"))
    assert on_disk["verification"] is None
    assert on_disk["generation"] == generation_result