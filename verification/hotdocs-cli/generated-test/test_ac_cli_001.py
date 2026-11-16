import json
import os
from pathlib import Path

import pytest

import hotdocs_cli


# (verb words, dir, module, strip) -- every row of VerbTable except "init".
VERB_ROWS = [
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
]


FAKE_TEMPLATE = '''import json


def main(argv=None, **kwargs):
    record = {"fake": __LABEL__, "argv": list(argv) if argv is not None else None}
    with open(__LOG__, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")
    return 7
'''


LLM_STANDIN = '''class ModelResolutionError(Exception):
    pass


def load_config(config_path=None):
    return None
'''


def _label(dir_, module):
    return dir_ + "/" + module


def _fake_source(log_path, label):
    return (
        FAKE_TEMPLATE.replace("__LABEL__", repr(label))
        .replace("__LOG__", repr(str(log_path)))
    )


def _write_module(base, dir_, module, source):
    base = Path(base)
    if "." in module:
        pkg, sub = module.split(".", 1)
        pkg_dir = base / dir_ / pkg
        pkg_dir.mkdir(parents=True, exist_ok=True)
        init = pkg_dir / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
        (pkg_dir / (sub + ".py")).write_text(source, encoding="utf-8")
    else:
        mod_dir = base / dir_
        mod_dir.mkdir(parents=True, exist_ok=True)
        (mod_dir / (module + ".py")).write_text(source, encoding="utf-8")


def _write_fake(base, dir_, module, log_path, label=None):
    if label is None:
        label = _label(dir_, module)
    _write_module(base, dir_, module, _fake_source(log_path, label))


def _read_log(log_path):
    log_path = Path(log_path)
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _clean_env():
    env = dict(os.environ)
    env.pop("VAR_HOTDOCS_CONFIG", None)
    return env


def _assert_tokens(received, expected_head, project):
    assert isinstance(received, list)
    assert len(received) == len(expected_head) + 1, received
    assert received[:-1] == expected_head, received
    last = received[-1]
    assert last.startswith("--repo-root="), received
    root_value = last[len("--repo-root="):]
    assert Path(root_value).resolve() == Path(project).resolve(), received


def _make_full_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "specs").mkdir()
    log = project / "calls.log"
    seen = set()
    for _words, dir_, module, _strip in VERB_ROWS:
        if (dir_, module) in seen:
            continue
        seen.add((dir_, module))
        _write_fake(project, dir_, module, log)
    _write_module(project, "gen/llm-endpoint", "llm_endpoint", LLM_STANDIN)
    return project, log


@pytest.mark.parametrize(
    "words,dir_,module,strip",
    VERB_ROWS,
    ids=[row[0].replace(" ", "_") for row in VERB_ROWS],
)
def test_each_row_dispatches_argv_after_strip(tmp_path, words, dir_, module, strip):
    project, log = _make_full_project(tmp_path)
    tool_root = tmp_path / "empty-tool-root"
    tool_root.mkdir()

    tokens = words.split() + ["x", "--flag"]
    rc = hotdocs_cli.main(
        list(tokens), tool_root=tool_root, cwd=project, env=_clean_env()
    )

    assert rc == 7
    records = _read_log(log)
    assert len(records) == 1, records
    record = records[0]
    # The longest prefix won: exactly this row's fake ran (e.g. "track ui build"
    # reached provenance_tracker_ui, never provenance_tracker).
    assert record["fake"] == _label(dir_, module)
    _assert_tokens(record["argv"], tokens[strip:], project)


def test_track_ui_build_never_reaches_track_feedback(tmp_path):
    project, log = _make_full_project(tmp_path)
    tool_root = tmp_path / "empty-tool-root"
    tool_root.mkdir()

    rc = hotdocs_cli.main(
        ["track", "ui", "build", "x", "--flag"],
        tool_root=tool_root,
        cwd=project,
        env=_clean_env(),
    )
    assert rc == 7
    records = _read_log(log)
    assert len(records) == 1, records
    assert records[0]["fake"] == _label("gen/provenance-tracker-ui", "provenance_tracker_ui")
    assert records[0]["fake"] != _label("gen/provenance-tracker", "provenance_tracker")
    _assert_tokens(records[0]["argv"], ["track", "ui", "build", "x", "--flag"], project)


def test_specific_token_examples(tmp_path):
    project, log = _make_full_project(tmp_path)
    tool_root = tmp_path / "empty-tool-root"
    tool_root.mkdir()
    env = _clean_env()

    assert hotdocs_cli.main(["lint", "x", "--flag"], tool_root=tool_root, cwd=project, env=env) == 7
    recs = _read_log(log)
    assert len(recs) == 1
    _assert_tokens(recs[-1]["argv"], ["x", "--flag"], project)

    assert hotdocs_cli.main(["generate", "x", "--flag"], tool_root=tool_root, cwd=project, env=env) == 7
    recs = _read_log(log)
    assert len(recs) == 2
    _assert_tokens(recs[-1]["argv"], ["generate", "x", "--flag"], project)

    assert hotdocs_cli.main(["docs-site", "build", "x", "--flag"], tool_root=tool_root, cwd=project, env=env) == 7
    recs = _read_log(log)
    assert len(recs) == 3
    _assert_tokens(recs[-1]["argv"], ["x", "--flag"], project)


SYSTEMEXIT_TEMPLATE = '''import json
import os


def main(argv=None, **kwargs):
    counter = __COUNTER__
    n = 0
    if os.path.exists(counter):
        with open(counter, "r", encoding="utf-8") as fh:
            n = int(fh.read().strip() or "0")
    with open(counter, "w", encoding="utf-8") as fh:
        fh.write(str(n + 1))
    with open(__LOG__, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"fake": "systemexit", "call": n}) + "\\n")
    codes = [3, None, "boom"]
    raise SystemExit(codes[n])
'''


def test_systemexit_codes_are_caught_and_returned(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "specs").mkdir()
    log = project / "calls.log"
    counter = project / "counter.txt"
    source = (
        SYSTEMEXIT_TEMPLATE.replace("__COUNTER__", repr(str(counter)))
        .replace("__LOG__", repr(str(log)))
    )
    _write_module(project, "gen/spec-linter", "spec_linter", source)
    tool_root = tmp_path / "empty-tool-root"
    tool_root.mkdir()
    env = _clean_env()

    results = []
    for _ in range(3):
        results.append(
            hotdocs_cli.main(["lint", "x", "--flag"], tool_root=tool_root, cwd=project, env=env)
        )

    assert results == [3, 0, 1]
    records = _read_log(log)
    assert [r["call"] for r in records] == [0, 1, 2]


def test_two_projects_each_reach_their_own_fake(tmp_path):
    tool_root = tmp_path / "empty-tool-root"
    tool_root.mkdir()
    env = _clean_env()

    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    for project, label in ((project_a, "fake-a"), (project_b, "fake-b")):
        project.mkdir()
        (project / "specs").mkdir()
        _write_fake(project, "gen/spec-linter", "spec_linter", project / "calls.log", label=label)

    log_a = project_a / "calls.log"
    log_b = project_b / "calls.log"

    assert hotdocs_cli.main(["lint"], tool_root=tool_root, cwd=project_a, env=env) == 7
    assert [r["fake"] for r in _read_log(log_a)] == ["fake-a"]
    assert _read_log(log_b) == []

    assert hotdocs_cli.main(["lint"], tool_root=tool_root, cwd=project_b, env=env) == 7
    assert [r["fake"] for r in _read_log(log_a)] == ["fake-a"]
    assert [r["fake"] for r in _read_log(log_b)] == ["fake-b"]

    assert hotdocs_cli.main(["lint"], tool_root=tool_root, cwd=project_a, env=env) == 7
    assert [r["fake"] for r in _read_log(log_a)] == ["fake-a", "fake-a"]
    assert [r["fake"] for r in _read_log(log_b)] == ["fake-b"]


def test_falls_back_to_tool_root_then_prefers_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "specs").mkdir()
    log = project / "calls.log"

    tool_root = tmp_path / "fake-tool-root"
    tool_root.mkdir()
    _write_fake(tool_root, "gen/spec-linter", "spec_linter", log, label="tool-root-fake")

    assert not (project / "gen" / "spec-linter").exists()
    rc = hotdocs_cli.main(["lint"], tool_root=tool_root, cwd=project)
    assert rc == 7
    records = _read_log(log)
    assert [r["fake"] for r in records] == ["tool-root-fake"]

    _write_fake(project, "gen/spec-linter", "spec_linter", log, label="project-fake")
    rc = hotdocs_cli.main(["lint"], tool_root=tool_root, cwd=project)
    assert rc == 7
    records = _read_log(log)
    assert [r["fake"] for r in records] == ["tool-root-fake", "project-fake"]