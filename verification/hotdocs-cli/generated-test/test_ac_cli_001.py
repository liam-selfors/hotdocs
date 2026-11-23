# hotdocs-criterion: sha256:c2c70b69db7327f9f5eee24a2c73c73333997e286011303d9189ade756af3425
import json
import os

import hotdocs_cli


VERB_ROWS = [
    # (verb words, dir, module, strip, model)
    (["lint"], "gen/spec-linter", "spec_linter", 1, "no"),
    (["impact"], "gen/impact-analyzer", "impact_analyzer", 1, "no"),
    (["assemble"], "gen/spec-bundle-assembler", "spec_bundle_assembler", 1, "no"),
    (["compile-criteria"], "pipeline/criterion-compiler", "criterion_compiler", 1, "no"),
    (["author-test"], "gen/test-author", "test_author", 0, "required"),
    (["verify-component"], "gen/verifier-orchestrator", "verifier_orchestrator", 1, "no"),
    (["generate"], "gen/component-gate-runner", "component_gate_runner", 0, "required"),
    (["verify"], "gen/provenance-tracker", "provenance_tracker", 0, "optional"),
    (["track", "feedback"], "gen/provenance-tracker", "provenance_tracker", 0, "no"),
    (["track", "ui", "build"], "gen/provenance-tracker-ui", "provenance_tracker_ui", 0, "optional"),
    (["provenance", "check"], "gen/provenance-checker", "provenance_checker", 1, "no"),
    (["provenance", "write"], "gen/provenance-writer", "provenance_writer", 0, "no"),
    (["license-scan"], "gen/license-scanner", "license_scanner", 1, "no"),
    (["secret-scan"], "gen/secret-scanner", "secret_scanner", 1, "no"),
    (["review-packet", "build"], "gen/review-packet-builder", "review_packet_builder", 0, "no"),
    (["decision-drift"], "gen/decision-drift-detector", "decision_drift_detector", 0, "no"),
    (["decision-impact"], "gen/decision-drift-detector", "decision_drift_detector", 0, "no"),
    (["docs-site", "build"], "gen/docs-site-renderer", "docs_site_renderer.cli", 2, "no"),
    (["corpus-graph", "build"], "gen/corpus-graph-builder", "corpus_graph_builder.cli", 1, "no"),
    (["assist"], "gen/spec-completeness-assistant", "spec_completeness_assistant", 1, "optional"),
    (["spec", "check"], "gen/spec-reviewer", "spec_reviewer", 2, "optional"),
    (["decision", "new"], "gen/spec-scaffolder", "spec_scaffolder", 0, "no"),
    (["decision", "ratify"], "gen/spec-scaffolder", "spec_scaffolder", 0, "no"),
    (["decision", "record-commit"], "gen/spec-scaffolder", "spec_scaffolder", 0, "no"),
    (["component", "new"], "gen/spec-scaffolder", "spec_scaffolder", 0, "no"),
    (["kind", "new"], "gen/spec-scaffolder", "spec_scaffolder", 0, "no"),
]


def fake_main_source(log_path, tag, body_tail):
    return (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "TAG = " + repr(tag) + "\n"
        "\n"
        "def main(argv=None):\n"
        "    tokens = list(argv) if argv is not None else None\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'fake': TAG, 'argv': tokens}) + '\\n')\n"
        + body_tail
    )


def write_fake(root, dir_, module, log_path, tag, body_tail="    return 7\n"):
    base = os.path.join(str(root), *dir_.split("/"))
    parts = module.split(".")
    target_dir = os.path.join(base, *parts[:-1])
    os.makedirs(target_dir, exist_ok=True)
    if len(parts) > 1:
        # create package __init__.py files along the way
        current = base
        for part in parts[:-1]:
            current = os.path.join(current, part)
            init = os.path.join(current, "__init__.py")
            if not os.path.exists(init):
                with open(init, "w", encoding="utf-8") as fh:
                    fh.write("")
    path = os.path.join(target_dir, parts[-1] + ".py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(fake_main_source(log_path, tag, body_tail))
    return path


def write_fake_llm_endpoint(root):
    base = os.path.join(str(root), "gen", "llm-endpoint")
    os.makedirs(base, exist_ok=True)
    config = {
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "base_url": None,
        "api_key_env": "ANTHROPIC_API_KEY",
        "timeout_seconds": 600,
        "auth": None,
    }
    src = (
        "def load_config(config_path=None):\n"
        "    return " + repr(config) + "\n"
    )
    with open(os.path.join(base, "llm_endpoint.py"), "w", encoding="utf-8") as fh:
        fh.write(src)


def read_log(log_path):
    if not os.path.exists(str(log_path)):
        return []
    with open(str(log_path), encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def clear_log(log_path):
    if os.path.exists(str(log_path)):
        os.remove(str(log_path))


def tag_for(dir_, module):
    return dir_ + ":" + module


def test_every_row_routes_with_strip_and_longest_prefix(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    log_path = project / "calls.log"

    written = set()
    for words, dir_, module, strip, model in VERB_ROWS:
        key = (dir_, module)
        if key in written:
            continue
        written.add(key)
        write_fake(project, dir_, module, log_path, tag_for(dir_, module))
    write_fake_llm_endpoint(project)

    root = os.path.abspath(str(project))
    repo_root_token = "--repo-root=" + root

    for words, dir_, module, strip, model in VERB_ROWS:
        clear_log(log_path)
        argv = list(words) + ["x", "--flag"]
        code = hotdocs_cli.run(
            list(argv), tool_root=str(tool_root), cwd=str(project), env={}
        )
        assert code == 7, (words, code)
        entries = read_log(log_path)
        assert len(entries) == 1, (words, entries)
        entry = entries[0]
        assert entry["fake"] == tag_for(dir_, module), (words, entry)
        received = entry["argv"]
        head = argv[strip:] + [repo_root_token]
        assert received[: len(head)] == head, (words, received)
        rest = received[len(head):]
        if model == "no":
            assert rest == [], (words, received)
        else:
            assert len(rest) <= 1, (words, received)
            for token in rest:
                assert token.startswith("--model="), (words, received)

    # Explicit examples from the criterion
    clear_log(log_path)
    assert hotdocs_cli.run(
        ["lint", "x", "--flag"], tool_root=str(tool_root), cwd=str(project), env={}
    ) == 7
    assert read_log(log_path)[0]["argv"] == ["x", "--flag", repo_root_token]

    clear_log(log_path)
    assert hotdocs_cli.run(
        ["docs-site", "build", "x", "--flag"],
        tool_root=str(tool_root), cwd=str(project), env={},
    ) == 7
    assert read_log(log_path)[0]["argv"] == ["x", "--flag", repo_root_token]

    clear_log(log_path)
    assert hotdocs_cli.run(
        ["generate", "x", "--flag"], tool_root=str(tool_root), cwd=str(project), env={}
    ) == 7
    received = read_log(log_path)[0]["argv"]
    assert received[:4] == ["generate", "x", "--flag", repo_root_token]

    # Longest prefix: "track ui build" never reached "track feedback"'s module
    clear_log(log_path)
    assert hotdocs_cli.run(
        ["track", "ui", "build", "x", "--flag"],
        tool_root=str(tool_root), cwd=str(project), env={},
    ) == 7
    entries = read_log(log_path)
    assert len(entries) == 1
    assert entries[0]["fake"] == tag_for("gen/provenance-tracker-ui", "provenance_tracker_ui")
    assert entries[0]["fake"] != tag_for("gen/provenance-tracker", "provenance_tracker")


def test_system_exit_codes_are_returned(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    log_path = project / "calls.log"
    counter_path = project / "count.txt"

    body_tail = (
        "    counter = " + repr(str(counter_path)) + "\n"
        "    try:\n"
        "        with open(counter, encoding='utf-8') as fh:\n"
        "            n = int(fh.read().strip() or '0')\n"
        "    except OSError:\n"
        "        n = 0\n"
        "    with open(counter, 'w', encoding='utf-8') as fh:\n"
        "        fh.write(str(n + 1))\n"
        "    codes = [3, None, 'boom']\n"
        "    raise SystemExit(codes[n])\n"
    )
    write_fake(project, "gen/spec-linter", "spec_linter", log_path, "exit", body_tail)

    results = []
    for _ in range(3):
        results.append(
            hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project), env={})
        )
    assert results == [3, 0, 1]
    assert len(read_log(log_path)) == 3


def test_two_projects_each_reach_their_own_fake(tmp_path):
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    project_a = tmp_path / "project_a"
    project_b = tmp_path / "project_b"
    project_a.mkdir()
    project_b.mkdir()
    log_a = project_a / "calls.log"
    log_b = project_b / "calls.log"
    write_fake(project_a, "gen/spec-linter", "spec_linter", log_a, "A")
    write_fake(project_b, "gen/spec-linter", "spec_linter", log_b, "B")

    assert hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project_a), env={}) == 7
    assert hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project_b), env={}) == 7

    entries_a = read_log(log_a)
    entries_b = read_log(log_b)
    assert [e["fake"] for e in entries_a] == ["A"]
    assert [e["fake"] for e in entries_b] == ["B"]

    # and back again: the first project's fake still runs, not the second's
    assert hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project_a), env={}) == 7
    assert [e["fake"] for e in read_log(log_a)] == ["A", "A"]
    assert [e["fake"] for e in read_log(log_b)] == ["B"]


def test_falls_back_to_tool_root_then_prefers_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    log_path = project / "calls.log"

    write_fake(tool_root, "gen/spec-linter", "spec_linter", log_path, "tool")

    code = hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project), env={})
    assert code == 7
    assert [e["fake"] for e in read_log(log_path)] == ["tool"]

    clear_log(log_path)
    write_fake(project, "gen/spec-linter", "spec_linter", log_path, "project")

    code = hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project), env={})
    assert code == 7
    assert [e["fake"] for e in read_log(log_path)] == ["project"]