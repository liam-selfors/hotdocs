import hashlib
import json
import os
from pathlib import Path

import spec_completeness_assistant


_MISSING = object()


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _snapshot(root: Path):
    snap = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            rel = str(fpath.relative_to(root))
            snap[rel] = hashlib.sha256(fpath.read_bytes()).hexdigest()
    return snap


FAKE_SPEC_LINTER_TEMPLATE = """
import json

LOG_FILE = __LOG_FILE__


def _record(call):
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(call) + "\\n")


def lint(paths, repo_root, strict=False, judge=None):
    _record({"module": "spec-linter", "repo_root": str(repo_root)})
    return {
        "findings": [],
        "summary": {"hard_failures": 0, "warnings": 0, "skipped": 0},
    }
"""


FAKE_IMPACT_ANALYZER_TEMPLATE = """
import json

LOG_FILE = __LOG_FILE__


def _record(call):
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(call) + "\\n")


def compute_blast_radius(changed_ids, repo_root):
    _record({
        "module": "impact-analyzer",
        "changed_ids": list(changed_ids),
        "repo_root": str(repo_root),
    })
    return {
        "impacted": [
            {"component_id": "comp-foo", "reason": "direct", "via": None}
        ],
        "precondition_error": None,
    }
"""


FAKE_SPEC_BUNDLE_ASSEMBLER_TEMPLATE = """
import json

LOG_FILE = __LOG_FILE__


def _record(call):
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(call) + "\\n")


def assemble(component_id, repo_root, mode="cold"):
    _record({
        "module": "spec-bundle-assembler",
        "component_id": component_id,
        "mode": mode,
        "repo_root": str(repo_root),
    })
    hint_code = None
    if mode == "hint":
        hint_code = {"spec_bundle_assembler.py": "# fake hint code"}
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:deadbeefdeadbeef",
        "spec": "fake spec body for " + component_id,
        "interface": "fake interface body",
        "constraints": "fake constraints body",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "fake glossary body",
        "hint_code": hint_code,
    }
"""


def _write_fake_dependency(repo_root: Path, slug: str, module_basename: str, template: str, log_file: Path):
    module_dir = repo_root / "gen" / slug
    module_dir.mkdir(parents=True, exist_ok=True)
    source = template.replace("__LOG_FILE__", repr(str(log_file)))
    (module_dir / (module_basename + ".py")).write_text(source)


def test_assist_exposes_decision_fields_and_leaves_repo_root_unchanged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "invocations.log"

    _write_fake_dependency(
        repo_root, "spec-linter", "spec_linter", FAKE_SPEC_LINTER_TEMPLATE, log_file
    )
    _write_fake_dependency(
        repo_root,
        "impact-analyzer",
        "impact_analyzer",
        FAKE_IMPACT_ANALYZER_TEMPLATE,
        log_file,
    )
    _write_fake_dependency(
        repo_root,
        "spec-bundle-assembler",
        "spec_bundle_assembler",
        FAKE_SPEC_BUNDLE_ASSEMBLER_TEMPLATE,
        log_file,
    )

    snapshot_before = _snapshot(repo_root)

    report = spec_completeness_assistant.assist(["R-FOO-003"], repo_root)

    snapshot_after = _snapshot(repo_root)
    assert snapshot_after == snapshot_before, (
        "repo_root's files must be unchanged (ignoring __pycache__) after assist() runs"
    )

    for field in (
        "lint_findings",
        "predicted_blast_radius",
        "hint_previews",
        "completeness_score",
        "completeness_rationale",
        "redundancy_flags",
        "degraded",
    ):
        assert _get(report, field, _MISSING) is not _MISSING, (
            f"CompletenessReport is missing field {field!r} needed by a calling "
            "tool to record an accept/override decision"
        )

    assert _get(report, "degraded") == True  # noqa: E712
    assert _get(report, "completeness_score") is None
    assert _get(report, "completeness_rationale") in (None, "")
    assert _get(report, "redundancy_flags") in (None, [])
    assert _get(report, "lint_findings") == []
    assert _get(report, "predicted_blast_radius") == ["comp-foo"]

    hint_previews = _get(report, "hint_previews")
    assert hint_previews is not None
    assert _get(hint_previews, "comp-foo", _MISSING) is not _MISSING
    assert _get(hint_previews, "comp-foo")

    if log_file.exists():
        calls = [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]
    else:
        calls = []

    modules_called = {call["module"] for call in calls}
    assert "spec-linter" in modules_called
    assert "impact-analyzer" in modules_called
    assert "spec-bundle-assembler" in modules_called

    assemble_calls = [c for c in calls if c["module"] == "spec-bundle-assembler"]
    assert any(
        c["component_id"] == "comp-foo" and c["mode"] == "hint" for c in assemble_calls
    )