"""AC-CLI-001 (Covers: R-CLI-001): verb dispatch by longest prefix, argv[strip:],
SystemExit handling, per-repo-root fresh loading, and tool-root fallback."""

import json
import os
from pathlib import Path

import pytest

import hotdocs_cli


# (verb words, dir, module, strip, model required)
ROWS = [
    (["lint"], "gen/spec-linter", "spec_linter", 1, False),
    (["impact"], "gen/impact-analyzer", "impact_analyzer", 1, False),
    (["assemble"], "gen/spec-bundle-assembler", "spec_bundle_assembler", 1, False),
    (["compile-criteria"], "pipeline/criterion-compiler", "criterion_compiler", 1, False),
    (["author-test"], "gen/test-author", "test_author", 0, True),
    (["verify-component"], "gen/verifier-orchestrator", "verifier_orchestrator", 1, False),
    (["generate"], "gen/component-gate-runner", "component_gate_runner", 0, True),
    (["verify"], "gen/provenance-tracker", "provenance_tracker", 0, False),
    (["track", "feedback"], "gen/provenance-tracker", "provenance_tracker", 0, False),
    (["track", "ui", "build"], "gen/provenance-tracker-ui", "provenance_tracker_ui", 0, False),
    (["provenance", "check"], "gen/provenance-checker", "provenance_checker", 1, False),
    (["provenance", "write"], "gen/provenance-writer", "provenance_writer", 0, False),
    (["license-scan"], "gen/license-scanner", "license_scanner", 1, False),
    (["secret-scan"], "gen/secret-scanner", "secret_scanner", 1, False),
    (["review-packet", "build"], "gen/review-packet-builder", "review_packet_builder", 0, False),
    (["decision-drift"], "gen/decision-drift-detector", "decision_drift_detector", 0, False),
    (["decision-impact"], "gen/decision-drift-detector", "decision_drift_detector", 0, False),
    (["docs-site", "build"], "gen/docs-site-renderer", "docs_site_renderer.cli", 2, False),
    (["corpus-graph", "build"], "gen/corpus-graph-builder", "corpus_graph_builder.cli", 1, False),
    (["assist"], "gen/spec-completeness-assistant", "spec_completeness_assistant", 1, False),
]


def _fake_source(log_path, label):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "LABEL = " + repr(label) + "\n"
        "def main(argv=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'fake': LABEL, 'argv': list(argv or [])}) + '\\n')\n"
        "    return 7\n"
    )


def _write_module(root, rel_dir, module, source):
    base = Path(root) / rel_dir
    base.mkdir(parents=True, exist_ok=True)
    if "." in module:
        pkg, sub = module.split(".", 1)
        pkg_dir = base / pkg
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
        (pkg_dir / (sub + ".py")).write_text(source, encoding="utf-8")
    else:
        (base / (module + ".py")).write_text(source, encoding="utf-8")


def _write_fake(root, rel_dir, module, log_path, label):
    _write_module(root, rel_dir, module, _fake_source(log_path, label))


LLM_FAKE = (
    "def load_config(config_path=None):\n"
    "    return {'provider': 'anthropic', 'model': 'claude-sonnet-5',\n"
    "            'base_url': None, 'api_key_env': None, 'timeout_seconds': None}\n"
)


def _make_project(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "hotdocs.toml").write_text(
        '[llm]\nprovider = "anthropic"\nmodel = "claude-sonnet-5"\n', encoding="utf-8"
    )
    _write_module(path, "gen/llm-endpoint", "llm_endpoint", LLM_FAKE)
    (path / "calls.log").write_text("", encoding="utf-8")
    return path


def _read_log(log_path):
    text = Path(log_path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _env_for(project):
    env = dict(os.environ)
    env["VAR_HOTDOCS_CONFIG"] = str(project / "hotdocs.toml")
    return env


def _call(argv, project, monkeypatch, **kwargs):
    monkeypatch.chdir(project)
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(project / "hotdocs.toml"))
    return hotdocs_cli.main(
        argv,
        cwd=str(project),
        env=_env_for(project),
        output_fn=lambda *a, **k: None,
        **kwargs,
    )


def _split_repo_root(tokens):
    roots = [t for t in tokens if t.startswith("--repo-root=")]
    rest = [t for t in tokens if not t.startswith("--repo-root=")]
    return roots, rest


def _strip_model(tokens):
    out = []
    skip = False
    for t in tokens:
        if skip:
            skip = False
            continue
        if t == "--model":
            skip = True
            continue
        if t.startswith("--model="):
            continue
        out.append(t)
    return out


def _same_path(a, b):
    return Path(a).resolve() == Path(b).resolve()


@pytest.mark.parametrize(
    "words,rel_dir,module,strip,model_required",
    ROWS,
    ids=[" ".join(r[0]) for r in ROWS],
)
def test_each_row_dispatches_argv_strip(tmp_path, monkeypatch, words, rel_dir, module,
                                        strip, model_required):
    project = _make_project(tmp_path / "project")
    log = project / "calls.log"
    for _w, d, m, _s, _mr in ROWS:
        _write_fake(project, d, m, log, d + "/" + m)

    argv = list(words) + ["x", "--flag"]
    rc = _call(argv, project, monkeypatch)

    assert rc == 7
    entries = _read_log(log)
    assert len(entries) == 1, entries
    entry = entries[0]
    # The row's own fake ran (longest prefix won, e.g. "track ui build"
    # reaches provenance-tracker-ui, never provenance-tracker).
    assert entry["fake"] == rel_dir + "/" + module

    received = entry["argv"]
    expected = argv[strip:]
    if not model_required:
        assert received[-1].startswith("--repo-root=")
        assert _same_path(received[-1].split("=", 1)[1], project)
        assert received[:-1] == expected
    else:
        roots, rest = _split_repo_root(received)
        assert len(roots) == 1
        assert _same_path(roots[0].split("=", 1)[1], project)
        assert _strip_model(rest) == expected


def test_track_ui_build_never_reaches_track_feedback(tmp_path, monkeypatch):
    project = _make_project(tmp_path / "project")
    log = project / "calls.log"
    for _w, d, m, _s, _mr in ROWS:
        _write_fake(project, d, m, log, d + "/" + m)

    rc = _call(["track", "ui", "build", "x", "--flag"], project, monkeypatch)
    assert rc == 7
    fakes = [e["fake"] for e in _read_log(log)]
    assert fakes == ["gen/provenance-tracker-ui/provenance_tracker_ui"]


def test_system_exit_codes_are_returned(tmp_path, monkeypatch):
    project = _make_project(tmp_path / "project")
    log = project / "calls.log"
    counter = project / "counter.txt"
    source = (
        "import json, os\n"
        "LOG = " + repr(str(log)) + "\n"
        "COUNTER = " + repr(str(counter)) + "\n"
        "def main(argv=None):\n"
        "    n = 0\n"
        "    if os.path.exists(COUNTER):\n"
        "        with open(COUNTER, encoding='utf-8') as fh:\n"
        "            n = int(fh.read().strip() or '0')\n"
        "    with open(COUNTER, 'w', encoding='utf-8') as fh:\n"
        "        fh.write(str(n + 1))\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'fake': 'exit', 'argv': list(argv or [])}) + '\\n')\n"
        "    if n == 0:\n"
        "        raise SystemExit(3)\n"
        "    if n == 1:\n"
        "        raise SystemExit(None)\n"
        "    raise SystemExit('boom')\n"
    )
    _write_module(project, "gen/spec-linter", "spec_linter", source)

    results = [_call(["lint"], project, monkeypatch) for _ in range(3)]

    assert results == [3, 0, 1]
    assert [e["fake"] for e in _read_log(log)] == ["exit", "exit", "exit"]


def test_two_projects_each_reach_their_own_fake(tmp_path, monkeypatch):
    proj_a = _make_project(tmp_path / "a")
    proj_b = _make_project(tmp_path / "b")
    _write_fake(proj_a, "gen/spec-linter", "spec_linter", proj_a / "calls.log", "A")
    _write_fake(proj_b, "gen/spec-linter", "spec_linter", proj_b / "calls.log", "B")

    rc_a = _call(["lint"], proj_a, monkeypatch)
    rc_b = _call(["lint"], proj_b, monkeypatch)
    rc_a2 = _call(["lint"], proj_a, monkeypatch)

    assert (rc_a, rc_b, rc_a2) == (7, 7, 7)
    assert [e["fake"] for e in _read_log(proj_a / "calls.log")] == ["A", "A"]
    assert [e["fake"] for e in _read_log(proj_b / "calls.log")] == ["B"]


def test_falls_back_to_tool_root_then_prefers_project(tmp_path, monkeypatch):
    project = _make_project(tmp_path / "project")
    tool_root = tmp_path / "tool"
    tool_root.mkdir()
    log = project / "calls.log"
    _write_fake(tool_root, "gen/spec-linter", "spec_linter", log, "tool")
    assert not (project / "gen" / "spec-linter").exists()

    rc = _call(["lint"], project, monkeypatch, tool_root=str(tool_root))
    assert rc == 7
    assert [e["fake"] for e in _read_log(log)] == ["tool"]

    _write_fake(project, "gen/spec-linter", "spec_linter", log, "project")
    rc2 = _call(["lint"], project, monkeypatch, tool_root=str(tool_root))
    assert rc2 == 7
    assert [e["fake"] for e in _read_log(log)] == ["tool", "project"]