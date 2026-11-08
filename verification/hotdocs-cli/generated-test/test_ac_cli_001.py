import json

import hotdocs_cli


ROWS = [
    (["lint"], "gen/spec-linter", "spec_linter", 1),
    (["impact"], "gen/impact-analyzer", "impact_analyzer", 1),
    (["assemble"], "gen/spec-bundle-assembler", "spec_bundle_assembler", 1),
    (["compile-criteria"], "pipeline/criterion-compiler", "criterion_compiler", 1),
    (["author-test"], "gen/test-author", "test_author", 0),
    (["verify-component"], "gen/verifier-orchestrator", "verifier_orchestrator", 1),
    (["generate"], "gen/component-gate-runner", "component_gate_runner", 0),
    (["verify"], "gen/provenance-tracker", "provenance_tracker", 0),
    (["track", "feedback"], "gen/provenance-tracker", "provenance_tracker", 0),
    (["track", "ui", "build"], "gen/provenance-tracker-ui", "provenance_tracker_ui", 0),
    (["provenance", "check"], "gen/provenance-checker", "provenance_checker", 1),
    (["provenance", "write"], "gen/provenance-writer", "provenance_writer", 0),
    (["license-scan"], "gen/license-scanner", "license_scanner", 1),
    (["secret-scan"], "gen/secret-scanner", "secret_scanner", 1),
    (["review-packet", "build"], "gen/review-packet-builder", "review_packet_builder", 0),
    (["decision-drift"], "gen/decision-drift-detector", "decision_drift_detector", 0),
    (["decision-impact"], "gen/decision-drift-detector", "decision_drift_detector", 0),
    (["docs-site", "build"], "gen/docs-site-renderer", "docs_site_renderer.cli", 2),
    (["corpus-graph", "build"], "gen/corpus-graph-builder", "corpus_graph_builder.cli", 1),
    (["assist"], "gen/spec-completeness-assistant", "spec_completeness_assistant", 1),
]


def _fake_source(log_path, marker=None, exit_code=7):
    write_expr = "json.dumps(argv)" if marker is None else repr(marker)
    return (
        "import json\n\n"
        "def main(argv):\n"
        "    with open(%r, 'a') as f:\n"
        "        f.write(%s + '\\n')\n"
        "    return %d\n"
    ) % (str(log_path), write_expr, exit_code)


def _write_fake_file(path, log_path, marker=None, exit_code=7):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_fake_source(log_path, marker=marker, exit_code=exit_code))


def _write_row_fake(project, dir_rel, module, log_path):
    base = project / dir_rel
    if "." in module:
        pkg, sub = module.split(".", 1)
        pkg_dir = base / pkg
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "__init__.py").write_text("")
        _write_fake_file(pkg_dir / f"{sub}.py", log_path)
    else:
        _write_fake_file(base / f"{module}.py", log_path)


def _log_path(project, dir_rel):
    return project / dir_rel / "calls.log"


def _line_count(path):
    return len(path.read_text().splitlines()) if path.exists() else 0


def test_dispatch_strip_and_longest_prefix(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    log_paths = {}
    for words, dir_rel, module, strip in ROWS:
        log_paths[dir_rel] = _log_path(project, dir_rel)

    for words, dir_rel, module, strip in ROWS:
        _write_row_fake(project, dir_rel, module, log_paths[dir_rel])

    for words, dir_rel, module, strip in ROWS:
        before_counts = {d: _line_count(p) for d, p in log_paths.items()}

        argv = list(words) + ["x", "--flag", f"--repo-root={project}"]
        exit_code = hotdocs_cli.main(argv, cwd=str(project))

        assert exit_code == 7, f"row {words!r} expected exit code 7, got {exit_code!r}"

        after_counts = {d: _line_count(p) for d, p in log_paths.items()}
        for d in log_paths:
            expected_delta = 1 if d == dir_rel else 0
            actual_delta = after_counts[d] - before_counts[d]
            assert actual_delta == expected_delta, (
                f"row {words!r}: expected only {dir_rel!r} to receive one new "
                f"call, but {d!r} changed by {actual_delta}"
            )

        last_line = log_paths[dir_rel].read_text().splitlines()[-1]
        got_tokens = json.loads(last_line)
        expected_tokens = argv[strip:]
        assert got_tokens == expected_tokens, (
            f"row {words!r}: expected tokens {expected_tokens!r}, got {got_tokens!r}"
        )


def test_system_exit_codes(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    fake_path = project / "gen" / "spec-linter" / "spec_linter.py"
    fake_path.parent.mkdir(parents=True)

    fake_path.write_text("def main(argv):\n    raise SystemExit(3)\n")
    assert hotdocs_cli.main(["lint", "ignored"], cwd=str(project)) == 3

    fake_path.write_text("def main(argv):\n    raise SystemExit(None)\n")
    assert hotdocs_cli.main(["lint", "ignored"], cwd=str(project)) == 0

    fake_path.write_text("def main(argv):\n    raise SystemExit('boom')\n")
    assert hotdocs_cli.main(["lint", "ignored"], cwd=str(project)) == 1


def test_routes_to_correct_project(tmp_path):
    project_a = tmp_path / "project_a"
    project_b = tmp_path / "project_b"
    project_a.mkdir()
    project_b.mkdir()

    log_a = project_a / "calls.log"
    log_b = project_b / "calls.log"

    _write_fake_file(
        project_a / "gen" / "spec-linter" / "spec_linter.py", log_a, marker="fake-one"
    )
    _write_fake_file(
        project_b / "gen" / "spec-linter" / "spec_linter.py", log_b, marker="fake-two"
    )

    hotdocs_cli.main(["lint", "x", f"--repo-root={project_a}"], cwd=str(project_a))
    hotdocs_cli.main(["lint", "x", f"--repo-root={project_b}"], cwd=str(project_b))

    assert log_a.read_text().splitlines() == ["fake-one"]
    assert log_b.read_text().splitlines() == ["fake-two"]


def test_tool_root_fallback_then_project_override(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()

    project_log = project / "calls.log"

    _write_fake_file(
        tool_root / "gen" / "spec-linter" / "spec_linter.py",
        project_log,
        marker="toolroot-fake",
    )

    assert not (project / "gen" / "spec-linter").exists()

    exit_code = hotdocs_cli.main(["lint"], tool_root=str(tool_root), cwd=str(project))
    assert exit_code == 7
    assert project_log.read_text().splitlines() == ["toolroot-fake"]

    _write_fake_file(
        project / "gen" / "spec-linter" / "spec_linter.py",
        project_log,
        marker="project-fake",
        exit_code=42,
    )

    exit_code = hotdocs_cli.main(["lint"], tool_root=str(tool_root), cwd=str(project))
    assert exit_code == 42
    assert project_log.read_text().splitlines() == ["toolroot-fake", "project-fake"]