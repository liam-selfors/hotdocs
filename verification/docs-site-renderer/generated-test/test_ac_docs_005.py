# hotdocs-criterion: sha256:4a4a3e0a39ce8e9c2d1a3fe8625c1e9f8d36f0e3876e2db649ea411bf7875c21
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import docs_site_renderer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(args, cwd):
    return subprocess.run(
        ["git"] + list(args),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _write_graph(repo_root):
    graph = {
        "nodes": {
            "P-DEMO": {"type": "capability"},
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
                "documents": {},
            },
            "VAR-FOO-URL": {"type": "var"},
        },
        "edges": [
            {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 1.0,
            "orphan_component_rate": 0.5,
            "orphan_var_rate": 0.0,
        },
    }
    verification = repo_root / "verification"
    verification.mkdir(parents=True, exist_ok=True)
    (verification / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _tool_root():
    pkg = Path(docs_site_renderer.__file__).resolve()
    gen = next((p for p in pkg.parents if p.name == "gen"), None)
    if gen is None:
        return None
    return gen.parent


def test_ac_docs_005_rendered_output_absent_from_version_control(tmp_path, monkeypatch):
    if shutil.which("git") is None:
        pytest.skip("git is not available")

    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _write_graph(repo_root)

    # A temporary repository holding the committed inputs.
    assert _git(["init", "-q"], repo_root).returncode == 0
    _git(["config", "user.email", "test@example.invalid"], repo_root)
    _git(["config", "user.name", "test"], repo_root)
    assert _git(["add", "-A"], repo_root).returncode == 0
    commit = _git(["commit", "-q", "-m", "fixture"], repo_root)
    assert commit.returncode == 0, commit.stderr

    # A successful render to the default output location.
    monkeypatch.chdir(repo_root)
    rc = docs_site_renderer.main(["--repo-root=" + str(repo_root)])
    assert rc == 0

    out_dir = repo_root / "dist" / "docs-site"
    assert out_dir.is_dir(), "default output dir dist/docs-site/ was not produced"
    rendered = [p for p in out_dir.rglob("*") if p.is_file()]
    assert rendered, "render produced no files"
    index_html = out_dir / "index.html"
    assert index_html.is_file()

    # The render writes nothing under gen/ (a committed location).
    assert not (repo_root / "gen").exists() or not any(
        p.is_file() for p in (repo_root / "gen").rglob("*")
    )

    # The rendered output is not part of the committed files.
    tracked = _git(["ls-files", "-z"], repo_root)
    assert tracked.returncode == 0
    tracked_paths = [p for p in tracked.stdout.split("\0") if p]
    assert not any(p.startswith("dist/") for p in tracked_paths)

    # The tool's own repository commits no rendered site either.
    tool_root = _tool_root()
    if tool_root is None:
        pytest.skip("docs_site_renderer is not under a gen/ directory")
    top = _git(["rev-parse", "--show-toplevel"], tool_root)
    if top.returncode != 0:
        pytest.skip("the tool root is not a git working tree")

    in_dist = _git(["ls-files", "-z", "--", "dist/docs-site"], tool_root)
    assert in_dist.returncode == 0
    assert [p for p in in_dist.stdout.split("\0") if p] == [], (
        "rendered output under dist/docs-site/ is committed"
    )

    all_tracked = _git(["ls-files", "-z"], tool_root)
    assert all_tracked.returncode == 0
    rendered_index = index_html.read_bytes()
    for rel in [p for p in all_tracked.stdout.split("\0") if p]:
        if not rel.endswith(".html"):
            continue
        candidate = tool_root / rel
        if candidate.is_file():
            assert candidate.read_bytes() != rendered_index, (
                "a rendered page is committed at " + repr(rel)
            )