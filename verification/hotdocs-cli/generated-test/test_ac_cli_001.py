# hotdocs-criterion: sha256:8130c1cdc57dd34140841a05e5904caf0657823f8fd40069349c85ac65dc091d
import json
import os

import hotdocs_cli


# Verb table rows, every row except "init": (verb words, dir, module, strip)
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _quiet(*args, **kwargs):
    pass


def fake_main_source(log_path, tag, ret=7):
    return (
        "import json\n"
        "def main(argv=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "        f.write(json.dumps({'tag': " + repr(tag) + ", 'argv': argv}) + '\\n')\n"
        "    return " + repr(ret) + "\n"
    )


def write_module(root, rel_dir, module, source):
    base = os.path.join(str(root), *rel_dir.split("/"))
    parts = module.split(".")
    if len(parts) == 1:
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, module + ".py")
    else:
        pkg_dir = os.path.join(base, *parts[:-1])
        os.makedirs(pkg_dir, exist_ok=True)
        # make every package level importable
        d = base
        for p in parts[:-1]:
            d = os.path.join(d, p)
            init = os.path.join(d, "__init__.py")
            if not os.path.exists(init):
                with open(init, "w") as f:
                    f.write("")
        path = os.path.join(pkg_dir, parts[-1] + ".py")
    with open(path, "w") as f:
        f.write(source)
    return path


def write_fake_llm_endpoint(project):
    src = (
        "def load_config(config_path=None):\n"
        "    return None\n"
    )
    write_module(project, "gen/llm-endpoint", "llm_endpoint", src)


def read_log(log_path):
    if not os.path.exists(str(log_path)):
        return []
    with open(str(log_path)) as f:
        return [json.loads(line) for line in f.read().splitlines() if line.strip()]


def clear_log(log_path):
    if os.path.exists(str(log_path)):
        os.remove(str(log_path))


def test_every_row_routes_with_strip_and_longest_prefix(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    log_path = project / "calls.log"

    written = set()
    for words, rel_dir, module, strip in ROWS:
        key = (rel_dir, module)
        if key in written:
            continue
        written.add(key)
        write_module(project, rel_dir, module,
                     fake_main_source(log_path, rel_dir + "::" + module))
    write_fake_llm_endpoint(project)

    root_token = "--repo-root=" + os.path.abspath(str(project))

    for words, rel_dir, module, strip in ROWS:
        clear_log(log_path)
        argv = list(words) + ["x", "--flag"]
        code = hotdocs_cli.run(argv, tool_root=str(tool_root), cwd=str(project),
                               output_fn=_quiet)
        entries = read_log(log_path)
        assert len(entries) == 1, (words, entries)
        entry = entries[0]
        assert entry["tag"] == rel_dir + "::" + module, (words, entry)
        expected = argv[strip:] + [root_token]
        assert entry["argv"] == expected, (words, entry["argv"], expected)
        assert code == 7, (words, code)

    # explicit spot checks from the criterion
    clear_log(log_path)
    hotdocs_cli.run(["lint", "x", "--flag"], tool_root=str(tool_root),
                    cwd=str(project), output_fn=_quiet)
    assert read_log(log_path)[0]["argv"] == ["x", "--flag", root_token]

    clear_log(log_path)
    hotdocs_cli.run(["generate", "x", "--flag"], tool_root=str(tool_root),
                    cwd=str(project), output_fn=_quiet)
    assert read_log(log_path)[0]["argv"] == ["generate", "x", "--flag", root_token]

    clear_log(log_path)
    hotdocs_cli.run(["docs-site", "build", "x", "--flag"], tool_root=str(tool_root),
                    cwd=str(project), output_fn=_quiet)
    assert read_log(log_path)[0]["argv"] == ["x", "--flag", root_token]

    # longest prefix: "track ui build" never reaches "track feedback"'s module
    clear_log(log_path)
    code = hotdocs_cli.run(["track", "ui", "build", "x", "--flag"],
                           tool_root=str(tool_root), cwd=str(project), output_fn=_quiet)
    entries = read_log(log_path)
    assert code == 7
    assert len(entries) == 1
    assert entries[0]["tag"] == "gen/provenance-tracker-ui::provenance_tracker_ui"
    assert entries[0]["argv"] == ["track", "ui", "build", "x", "--flag", root_token]


def test_system_exit_codes_are_returned(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    counter = project / "counter.txt"
    log_path = project / "calls.log"
    src = (
        "import json, os\n"
        "def main(argv=None):\n"
        "    counter = " + repr(str(counter)) + "\n"
        "    n = 0\n"
        "    if os.path.exists(counter):\n"
        "        with open(counter) as f:\n"
        "            n = int(f.read().strip() or '0')\n"
        "    with open(counter, 'w') as f:\n"
        "        f.write(str(n + 1))\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "        f.write(json.dumps({'tag': 'exit', 'argv': argv}) + '\\n')\n"
        "    codes = " + repr([3, None, "boom"]) + "\n"
        "    raise SystemExit(codes[n])\n"
    )
    write_module(project, "gen/spec-linter", "spec_linter", src)

    results = []
    for _ in range(3):
        results.append(hotdocs_cli.run(["lint"], tool_root=str(tool_root),
                                       cwd=str(project), output_fn=_quiet))
    assert results == [3, 0, 1]
    assert len(read_log(log_path)) == 3


def test_two_projects_each_reach_their_own_fake(tmp_path):
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    proj_a = tmp_path / "a"
    proj_b = tmp_path / "b"
    proj_a.mkdir()
    proj_b.mkdir()
    log_a = proj_a / "calls.log"
    log_b = proj_b / "calls.log"
    write_module(proj_a, "gen/spec-linter", "spec_linter",
                 fake_main_source(log_a, "fake-a"))
    write_module(proj_b, "gen/spec-linter", "spec_linter",
                 fake_main_source(log_b, "fake-b"))

    code_a = hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(proj_a),
                             output_fn=_quiet)
    code_b = hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(proj_b),
                             output_fn=_quiet)
    assert code_a == 7
    assert code_b == 7

    entries_a = read_log(log_a)
    entries_b = read_log(log_b)
    assert [e["tag"] for e in entries_a] == ["fake-a"]
    assert [e["tag"] for e in entries_b] == ["fake-b"]


def test_tool_root_fallback_then_project_fake(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    log_path = project / "calls.log"

    write_module(tool_root, "gen/spec-linter", "spec_linter",
                 fake_main_source(log_path, "tool-root-fake"))
    assert not os.path.exists(os.path.join(str(project), "gen", "spec-linter"))

    code = hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project),
                           output_fn=_quiet)
    assert code == 7
    entries = read_log(log_path)
    assert [e["tag"] for e in entries] == ["tool-root-fake"]

    clear_log(log_path)
    write_module(project, "gen/spec-linter", "spec_linter",
                 fake_main_source(log_path, "project-fake"))
    code = hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project),
                           output_fn=_quiet)
    assert code == 7
    entries = read_log(log_path)
    assert [e["tag"] for e in entries] == ["project-fake"]