# hotdocs-criterion: sha256:b758637e8dbf9e0ba625b52b18e0faa9e7ebed8e68995a23a91090dae54244bf
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


GIT = shutil.which("git")


def _git(repo, *args):
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["HOME"] = str(repo)
    result = subprocess.run(
        [GIT, "-c", "user.name=hotdocs-test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", "-C", str(repo)] + list(args),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return result


def _git_ok(repo, *args):
    result = _git(repo, *args)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def _corpus_graph():
    return {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "# Foo\n\nThe foo component.\n",
                    "requirements/R-FOO-001.md": "# R-FOO-001\n\nFoo MUST work.\n",
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
            "orphan_var_rate": 1.0,
        },
    }


def _main():
    main = getattr(docs_site_renderer, "main", None)
    if main is None:
        from docs_site_renderer import cli
        main = cli.main
    return main


@pytest.mark.skipif(GIT is None, reason="git is not installed")
def test_rendered_output_is_not_committed(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    graph_path = repo / "verification" / "corpus-graph.json"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text(
        json.dumps(_corpus_graph(), sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    _git_ok(repo, "init", "-q")
    _git_ok(repo, "add", "-A")
    _git_ok(repo, "commit", "-q", "-m", "fixture")
    head_before = _git_ok(repo, "rev-parse", "HEAD").strip()
    tracked_before = sorted(_git_ok(repo, "ls-files").splitlines())

    # Given a successful render (default --out, relative paths resolved
    # against both the working directory and --repo-root, which coincide).
    monkeypatch.chdir(repo)
    code = _main()(["--repo-root=" + str(repo)])
    assert code == 0

    out_dir = repo / "dist" / "docs-site"
    assert out_dir.is_dir()
    assert (out_dir / "index.html").is_file()

    # When the repository's committed files are checked
    head_after = _git_ok(repo, "rev-parse", "HEAD").strip()
    tracked_after = sorted(_git_ok(repo, "ls-files").splitlines())

    # Then the rendered output directory is absent from version control.
    assert head_after == head_before
    assert tracked_after == tracked_before
    assert not any(p == "dist" or p.startswith("dist/") for p in tracked_after)
    assert _git_ok(repo, "ls-files", "--", "dist/docs-site").strip() == ""
    committed = _git_ok(repo, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    assert not any(p.startswith("dist/") for p in committed)
    # The default output location is a build-artifact location, never gen/.
    assert not (repo / "gen" / "docs-site-renderer" / "index.html").exists()


@pytest.mark.skipif(GIT is None, reason="git is not installed")
def test_real_repository_does_not_commit_rendered_site():
    parents = list(Path(docs_site_renderer.__file__).resolve().parents)
    gens = [p for p in parents if p.name == "gen"]
    if not gens:
        pytest.skip("component is not laid out under a gen/ directory")
    repo = gens[0].parent
    probe = _git(repo, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        pytest.skip("component's repository is not a git work tree")
    toplevel = Path(_git_ok(repo, "rev-parse", "--show-toplevel").strip())
    rel = os.path.relpath(repo / "dist" / "docs-site", toplevel).replace(os.sep, "/")
    assert _git_ok(toplevel, "ls-files", "--", rel).strip() == ""