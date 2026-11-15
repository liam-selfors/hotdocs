import docs_site_renderer

import importlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


GIT = shutil.which("git")

OUT_REL = "dist/docs-site"


def _git(repo, *args, check=True):
    cmd = [
        GIT,
        "-c", "user.name=docs-site-test",
        "-c", "user.email=docs-site-test@example.invalid",
        "-c", "commit.gpgsign=false",
        "-c", "core.autocrlf=false",
        *args,
    ]
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
    )
    if check:
        assert proc.returncode == 0, (
            f"git {' '.join(args)} failed: {proc.stdout}\n{proc.stderr}"
        )
    return proc


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _corpus_graph_dict():
    component_md = (
        "---\n"
        "id: comp-demo\n"
        "title: Demo component\n"
        "status: draft\n"
        "owners: [docs-team]\n"
        "depends_on: []\n"
        "realizes: [P-DEMO]\n"
        "uses_var: [VAR-DEMO-URL]\n"
        "sealed: true\n"
        "source_path: legacy/demo/\n"
        "---\n"
        "\n"
        "# Demo component\n"
        "\n"
        "A demo component for rendering.\n"
    )
    requirement_md = (
        "# R-DEMO-001\n"
        "\n"
        "**R-DEMO-001** — MUST render.\n"
    )
    return {
        "nodes": {
            "P-DEMO": {"type": "capability"},
            "VAR-DEMO-URL": {"type": "var"},
            "comp-demo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["docs-team"],
                "documents": {
                    "component.md": component_md,
                    "requirements/R-DEMO-001.md": requirement_md,
                },
            },
        },
        "edges": [
            {"from": "comp-demo", "to": "P-DEMO", "kind": "realizes"},
            {"from": "comp-demo", "to": "VAR-DEMO-URL", "kind": "uses_var"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    graph = _corpus_graph_dict()
    data = json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    (repo / "verification").mkdir()
    (repo / "verification" / "corpus-graph.json").write_bytes(data.encode("utf-8"))
    _write(
        repo / "specs" / "components" / "demo" / "component.md",
        graph["nodes"]["comp-demo"]["documents"]["component.md"],
    )
    _write(
        repo / "specs" / "components" / "demo" / "requirements" / "R-DEMO-001.md",
        graph["nodes"]["comp-demo"]["documents"]["requirements/R-DEMO-001.md"],
    )
    _write(repo / "README.md", "# fixture repo\n")
    return repo


def _cli_main():
    cli = getattr(docs_site_renderer, "cli", None)
    if cli is None or not hasattr(cli, "main"):
        cli = importlib.import_module("docs_site_renderer.cli")
    return cli.main


def _tracked_files(repo: Path):
    proc = _git(repo, "ls-files", "-z")
    return [p for p in proc.stdout.split("\0") if p]


def _under_out(path: str) -> bool:
    norm = path.replace("\\", "/")
    return norm == OUT_REL or norm.startswith(OUT_REL + "/")


@pytest.mark.skipif(GIT is None, reason="git is required to inspect committed files")
def test_rendered_output_is_not_committed(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)

    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline fixture")
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()

    # Run with cwd at the repo root so the default --out (dist/docs-site/)
    # resolves inside the repository whether relative to cwd or repo root.
    monkeypatch.chdir(repo)
    main = _cli_main()
    rc = main([f"--repo-root={repo}"])
    assert rc == 0, f"render did not succeed, exit code {rc!r}"

    out_dir = repo / OUT_REL
    assert out_dir.is_dir(), "successful render should produce dist/docs-site/"
    rendered = [p for p in out_dir.rglob("*") if p.is_file()]
    assert rendered, "successful render should write files to the output directory"

    # No new commit was made by the render.
    head_after = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert head_after == head_before, "rendering must not create a commit"

    # Nothing under the output directory is tracked in version control.
    tracked = _tracked_files(repo)
    tracked_out = [p for p in tracked if _under_out(p)]
    assert tracked_out == [], f"rendered output is tracked: {tracked_out}"

    # Nothing under the output directory is in the committed tree.
    tree = _git(repo, "ls-tree", "-r", "--name-only", "HEAD").stdout.splitlines()
    committed_out = [p for p in tree if _under_out(p)]
    assert committed_out == [], f"rendered output is committed: {committed_out}"

    # Nothing under the output directory was staged either.
    staged = _git(repo, "diff", "--cached", "--name-only").stdout.splitlines()
    staged_out = [p for p in staged if _under_out(p)]
    assert staged_out == [], f"rendered output was staged: {staged_out}"

    # Every rendered file is untracked (or ignored), never tracked.
    for path in rendered:
        rel = path.relative_to(repo).as_posix()
        proc = _git(repo, "ls-files", "--error-unmatch", "--", rel, check=False)
        assert proc.returncode != 0, f"rendered file is tracked: {rel}"


def _tool_root():
    mod_file = Path(docs_site_renderer.__file__).resolve()
    for parent in mod_file.parents:
        if parent.name == "gen":
            return parent.parent
    return None


@pytest.mark.skipif(GIT is None, reason="git is required to inspect committed files")
def test_tool_repository_does_not_commit_rendered_site():
    root = _tool_root()
    if root is None:
        pytest.skip("module under test is not inside a gen/ tree")
    probe = _git(root, "rev-parse", "--is-inside-work-tree", check=False)
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        pytest.skip("tool root is not a git work tree")
    top = Path(_git(root, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    proc = _git(top, "ls-files", "-z", "--", OUT_REL)
    tracked = [p for p in proc.stdout.split("\0") if p]
    assert tracked == [], f"rendered docs site is committed in the repository: {tracked}"