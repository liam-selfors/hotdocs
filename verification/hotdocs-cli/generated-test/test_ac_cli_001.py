# hotdocs-criterion: sha256:bfdfacded349d688d9c750c59543dcaedcb135a4b4d05a3322b7b60a14ff25b8
import json
import os

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
    (["spec", "check"], "gen/spec-reviewer", "spec_reviewer", 2),
    (["decision", "new"], "gen/spec-scaffolder", "spec_scaffolder", 0),
    (["decision", "ratify"], "gen/spec-scaffolder", "spec_scaffolder", 0),
    (["decision", "record-commit"], "gen/spec-scaffolder", "spec_scaffolder", 0),
    (["component", "new"], "gen/spec-scaffolder", "spec_scaffolder", 0),
    (["kind", "new"], "gen/spec-scaffolder", "spec_scaffolder", 0),
    (["capability", "new"], "gen/spec-scaffolder", "spec_scaffolder", 0),
]


def fake_main_source(calls_log, which_log, tag, body_tail):
    nl = repr("\n")
    return (
        "import json\n"
        "def main(argv=None):\n"
        "    with open(" + repr(str(calls_log)) + ", 'a') as f:\n"
        "        f.write(json.dumps(argv) + " + nl + ")\n"
        "    with open(" + repr(str(which_log)) + ", 'a') as f:\n"
        "        f.write(" + repr(tag) + " + " + nl + ")\n"
        + body_tail
    )


def write_fake(root, rel_dir, module, calls_log, which_log, tag, body_tail="    return 7\n"):
    base = root / rel_dir
    parts = module.split(".")
    target_dir = base
    for pkg in parts[:-1]:
        target_dir = target_dir / pkg
        target_dir.mkdir(parents=True, exist_ok=True)
        init = target_dir / "__init__.py"
        if not init.exists():
            init.write_text("")
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / (parts[-1] + ".py")
    path.write_text(fake_main_source(calls_log, which_log, tag, body_tail))
    return path


def write_fake_llm_endpoint(project):
    d = project / "gen" / "llm-endpoint"
    d.mkdir(parents=True, exist_ok=True)
    (d / "llm_endpoint.py").write_text(
        "def load_config(config_path=None):\n"
        "    return None\n"
    )


def read_lines(path):
    if not path.exists():
        return []
    return [line for line in path.read_text().splitlines() if line.strip()]


def call_run(argv, project, tool_root):
    outputs = []
    return hotdocs_cli.run(
        argv,
        tool_root=str(tool_root),
        input_fn=lambda *a, **k: "",
        output_fn=lambda *a, **k: outputs.append(a),
        env={},
        cwd=str(project),
    )


def test_each_row_dispatches_with_strip_and_longest_prefix(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    calls_log = project / "calls.log"
    which_log = project / "which.log"
    write_fake_llm_endpoint(project)
    for words, rel_dir, module, strip in ROWS:
        write_fake(project, rel_dir, module, calls_log, which_log, module)

    repo_token = "--repo-root=" + os.path.abspath(str(project))

    for words, rel_dir, module, strip in ROWS:
        if calls_log.exists():
            calls_log.unlink()
        if which_log.exists():
            which_log.unlink()
        argv = list(words) + ["x", "--flag"]
        rc = call_run(argv, project, tool_root)
        assert rc == 7, (words, rc)
        lines = read_lines(calls_log)
        assert len(lines) == 1, (words, lines)
        received = json.loads(lines[0])
        expected = argv[strip:] + [repo_token]
        assert received[: len(expected)] == expected, (words, received)
        rest = received[len(expected):]
        assert all(t.startswith("--model=") for t in rest), (words, received)
        assert read_lines(which_log) == [module], (words, read_lines(which_log))

    # Longest prefix: "track ui build" reaches provenance_tracker_ui, never provenance_tracker.
    for p in (calls_log, which_log):
        if p.exists():
            p.unlink()
    rc = call_run(["track", "ui", "build", "x", "--flag"], project, tool_root)
    assert rc == 7
    assert read_lines(which_log) == ["provenance_tracker_ui"]


def test_system_exit_codes_are_returned(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    calls_log = project / "calls.log"
    which_log = project / "which.log"
    counter = project / "counter.txt"
    counter.write_text("0")
    nl = repr("\n")
    tail = (
        "    with open(" + repr(str(counter)) + ") as f:\n"
        "        n = int(f.read().strip() or '0')\n"
        "    with open(" + repr(str(counter)) + ", 'w') as f:\n"
        "        f.write(str(n + 1))\n"
        "    codes = [3, None, 'boom']\n"
        "    raise SystemExit(codes[n])\n"
    )
    assert nl  # keeps repr usage consistent
    write_fake(project, "gen/spec-linter", "spec_linter", calls_log, which_log, "exit", tail)

    results = [call_run(["lint"], project, tool_root) for _ in range(3)]
    assert results == [3, 0, 1]
    assert len(read_lines(which_log)) == 3


def test_two_projects_each_reach_their_own_fake(tmp_path):
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    shared_which = tmp_path / "which.log"
    project_a = tmp_path / "a"
    project_b = tmp_path / "b"
    project_a.mkdir()
    project_b.mkdir()
    write_fake(project_a, "gen/spec-linter", "spec_linter", project_a / "calls.log", shared_which, "A")
    write_fake(project_b, "gen/spec-linter", "spec_linter", project_b / "calls.log", shared_which, "B")

    assert call_run(["lint"], project_a, tool_root) == 7
    assert read_lines(shared_which) == ["A"]
    assert call_run(["lint"], project_b, tool_root) == 7
    assert read_lines(shared_which) == ["A", "B"]
    assert len(read_lines(project_a / "calls.log")) == 1
    assert len(read_lines(project_b / "calls.log")) == 1


def test_falls_back_to_tool_root_then_prefers_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    calls_log = project / "calls.log"
    which_log = project / "which.log"
    write_fake(tool_root, "gen/spec-linter", "spec_linter", calls_log, which_log, "tool")
    assert not (project / "gen" / "spec-linter").exists()

    rc = call_run(["lint"], project, tool_root)
    assert rc == 7
    assert read_lines(which_log) == ["tool"]
    assert len(read_lines(calls_log)) == 1

    write_fake(project, "gen/spec-linter", "spec_linter", calls_log, which_log, "project")
    rc = call_run(["lint"], project, tool_root)
    assert rc == 7
    assert read_lines(which_log) == ["tool", "project"]
    assert len(read_lines(calls_log)) == 2