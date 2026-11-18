# hotdocs-criterion: sha256:320b81eec3cd113bbfde36653d635210f4d84fa27bda048c6950d54d29c782bf
import json
import os
from pathlib import Path

import hotdocs_cli


# (verb words, dir, module, strip, model required)
ROWS = [
    ("lint", "gen/spec-linter", "spec_linter", 1, False),
    ("impact", "gen/impact-analyzer", "impact_analyzer", 1, False),
    ("assemble", "gen/spec-bundle-assembler", "spec_bundle_assembler", 1, False),
    ("compile-criteria", "pipeline/criterion-compiler", "criterion_compiler", 1, False),
    ("author-test", "gen/test-author", "test_author", 0, True),
    ("verify-component", "gen/verifier-orchestrator", "verifier_orchestrator", 1, False),
    ("generate", "gen/component-gate-runner", "component_gate_runner", 0, True),
    ("verify", "gen/provenance-tracker", "provenance_tracker", 0, False),
    ("track feedback", "gen/provenance-tracker", "provenance_tracker", 0, False),
    ("track ui build", "gen/provenance-tracker-ui", "provenance_tracker_ui", 0, False),
    ("provenance check", "gen/provenance-checker", "provenance_checker", 1, False),
    ("provenance write", "gen/provenance-writer", "provenance_writer", 0, False),
    ("license-scan", "gen/license-scanner", "license_scanner", 1, False),
    ("secret-scan", "gen/secret-scanner", "secret_scanner", 1, False),
    ("review-packet build", "gen/review-packet-builder", "review_packet_builder", 0, False),
    ("decision-drift", "gen/decision-drift-detector", "decision_drift_detector", 0, False),
    ("decision-impact", "gen/decision-drift-detector", "decision_drift_detector", 0, False),
    ("docs-site build", "gen/docs-site-renderer", "docs_site_renderer.cli", 2, False),
    ("corpus-graph build", "gen/corpus-graph-builder", "corpus_graph_builder.cli", 1, False),
    ("assist", "gen/spec-completeness-assistant", "spec_completeness_assistant", 1, False),
]


def _module_path(root, dir_, module):
    base = Path(root) / dir_
    if "." in module:
        parts = module.split(".")
        pkg_dir = base.joinpath(*parts[:-1])
        pkg_dir.mkdir(parents=True, exist_ok=True)
        # make every package level importable
        cur = base
        for part in parts[:-1]:
            cur = cur / part
            init = cur / "__init__.py"
            if not init.exists():
                init.write_text("")
        return pkg_dir / (parts[-1] + ".py")
    base.mkdir(parents=True, exist_ok=True)
    return base / (module + ".py")


def _fake_source(log_path, which_path, tag, code=7):
    return (
        "import json\n"
        "\n"
        "def main(argv):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "        f.write(json.dumps(argv) + '\\n')\n"
        "    with open(" + repr(str(which_path)) + ", 'a') as f:\n"
        "        f.write(" + repr(tag) + " + '\\n')\n"
        "    return " + repr(code) + "\n"
    )


def _write_fake(root, dir_, module, log_path, which_path, tag, code=7):
    path = _module_path(root, dir_, module)
    path.write_text(_fake_source(log_path, which_path, tag, code))
    return path


def _llm_endpoint_source():
    return (
        "class ModelResolutionError(Exception):\n"
        "    pass\n"
        "\n"
        "def load_config(config_path=None):\n"
        "    return {\n"
        "        'provider': " + repr("anthropic") + ",\n"
        "        'model': " + repr("claude-sonnet-5") + ",\n"
        "        'base_url': None,\n"
        "        'api_key_env': " + repr("ANTHROPIC_API_KEY") + ",\n"
        "        'timeout_seconds': 600,\n"
        "        'auth': None,\n"
        "    }\n"
    )


def _make_project(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "specs").mkdir(exist_ok=True)
    (path / "hotdocs.toml").write_text(
        "[llm]\n" + "provider = " + json.dumps("anthropic") + "\n"
        + "model = " + json.dumps("claude-sonnet-5") + "\n"
    )
    return path


def _read_lines(path):
    if not Path(path).exists():
        return []
    return [line for line in Path(path).read_text().splitlines() if line.strip()]


def _is_repo_root_token(token, project):
    prefix = "--repo-root="
    if not isinstance(token, str) or not token.startswith(prefix):
        return False
    return Path(token[len(prefix):]).resolve() == Path(project).resolve()


def _strip_model_and_root(tokens):
    out = []
    skip = False
    for tok in tokens:
        if skip:
            skip = False
            continue
        if tok == "--model":
            skip = True
            continue
        if tok.startswith("--model=") or tok.startswith("--repo-root="):
            continue
        out.append(tok)
    return out


def _quiet():
    sink = []
    return sink, (lambda *a, **k: sink.append(a))


def test_every_row_dispatches_with_strip_and_longest_prefix(tmp_path):
    project = _make_project(tmp_path / "project")
    tool_root = tmp_path / "tool"
    tool_root.mkdir()
    log = project / "calls.log"
    which = project / "which.log"

    llm_dir = project / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True, exist_ok=True)
    (llm_dir / "llm_endpoint.py").write_text(_llm_endpoint_source())

    for words, dir_, module, strip, model in ROWS:
        _write_fake(project, dir_, module, log, which, dir_ + "/" + module)

    for words, dir_, module, strip, model in ROWS:
        for p in (log, which):
            if p.exists():
                p.unlink()
        argv = words.split() + ["x", "--flag"]
        _, out = _quiet()
        code = hotdocs_cli.main(
            list(argv),
            tool_root=tool_root,
            cwd=project,
            env=dict(os.environ),
            output_fn=out,
        )
        assert code == 7, (words, code)

        tags = _read_lines(which)
        assert tags == [dir_ + "/" + module], (words, tags)

        calls = _read_lines(log)
        assert len(calls) == 1, (words, calls)
        received = json.loads(calls[0])
        expected = argv[strip:]

        root_tokens = [t for t in received if isinstance(t, str) and t.startswith("--repo-root=")]
        assert len(root_tokens) == 1, (words, received)
        assert _is_repo_root_token(root_tokens[0], project), (words, received)

        if model:
            assert _strip_model_and_root(received) == expected, (words, received)
        else:
            assert received[:-1] == expected, (words, received)
            assert _is_repo_root_token(received[-1], project), (words, received)

    # Spot checks spelled out by the criterion.
    for p in (log, which):
        if p.exists():
            p.unlink()
    _, out = _quiet()
    assert hotdocs_cli.main(["track", "ui", "build", "x", "--flag"],
                            tool_root=tool_root, cwd=project, output_fn=out) == 7
    assert _read_lines(which) == ["gen/provenance-tracker-ui/provenance_tracker_ui"]
    assert json.loads(_read_lines(log)[0])[:-1] == ["track", "ui", "build", "x", "--flag"]

    for p in (log, which):
        if p.exists():
            p.unlink()
    assert hotdocs_cli.main(["docs-site", "build", "x", "--flag"],
                            tool_root=tool_root, cwd=project, output_fn=out) == 7
    assert json.loads(_read_lines(log)[0])[:-1] == ["x", "--flag"]

    for p in (log, which):
        if p.exists():
            p.unlink()
    assert hotdocs_cli.main(["lint", "x", "--flag"],
                            tool_root=tool_root, cwd=project, output_fn=out) == 7
    received = json.loads(_read_lines(log)[0])
    assert received[:-1] == ["x", "--flag"]
    assert _is_repo_root_token(received[-1], project)


def test_system_exit_codes_are_caught_and_mapped(tmp_path):
    project = _make_project(tmp_path / "project")
    tool_root = tmp_path / "tool"
    tool_root.mkdir()
    counter = project / "counter.txt"
    log = project / "calls.log"

    src = (
        "import json\n"
        "import os\n"
        "\n"
        "def main(argv):\n"
        "    p = " + repr(str(counter)) + "\n"
        "    n = int(open(p).read()) if os.path.exists(p) else 0\n"
        "    with open(p, 'w') as f:\n"
        "        f.write(str(n + 1))\n"
        "    with open(" + repr(str(log)) + ", 'a') as f:\n"
        "        f.write(json.dumps(argv) + '\\n')\n"
        "    codes = [3, None, " + repr("boom") + "]\n"
        "    raise SystemExit(codes[n])\n"
    )
    path = _module_path(project, "gen/spec-linter", "spec_linter")
    path.write_text(src)

    _, out = _quiet()
    results = [
        hotdocs_cli.main(["lint"], tool_root=tool_root, cwd=project, output_fn=out)
        for _ in range(3)
    ]
    assert results == [3, 0, 1]
    assert len(_read_lines(log)) == 3


def test_two_projects_each_reach_their_own_fake(tmp_path):
    tool_root = tmp_path / "tool"
    tool_root.mkdir()
    which = tmp_path / "which.log"
    proj_a = _make_project(tmp_path / "a")
    proj_b = _make_project(tmp_path / "b")
    _write_fake(proj_a, "gen/spec-linter", "spec_linter", proj_a / "calls.log", which, "A")
    _write_fake(proj_b, "gen/spec-linter", "spec_linter", proj_b / "calls.log", which, "B")

    _, out = _quiet()
    assert hotdocs_cli.main(["lint"], tool_root=tool_root, cwd=proj_a, output_fn=out) == 7
    assert hotdocs_cli.main(["lint"], tool_root=tool_root, cwd=proj_b, output_fn=out) == 7
    assert hotdocs_cli.main(["lint"], tool_root=tool_root, cwd=proj_a, output_fn=out) == 7

    assert _read_lines(which) == ["A", "B", "A"]
    assert len(_read_lines(proj_a / "calls.log")) == 2
    assert len(_read_lines(proj_b / "calls.log")) == 1


def test_falls_back_to_tool_root_then_prefers_project(tmp_path):
    project = _make_project(tmp_path / "project")
    tool_root = tmp_path / "tool"
    tool_root.mkdir()
    log = project / "calls.log"
    which = project / "which.log"

    assert not (project / "gen" / "spec-linter").exists()
    _write_fake(tool_root, "gen/spec-linter", "spec_linter", log, which, "tool")

    _, out = _quiet()
    code = hotdocs_cli.main(["lint"], tool_root=tool_root, cwd=project, output_fn=out)
    assert code == 7
    assert _read_lines(which) == ["tool"]
    assert len(_read_lines(log)) == 1

    _write_fake(project, "gen/spec-linter", "spec_linter", log, which, "project")
    code = hotdocs_cli.main(["lint"], tool_root=tool_root, cwd=project, output_fn=out)
    assert code == 7
    assert _read_lines(which) == ["tool", "project"]
    assert len(_read_lines(log)) == 2