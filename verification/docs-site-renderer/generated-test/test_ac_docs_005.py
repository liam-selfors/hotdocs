# hotdocs-criterion: sha256:aef796b945467f29079817d4cb76c07ba4e5f0dc3632c515d8de95106fcd835a
"""AC-DOCS-005: after a successful render, the rendered output directory
is absent from version control (R-DOCS-005: the rendered site is a CI
build artifact, never committed)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import docs_site_renderer


DEFAULT_OUT = "dist/docs-site"


def _git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def _committed_files(cwd):
    result = _git(cwd, "ls-files", "-z")
    assert result.returncode == 0, result.stderr
    return [p for p in result.stdout.split("\0") if p]


def _under(path, prefix):
    norm = path.replace("\\", "/")
    return norm == prefix or norm.startswith(prefix.rstrip("/") + "/")


def _graph():
    return {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {"component.md": "# Foo\n\nThe foo component.\n"},
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


def test_ac_docs_005_rendered_output_absent_from_version_control(tmp_path, monkeypatch):
    if shutil.which("git") is None:
        pytest.skip("git is not available")

    from docs_site_renderer import cli

    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(_graph(), sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    init = _git(repo_root, "init", "-q")
    assert init.returncode == 0, init.stderr
    assert _git(repo_root, "add", "-A").returncode == 0
    commit = _git(repo_root, "commit", "-q", "-m", "fixture")
    assert commit.returncode == 0, commit.stderr

    head_before = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    committed_before = sorted(_committed_files(repo_root))

    # Given a successful render (default --out, resolved the same whether
    # relative to the current directory or to --repo-root).
    monkeypatch.chdir(repo_root)
    code = cli.main(["--repo-root", str(repo_root)])
    assert code == 0
    out_dir = repo_root / DEFAULT_OUT
    assert out_dir.is_dir()
    assert any(out_dir.iterdir())

    # When the repository's committed files are checked,
    # Then the rendered output directory is absent from version control.
    head_after = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    assert head_after == head_before
    committed_after = sorted(_committed_files(repo_root))
    assert committed_after == committed_before
    assert [p for p in committed_after if _under(p, DEFAULT_OUT)] == []

    # The tool's own repository never commits the rendered site either.
    gen = next(
        (p for p in Path(docs_site_renderer.__file__).resolve().parents if p.name == "gen"),
        None,
    )
    if gen is not None:
        tool_root = gen.parent
        probe = _git(tool_root, "rev-parse", "--show-toplevel")
        if probe.returncode == 0:
            tool_committed = _committed_files(tool_root)
            assert [p for p in tool_committed if _under(p, DEFAULT_OUT)] == []