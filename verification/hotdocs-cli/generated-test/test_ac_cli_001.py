# hotdocs-criterion: sha256:b46b232c70836d243a55f3beea3b56f59536079d2c63c21eaac4d22cb7c40b60
import json
import os
from pathlib import Path

import hotdocs_cli


VERB_TABLE = [
    ("lint", "gen/spec-linter", "spec_linter", 1),
    ("impact", "gen/impact-analyzer", "impact_analyzer", 1),
    ("assemble", "gen/spec-bundle-assembler", "spec_bundle_assembler", 1),
    ("compile-criteria", "pipeline/criterion-compiler", "criterion_compiler", 1),
    ("author-test", "gen/test-author", "test_author", 0),
    ("verify-component", "gen/verifier-orchestrator", "verifier_orchestrator", 1),
    ("generate", "gen/component-gate-runner", "component_gate_runner", 0),
    ("verify", "gen/provenance-tracker", "provenance_tracker", 0),
    ("track feedback", "gen/provenance-tracker", "provenance_tracker", 0),
    ("track ui build", "gen/provenance-tracker-ui", "provenance_tracker_ui", 0),
    ("provenance check", "gen/provenance-checker", "provenance_checker", 1),
    ("provenance write", "gen/provenance-writer", "provenance_writer", 0),
    ("license-scan", "gen/license-scanner", "license_scanner", 1),
    ("secret-scan", "gen/secret-scanner", "secret_scanner", 1),
    ("review-packet build", "gen/review-packet-builder", "review_packet_builder", 0),
    ("decision-drift", "gen/decision-drift-detector", "decision_drift_detector", 0),
    ("decision-impact", "gen/decision-drift-detector", "decision_drift_detector", 0),
    ("docs-site build", "gen/docs-site-renderer", "docs_site_renderer.cli", 2),
    ("corpus-graph build", "gen/corpus-graph-builder", "corpus_graph_builder.cli", 1),
    ("assist", "gen/spec-completeness-assistant", "spec_completeness_assistant", 1),
    ("spec check", "gen/spec-reviewer", "spec_reviewer", 2),
    ("decision new", "gen/spec-scaffolder", "spec_scaffolder", 0),
    ("decision ratify", "gen/spec-scaffolder", "spec_scaffolder", 0),
    ("decision record-commit", "gen/spec-scaffolder", "spec_scaffolder", 0),
    ("component new", "gen/spec-scaffolder", "spec_scaffolder", 0),
    ("kind new", "gen/spec-scaffolder", "spec_scaffolder", 0),
]


def _quiet(*args, **kwargs):
    return None


def _fake_main_source(log_path, tag):
    return (
        "import json\n"
        "\n"
        "def main(argv=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "        f.write(json.dumps({'fake': " + repr(tag) + ", 'argv': argv}) + '\\n')\n"
        "    return 7\n"
    )


def _module_file(root, dir_, module):
    base = Path(root) / dir_
    if "." in module:
        parts = module.split(".")
        pkg_dir = base
        for part in parts[:-1]:
            pkg_dir = pkg_dir / part
            pkg_dir.mkdir(parents=True, exist_ok=True)
            init = pkg_dir / "__init__.py"
            if not init.exists():
                init.write_text("")
        return pkg_dir / (parts[-1] + ".py")
    base.mkdir(parents=True, exist_ok=True)
    return base / (module + ".py")


def _write_fake(root, dir_, module, log_path, tag):
    path = _module_file(root, dir_, module)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_fake_main_source(log_path, tag))
    return path


def _write_fake_llm_endpoint(project):
    d = Path(project) / "gen" / "llm-endpoint"
    d.mkdir(parents=True, exist_ok=True)
    (d / "llm_endpoint.py").write_text(
        "def load_config(config_path=None):\n"
        "    return None\n"
    )


def _read_log(log_path):
    p = Path(log_path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def _run(argv, project, tool_root):
    return hotdocs_cli.run(
        argv,
        tool_root=str(tool_root),
        cwd=str(project),
        env={},
        output_fn=_quiet,
        input_fn=lambda *a, **k: "",
    )


def test_each_row_routes_with_strip_and_longest_prefix(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    log_path = project / "calls.log"
    _write_fake_llm_endpoint(project)

    for words, dir_, module, strip in VERB_TABLE:
        _write_fake(project, dir_, module, log_path, module)

    repo_root_token = "--repo-root=" + os.path.abspath(str(project))

    for words, dir_, module, strip in VERB_TABLE:
        if log_path.exists():
            log_path.unlink()
        argv = words.split() + ["x", "--flag"]
        code = _run(list(argv), project, tool_root)
        assert code == 7, (words, code)
        calls = _read_log(log_path)
        assert len(calls) == 1, (words, calls)
        assert calls[0]["fake"] == module, (words, calls)
        expected = argv[strip:] + [repo_root_token]
        assert calls[0]["argv"] == expected, (words, calls[0]["argv"], expected)

    # Spot checks spelled out by the criterion.
    if log_path.exists():
        log_path.unlink()
    assert _run(["lint", "x", "--flag"], project, tool_root) == 7
    assert _read_log(log_path)[0]["argv"] == ["x", "--flag", repo_root_token]

    if log_path.exists():
        log_path.unlink()
    assert _run(["generate", "x", "--flag"], project, tool_root) == 7
    assert _read_log(log_path)[0]["argv"] == ["generate", "x", "--flag", repo_root_token]

    if log_path.exists():
        log_path.unlink()
    assert _run(["docs-site", "build", "x", "--flag"], project, tool_root) == 7
    assert _read_log(log_path)[0]["argv"] == ["x", "--flag", repo_root_token]

    if log_path.exists():
        log_path.unlink()
    assert _run(["track", "ui", "build", "x", "--flag"], project, tool_root) == 7
    calls = _read_log(log_path)
    assert len(calls) == 1
    assert calls[0]["fake"] == "provenance_tracker_ui"
    assert calls[0]["argv"] == ["track", "ui", "build", "x", "--flag", repo_root_token]


def test_system_exit_codes_are_caught_and_returned(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    counter = project / "counter.txt"
    d = project / "gen" / "spec-linter"
    d.mkdir(parents=True)
    (d / "spec_linter.py").write_text(
        "import os\n"
        "\n"
        "def main(argv=None):\n"
        "    path = " + repr(str(counter)) + "\n"
        "    n = 0\n"
        "    if os.path.exists(path):\n"
        "        with open(path) as f:\n"
        "            n = int(f.read().strip() or '0')\n"
        "    with open(path, 'w') as f:\n"
        "        f.write(str(n + 1))\n"
        "    codes = [3, None, 'boom']\n"
        "    raise SystemExit(codes[n])\n"
    )

    assert _run(["lint"], project, tool_root) == 3
    assert _run(["lint"], project, tool_root) == 0
    assert _run(["lint"], project, tool_root) == 1
    assert counter.read_text().strip() == "3"


def test_two_projects_each_reach_their_own_fake(tmp_path):
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    project_a = tmp_path / "project_a"
    project_b = tmp_path / "project_b"
    project_a.mkdir()
    project_b.mkdir()
    log_a = project_a / "calls.log"
    log_b = project_b / "calls.log"
    _write_fake(project_a, "gen/spec-linter", "spec_linter", log_a, "fake-A")
    _write_fake(project_b, "gen/spec-linter", "spec_linter", log_b, "fake-B")

    assert _run(["lint"], project_a, tool_root) == 7
    assert _run(["lint"], project_b, tool_root) == 7
    assert _run(["lint"], project_a, tool_root) == 7

    calls_a = _read_log(log_a)
    calls_b = _read_log(log_b)
    assert [c["fake"] for c in calls_a] == ["fake-A", "fake-A"]
    assert [c["fake"] for c in calls_b] == ["fake-B"]


def test_falls_back_to_tool_root_until_project_has_its_own(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    log_path = project / "calls.log"

    assert not (project / "gen" / "spec-linter").exists()
    _write_fake(tool_root, "gen/spec-linter", "spec_linter", log_path, "tool-root-fake")

    assert _run(["lint"], project, tool_root) == 7
    calls = _read_log(log_path)
    assert len(calls) == 1
    assert calls[0]["fake"] == "tool-root-fake"

    log_path.unlink()
    _write_fake(project, "gen/spec-linter", "spec_linter", log_path, "project-fake")

    assert _run(["lint"], project, tool_root) == 7
    calls = _read_log(log_path)
    assert len(calls) == 1
    assert calls[0]["fake"] == "project-fake"