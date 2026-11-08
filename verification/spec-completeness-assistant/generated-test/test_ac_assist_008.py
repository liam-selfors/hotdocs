import hashlib
import os
import tempfile
from pathlib import Path

import spec_completeness_assistant


def _get_field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _has_field(obj, name):
    if isinstance(obj, dict):
        return name in obj
    return hasattr(obj, name)


def _write_fake_dependencies(repo_root: Path):
    linter_dir = repo_root / "gen" / "spec-linter"
    linter_dir.mkdir(parents=True, exist_ok=True)
    (linter_dir / "spec_linter.py").write_text(
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    return {\n"
        "        'findings': [],\n"
        "        'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0},\n"
        "    }\n"
    )

    impact_dir = repo_root / "gen" / "impact-analyzer"
    impact_dir.mkdir(parents=True, exist_ok=True)
    (impact_dir / "impact_analyzer.py").write_text(
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': 'comp-foo', 'reason': 'direct', 'via': None},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    )

    assembler_dir = repo_root / "gen" / "spec-bundle-assembler"
    assembler_dir.mkdir(parents=True, exist_ok=True)
    (assembler_dir / "spec_bundle_assembler.py").write_text(
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:fake',\n"
        "        'spec': 'fake spec text',\n"
        "        'interface': 'fake interface text',\n"
        "        'constraints': 'fake constraints text',\n"
        "        'dependency_interfaces': {},\n"
        "        'dependency_context': {},\n"
        "        'dependency_usage': {},\n"
        "        'vars': {},\n"
        "        'glossary': 'fake glossary text',\n"
        "        'hint_code': {'spec_completeness_assistant.py': '# fake hint code'},\n"
        "    }\n"
    )


def _snapshot(repo_root: Path):
    snap = {}
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fname in files:
            full = Path(root) / fname
            rel = str(full.relative_to(repo_root))
            snap[rel] = hashlib.sha256(full.read_bytes()).hexdigest()
    return snap


def test_ac_assist_008_report_fields_and_no_filesystem_mutation():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _write_fake_dependencies(repo_root)

        before_snapshot = _snapshot(repo_root)

        report = spec_completeness_assistant.assist(["R-FOO-003"], repo_root)

        after_snapshot = _snapshot(repo_root)

        assert after_snapshot == before_snapshot, (
            "repo_root's files must be unchanged after assist() runs "
            "(ignoring __pycache__)"
        )

        for field_name in (
            "lint_findings",
            "predicted_blast_radius",
            "hint_previews",
            "completeness_score",
            "completeness_rationale",
            "redundancy_flags",
            "degraded",
        ):
            assert _has_field(report, field_name), (
                f"CompletenessReport must expose '{field_name}' "
                "(never silently omitted)"
            )

        assert _get_field(report, "lint_findings") == []

        predicted_blast_radius = _get_field(report, "predicted_blast_radius")
        assert list(predicted_blast_radius) == ["comp-foo"]

        hint_previews = _get_field(report, "hint_previews")
        for component_id in predicted_blast_radius:
            assert component_id in hint_previews
            assert hint_previews[component_id] is not None

        assert _get_field(report, "degraded") is True
        assert _get_field(report, "completeness_score") is None
        assert _get_field(report, "completeness_rationale") is None
        assert not _get_field(report, "redundancy_flags")