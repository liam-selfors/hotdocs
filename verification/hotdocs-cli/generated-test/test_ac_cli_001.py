# hotdocs-criterion: sha256:4db9d0484d9a17d7438f9915975f8e7f630066e0514f6dcf575fa0e9d4eacfd5
import json
import os
from pathlib import Path

import hotdocs_cli


VERB_ROWS = [
    ("lint", "gen/spec-linter", "spec_linter", 1),
    ("impact", "gen/impact-analyzer", "impact_analyzer", 1),
    ("assemble", "gen/spec-bundle-assembler", "spec_bundle_assembler", 1),
    ("compile-criteria", "pipeline/criterion-compiler", "criterion_compiler", 1),
    ("author-test", "gen/test-author", "test_author", 1),
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
    ("capability new", "gen/spec-scaffolder", "spec_scaffolder", 0),
]


def _env():
    return {"PATH": os.environ.get("PATH", "")}


def _fake_main_source(log_path, return_code, tag_path=None, tag=None):
    src = "import json\n"
    src += "LOG = " + repr(str(log_path)) + "\n"
    src += "TAG_PATH = " + repr(None if tag_path is None else str(tag_path)) + "\n"
    src += "TAG = " + repr(tag) + "\n"
    src += "def main(argv=None):\n"
    src += "    with open(LOG, 'a') as f:\n"
    src += "        f.write(json.dumps(argv) + '\\n')\n"
    src += "    if TAG_PATH is not None:\n"
    src += "        with open(TAG_PATH, 'a') as f:\n"
    src += "            f.write(TAG + '\\n')\n"
    src += "    return " + repr(return_code) + "\n"
    return src


def _write_fake(root, dir_, module, source):
    base = Path(root) / dir_
    if "." in module:
        parts = module.split(".")
        pkg = base
        for part in parts[:-1]:
            pkg = pkg / part
            pkg.mkdir(parents=True, exist_ok=True)
            init = pkg / "__init__.py"
            if not init.exists():
                init.write_text("")
        (pkg / (parts[-1] + ".py")).write_text(source)
    else:
        base.mkdir(parents=True, exist_ok=True)
        (base / (module + ".py")).write_text(source)


def _write_fake_llm_endpoint(project):
    d = Path(project) / "gen" / "llm-endpoint"
    d.mkdir(parents=True, exist_ok=True)
    src = "def load_config(config_path=None):\n"
    src += "    return None\n"
    (d / "llm_endpoint.py").write_text(src)


def _read_log(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _assert_tokens(logged, expected):
    assert logged[: len(expected)] == expected, (logged, expected)
    extras = logged[len(expected):]
    assert len(extras) <= 1, logged
    for tok in extras:
        assert tok.startswith("--model="), logged


def test_every_row_routes_with_strip_and_longest_prefix(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "tool"
    tool_root.mkdir()
    log = project / "calls.log"
    who = project / "who.log"
    _write_fake_llm_endpoint(project)

    written = set()
    for words, dir_, module, strip in VERB_ROWS:
        key = (dir_, module)
        if key in written:
            continue
        written.add(key)
        _write_fake(project, dir_, module, _fake_main_source(log, 7, who, dir_ + ":" + module))

    repo_root_token = "--repo-root=" + os.path.abspath(str(project))

    for words, dir_, module, strip in VERB_ROWS:
        if log.exists():
            log.unlink()
        if who.exists():
            who.unlink()
        argv = words.split() + ["x", "--flag"]
        code = hotdocs_cli.run(argv, tool_root=str(tool_root), cwd=str(project), env=_env())
        assert code == 7, (words, code)
        calls = _read_log(log)
        assert len(calls) == 1, (words, calls)
        _assert_tokens(calls[0], argv[strip:] + [repo_root_token])
        ran = who.read_text().splitlines()
        assert ran == [dir_ + ":" + module], (words, ran)

    # explicit checks of the examples from the criterion
    for words, expected_head in [
        ("lint", ["x", "--flag"]),
        ("generate", ["generate", "x", "--flag"]),
        ("docs-site build", ["x", "--flag"]),
        ("track ui build", ["track", "ui", "build", "x", "--flag"]),
    ]:
        if log.exists():
            log.unlink()
        if who.exists():
            who.unlink()
        argv = words.split() + ["x", "--flag"]
        code = hotdocs_cli.run(argv, tool_root=str(tool_root), cwd=str(project), env=_env())
        assert code == 7
        calls = _read_log(log)
        assert len(calls) == 1
        _assert_tokens(calls[0], expected_head + [repo_root_token])
        if words == "track ui build":
            assert who.read_text().splitlines() == [
                "gen/provenance-tracker-ui:provenance_tracker_ui"
            ]


def test_system_exit_codes_are_returned(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "tool"
    tool_root.mkdir()
    log = project / "calls.log"

    src = "import json\n"
    src += "import os\n"
    src += "LOG = " + repr(str(log)) + "\n"
    src += "def main(argv=None):\n"
    src += "    n = 0\n"
    src += "    if os.path.exists(LOG):\n"
    src += "        with open(LOG) as f:\n"
    src += "            n = len([l for l in f.read().splitlines() if l.strip()])\n"
    src += "    with open(LOG, 'a') as f:\n"
    src += "        f.write(json.dumps(argv) + '\\n')\n"
    src += "    if n == 0:\n"
    src += "        raise SystemExit(3)\n"
    src += "    if n == 1:\n"
    src += "        raise SystemExit(None)\n"
    src += "    raise SystemExit('boom')\n"
    _write_fake(project, "gen/spec-linter", "spec_linter", src)

    results = []
    for _ in range(3):
        results.append(
            hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project), env=_env())
        )
    assert results == [3, 0, 1]
    assert len(_read_log(log)) == 3


def test_two_projects_each_reach_their_own_fake(tmp_path):
    tool_root = tmp_path / "tool"
    tool_root.mkdir()
    project_a = tmp_path / "project_a"
    project_b = tmp_path / "project_b"
    project_a.mkdir()
    project_b.mkdir()
    log_a = project_a / "calls.log"
    log_b = project_b / "calls.log"
    _write_fake(project_a, "gen/spec-linter", "spec_linter", _fake_main_source(log_a, 7))
    _write_fake(project_b, "gen/spec-linter", "spec_linter", _fake_main_source(log_b, 8))

    code_a = hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project_a), env=_env())
    assert code_a == 7
    assert len(_read_log(log_a)) == 1
    assert len(_read_log(log_b)) == 0

    code_b = hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project_b), env=_env())
    assert code_b == 8
    assert len(_read_log(log_a)) == 1
    assert len(_read_log(log_b)) == 1


def test_tool_root_fallback_then_project_fake_wins(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "tool"
    tool_root.mkdir()
    log = project / "calls.log"
    who = project / "who.log"

    _write_fake(tool_root, "gen/spec-linter", "spec_linter", _fake_main_source(log, 7, who, "tool"))
    assert not (project / "gen" / "spec-linter").exists()

    code = hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project), env=_env())
    assert code == 7
    assert who.read_text().splitlines() == ["tool"]
    assert len(_read_log(log)) == 1

    _write_fake(project, "gen/spec-linter", "spec_linter", _fake_main_source(log, 7, who, "project"))
    who.unlink()
    log.unlink()

    code = hotdocs_cli.run(["lint"], tool_root=str(tool_root), cwd=str(project), env=_env())
    assert code == 7
    assert who.read_text().splitlines() == ["project"]
    assert len(_read_log(log)) == 1