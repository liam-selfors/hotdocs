"""AC-DOCS-005 (Covers: R-DOCS-005).

Given a successful render
When the repository's committed files are checked
Then the rendered output directory is absent from version control
"""

import importlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import docs_site_renderer


def _cli_main():
    cli = importlib.import_module("docs_site_renderer.cli")
    return cli.main


def _corpus_graph_dict():
    return {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "VAR-FOO-URL": {"type": "var"},
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": True,
                "pinned_overrides": [],
                "owners": [],
                "documents": {
                    "component.md": "---\nid: comp-bar\ntitle: Bar\nstatus: draft\n"
                    "owners: [pipeline-team]\nsealed: true\nsource_path: legacy/bar/\n---\n\n# Bar\n",
                },
            },
            "comp-foo": {
                "type": "component",
                "verification": {
                    "requirement_results": {"R-FOO-001": "pass"},
                    "criteria": [
                        {"id": "AC-FOO-001", "kind": "generated-test", "result": "pass"}
                    ],
                },
                "provenance": {
                    "component_id": "comp-foo",
                    "generated_at": "2026-01-01T00:00:00Z",
                },
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "---\nid: comp-foo\ntitle: Foo\nstatus: draft\n"
                    "owners: [pipeline-team]\ndepends_on: [comp-bar]\n"
                    "realizes: [P-ZERO-EDIT]\nuses_var: [VAR-FOO-URL]\nsealed: false\n---\n\n# Foo\n",
                    "requirements/R-FOO-001.md": "**R-FOO-001** - MUST do foo.\n",
                },
            },
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


def _write_graph(repo_root: Path):
    ver = repo_root / "verification"
    ver.mkdir(parents=True, exist_ok=True)
    data = json.dumps(_corpus_graph_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    (ver / "corpus-graph.json").write_bytes(data.encode("utf-8"))


def _files_under(d: Path):
    return sorted(p for p in d.rglob("*") if p.is_file())


def _tool_root() -> Path:
    here = Path(docs_site_renderer.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent.parent


def _git_toplevel(start: Path):
    if shutil.which("git") is None:
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return Path(proc.stdout.strip())


def test_rendered_output_directory_absent_from_version_control(tmp_path, monkeypatch):
    main = _cli_main()

    # --- Given a successful render (explicit --out) ---
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_graph(repo_root)
    out_dir = tmp_path / "site-out"

    rc = main([f"--repo-root={repo_root}", f"--out={out_dir}"])
    assert rc == 0, f"render with explicit --out failed with exit code {rc}"
    rendered = _files_under(out_dir)
    assert rendered, "a successful render must write the static site into --out"

    # --- Given a successful render (default --out, isolated in a temp cwd) ---
    monkeypatch.chdir(repo_root)
    rc_default = main([f"--repo-root={repo_root}"])
    assert rc_default == 0, f"render with default --out failed with exit code {rc_default}"
    default_out = repo_root / "dist" / "docs-site"
    assert default_out.is_dir() and _files_under(default_out), (
        "default output location must be dist/docs-site/"
    )
    # The default output location is a build-artifact location, never gen/.
    assert not (repo_root / "gen").exists() or not _files_under(repo_root / "gen"), (
        "rendering must not write its output into gen/ (a committed location)"
    )

    # --- When the repository's committed files are checked ---
    tool_root = _tool_root()
    top = _git_toplevel(tool_root)
    if top is None:
        pytest.skip("tool root is not inside a git repository; cannot check committed files")

    proc = subprocess.run(
        ["git", "-C", str(tool_root), "ls-files", "-z", "--", "dist/docs-site"],
        capture_output=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    tracked = [p for p in proc.stdout.decode("utf-8", "replace").split("\0") if p]

    # --- Then the rendered output directory is absent from version control ---
    assert tracked == [], (
        "rendered docs-site output must not be committed; tracked files found: "
        f"{tracked[:20]}"
    )

    # And none of the files this render produced is tracked under the default
    # output location either.
    for f in _files_under(default_out):
        rel = f.relative_to(default_out).as_posix()
        check = subprocess.run(
            ["git", "-C", str(tool_root), "ls-files", "--error-unmatch", "--",
             f"dist/docs-site/{rel}"],
            capture_output=True,
            timeout=60,
        )
        assert check.returncode != 0, (
            f"rendered file dist/docs-site/{rel} is committed to version control"
        )