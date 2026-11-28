# hotdocs-criterion: sha256:6f0ec9492ac79c302a496ef92d8912858b8d2e3b903d04917a37071f558424d9
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import docs_site_renderer


def _corpus_graph():
    return {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "# Foo\n\nA component.\n",
                },
            },
            "VAR-FOO-URL": {"type": "var"},
        },
        "edges": [
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
            {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


def _git(args, cwd):
    return subprocess.run(
        ["git"] + list(args),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _tool_repo_root():
    here = Path(docs_site_renderer.__file__).resolve()
    gen = next((p for p in here.parents if p.name == "gen"), None)
    if gen is None:
        pytest.skip("docs_site_renderer is not under a gen/ directory")
    return gen.parent


def test_rendered_output_directory_is_not_committed(tmp_path, monkeypatch):
    if shutil.which("git") is None:
        pytest.skip("git is not available")

    # Given a successful render (default --out, which is dist/docs-site/).
    corpus_root = tmp_path / "corpus"
    (corpus_root / "verification").mkdir(parents=True)
    (corpus_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(_corpus_graph(), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(corpus_root)

    from docs_site_renderer import cli

    code = cli.main(["--repo-root=" + str(corpus_root)])
    assert code == 0

    rendered_dir = corpus_root / "dist" / "docs-site"
    assert rendered_dir.is_dir()
    assert (rendered_dir / "index.html").is_file()

    # When the repository's committed files are checked.
    tool_root = _tool_repo_root()
    top = _git(["rev-parse", "--show-toplevel"], tool_root)
    if top.returncode != 0:
        pytest.skip("the tool's repository is not a git working tree")
    toplevel = Path(top.stdout.strip()).resolve()

    listed = _git(["ls-files", "-z"], toplevel)
    assert listed.returncode == 0, listed.stderr
    tracked = [p for p in listed.stdout.split("\0") if p]

    out_dir = (tool_root / "dist" / "docs-site").resolve()
    try:
        out_rel = out_dir.relative_to(toplevel).as_posix()
    except ValueError:
        out_rel = None

    # Then the rendered output directory is absent from version control.
    if out_rel is not None:
        offending = [
            p for p in tracked if p == out_rel or p.startswith(out_rel + "/")
        ]
        assert offending == [], offending

    # The renderer's own generated directory holds no committed rendered site.
    rendered_names = sorted(
        p.relative_to(rendered_dir).as_posix()
        for p in rendered_dir.rglob("*")
        if p.is_file()
    )
    assert rendered_names, "the render produced no files"
    gen_rel_prefix = None
    try:
        gen_rel_prefix = (
            (tool_root / "gen" / "docs-site-renderer").resolve().relative_to(toplevel).as_posix()
        )
    except ValueError:
        gen_rel_prefix = None
    if gen_rel_prefix is not None:
        committed_index = [
            p
            for p in tracked
            if p.startswith(gen_rel_prefix + "/") and p.endswith("/index.html")
            or p == gen_rel_prefix + "/index.html"
        ]
        assert committed_index == [], committed_index