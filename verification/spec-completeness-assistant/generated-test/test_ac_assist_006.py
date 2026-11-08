import spec_completeness_assistant


def _get(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _has(obj, name):
    if isinstance(obj, dict):
        return name in obj
    return hasattr(obj, name)


LINTER_SRC_TEMPLATE = """LOG_FILE = "__LOG_FILE__"


def lint(paths, repo_root, strict=False, judge=None):
    with open(LOG_FILE, "a") as f:
        f.write("lint\\n")
    return {
        "findings": [],
        "summary": {"hard_failures": 0, "warnings": 0, "skipped": 0},
    }
"""

IMPACT_SRC_TEMPLATE = """LOG_FILE = "__LOG_FILE__"


def compute_blast_radius(changed_ids, repo_root):
    with open(LOG_FILE, "a") as f:
        f.write("compute_blast_radius\\n")
    return {
        "impacted": [
            {"component_id": "comp-foo", "reason": "direct", "via": None},
        ],
        "precondition_error": None,
    }
"""

ASSEMBLER_SRC_TEMPLATE = """LOG_FILE = "__LOG_FILE__"


def assemble(component_id, repo_root, mode="cold"):
    with open(LOG_FILE, "a") as f:
        f.write("assemble:" + component_id + ":" + mode + "\\n")
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:deadbeef",
        "spec": "# Foo\\n\\nFoo MUST do a foo thing.\\n",
        "interface": "# CLI\\n\\nNone.\\n",
        "constraints": "No additional constraints.\\n",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": {"spec_linter.py": "# placeholder\\n"} if mode == "hint" else None,
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    with open(LOG_FILE, "a") as f:
        f.write("assemble_criterion:" + component_id + ":" + criterion_id + "\\n")
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-FOO-001",
        "criterion_text": "",
        "requirement_text": "",
        "interface": "",
        "glossary": "",
    }
"""


def test_assist_output_is_advisory_only_and_never_gates(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "interface").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)

    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo Component\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo.py\n"
        "last_ratified_commit: 0000000\n"
        "depends_on: [comp-bar]\n"
        "---\n\n"
        "# Foo\n\n"
        "Purpose: a fixture component unrelated to the assistant under test.\n"
    )

    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n"
        "Foo MUST do a foo thing.\n"
    )

    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given foo\n"
        "When foo happens\n"
        "Then foo is done\n"
        "```\n"
    )

    (comp_dir / "interface" / "cli.md").write_text(
        "# CLI\n\nNone.\n"
    )

    (comp_dir / "constraints.md").write_text(
        "No additional constraints.\n"
    )

    log_file = tmp_path / "invocations.log"

    gen_dir = repo_root / "gen"

    linter_dir = gen_dir / "spec-linter"
    linter_dir.mkdir(parents=True)
    (linter_dir / "spec_linter.py").write_text(
        LINTER_SRC_TEMPLATE.replace("__LOG_FILE__", str(log_file))
    )

    impact_dir = gen_dir / "impact-analyzer"
    impact_dir.mkdir(parents=True)
    (impact_dir / "impact_analyzer.py").write_text(
        IMPACT_SRC_TEMPLATE.replace("__LOG_FILE__", str(log_file))
    )

    assembler_dir = gen_dir / "spec-bundle-assembler"
    assembler_dir.mkdir(parents=True)
    (assembler_dir / "spec_bundle_assembler.py").write_text(
        ASSEMBLER_SRC_TEMPLATE.replace("__LOG_FILE__", str(log_file))
    )

    def _no_exit(*args, **kwargs):
        raise AssertionError("assist() must never call sys.exit")

    import sys
    monkeypatch.setattr(sys, "exit", _no_exit)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    assert report is not None

    assert log_file.exists()
    log_contents = log_file.read_text()
    assert "lint" in log_contents
    assert "compute_blast_radius" in log_contents
    assert "assemble:comp-foo:hint" in log_contents

    lint_findings = _get(report, "lint_findings")
    predicted_blast_radius = _get(report, "predicted_blast_radius")
    hint_previews = _get(report, "hint_previews")
    completeness_score = _get(report, "completeness_score")
    completeness_rationale = _get(report, "completeness_rationale")
    redundancy_flags = _get(report, "redundancy_flags")
    degraded = _get(report, "degraded")

    assert lint_findings == []
    assert predicted_blast_radius == ["comp-foo"]
    assert isinstance(hint_previews, dict)
    assert degraded is True
    assert completeness_score is None
    assert completeness_rationale is None
    assert redundancy_flags in (None, [])

    blocking_names = [
        "block",
        "fail",
        "exit",
        "abort",
        "gate",
        "should_fail",
        "should_block",
        "is_blocking",
        "blocking",
        "hard_fail",
        "raise_error",
        "halt",
        "raise_for_status",
    ]
    for name in blocking_names:
        assert not _has(report, name), (
            "CompletenessReport must not expose field or method '%s' "
            "that could block, fail, or exit anything" % name
        )