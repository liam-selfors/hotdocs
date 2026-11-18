# hotdocs-criterion: sha256:b61f8e8297d1b9a764a1debe1c9613d236ddf97cb8275b9b30ff07057159db58
"""AC-DOCS-005: after a successful render, the rendered output directory is
absent from version control (R-DOCS-005: the rendered site is a CI build
artifact, never committed)."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import docs_site_renderer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git_env():
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_AUTHOR_NAME"] = "test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.invalid"
    return env


def _git(repo, *args):
    cmd = [
        "git",
        "-c", "commit.gpgsign=false",
        "-c", "init.defaultBranch=main",
        "-c", "core.autocrlf=false",
    ] + list(args)
    result = subprocess.run(
        cmd,
        cwd=str(repo),
        env=_git_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode == 0, (
        "git " + " ".join(args) + " failed: " + result.stderr
    )
    return result.stdout


def _corpus_graph_dict():
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
                    "component.md": "---\nid: comp-foo\ntitle: Foo\nstatus: draft\nowners: [pipeline-team]\n---\n\n# Foo\n",
                    "requirements/R-FOO-001.md": "**R-FOO-001** - MUST foo.\n",
                },
            },
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": True,
                "pinned_overrides": [],
                "owners": [],
                "documents": {
                    "component.md": "---\nid: comp-bar\ntitle: Bar\nstatus: draft\nowners: [pipeline-team]\n---\n\n# Bar\n",
                },
            },
            "VAR-FOO-URL": {"type": "var"},
        },
        "edges": [
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
            {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


def _write_corpus_graph(repo_root):
    graph = _corpus_graph_dict()
    data = json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    path = repo_root / "verification" / "corpus-graph.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8"))
    return path


def _cli_main():
    from docs_site_renderer import cli

    return cli.main


def _run_build(argv):
    main = _cli_main()
    rc = main(list(argv))
    if rc == 2:
        # Tolerate a main that still expects the `build` verb word.
        rc = main(["build"] + list(argv))
    return rc


def _tracked_under(repo, rel_dir):
    out = _git(repo, "ls-files", "--", rel_dir)
    return [line for line in out.splitlines() if line.strip()]


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_default_render_output_is_not_committed(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _write_corpus_graph(repo_root)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")
    head_before = _git(repo_root, "rev-parse", "HEAD").strip()
    tracked_before = sorted(_git(repo_root, "ls-files").splitlines())

    monkeypatch.chdir(repo_root)
    rc = _run_build(["--repo-root=" + str(repo_root)])
    assert rc == 0

    out_dir = repo_root / "dist" / "docs-site"
    assert out_dir.is_dir(), "default output dir dist/docs-site/ was not created"
    rendered = [p for p in out_dir.rglob("*") if p.is_file()]
    assert rendered, "render succeeded but wrote no files"

    # The render never commits: HEAD is unchanged.
    head_after = _git(repo_root, "rev-parse", "HEAD").strip()
    assert head_after == head_before

    # Nothing under the output directory is tracked or staged.
    assert _tracked_under(repo_root, "dist/docs-site") == []
    staged = _git(repo_root, "diff", "--cached", "--name-only").splitlines()
    assert [s for s in staged if s.startswith("dist/")] == []
    assert sorted(_git(repo_root, "ls-files").splitlines()) == tracked_before

    # The output is a build-artifact location, never under gen/.
    gen_dir = repo_root / "gen"
    if gen_dir.exists():
        gen_files = [
            p for p in gen_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in (".html", ".js", ".css")
        ]
        assert gen_files == [], "rendered output was written under gen/"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_explicit_out_render_output_is_not_committed(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _write_corpus_graph(repo_root)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")
    head_before = _git(repo_root, "rev-parse", "HEAD").strip()

    monkeypatch.chdir(repo_root)
    out_dir = repo_root / "site-out"
    rc = _run_build(["--repo-root=" + str(repo_root), "--out=" + str(out_dir)])
    assert rc == 0
    assert out_dir.is_dir()
    assert [p for p in out_dir.rglob("*") if p.is_file()]

    assert _git(repo_root, "rev-parse", "HEAD").strip() == head_before
    assert _tracked_under(repo_root, "site-out") == []
    staged = _git(repo_root, "diff", "--cached", "--name-only").splitlines()
    assert [s for s in staged if s.startswith("site-out")] == []


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_tool_repository_does_not_track_rendered_site():
    module_path = Path(docs_site_renderer.__file__).resolve()
    gen = next((p for p in module_path.parents if p.name == "gen"), None)
    if gen is None:
        pytest.skip("docs_site_renderer is not located under a gen/ directory")
    tool_root = gen.parent
    probe = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(tool_root),
        env=_git_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if probe.returncode != 0:
        pytest.skip("tool root is not inside a git repository")
    assert _tracked_under(tool_root, "dist/docs-site") == []