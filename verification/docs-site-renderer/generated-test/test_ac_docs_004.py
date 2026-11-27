# hotdocs-criterion: sha256:11753bf6e627326c0db311a2fa3db47ca12e2cc0e2aea139d82d963a5d1ef4c0
import importlib
import json
import os
import sys
from pathlib import Path

import docs_site_renderer


# ---------------------------------------------------------------------------
# File-read recorder built on the interpreter's "open" audit event.
# The hook is installed once (audit hooks cannot be removed) and records only
# while a test has switched recording on.
# ---------------------------------------------------------------------------

_STATE = {"recording": False, "in_hook": False, "events": []}

_CODE_SUFFIXES = (".py", ".pyc", ".pyo", ".so", ".pyd", ".dylib", ".pth")


def _audit_hook(event, args):
    if event != "open" or not _STATE["recording"] or _STATE["in_hook"]:
        return
    _STATE["in_hook"] = True
    try:
        path = args[0] if args else None
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else 0
        if isinstance(path, (str, bytes, os.PathLike)):
            try:
                text = os.fsdecode(path)
            except Exception:
                text = None
            if text is not None:
                _STATE["events"].append((os.path.abspath(text), mode, flags))
    finally:
        _STATE["in_hook"] = False


sys.addaudithook(_audit_hook)


def _is_write(mode, flags):
    if isinstance(mode, str):
        return any(c in mode for c in "wax+")
    if isinstance(flags, int):
        return bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC))
    return False


def _real(p):
    return os.path.realpath(str(p))


def _is_under(path, root):
    root = root.rstrip(os.sep) + os.sep
    return path == root.rstrip(os.sep) or path.startswith(root)


def _cli_main():
    main = getattr(docs_site_renderer, "main", None)
    if callable(main):
        return main
    cli = importlib.import_module("docs_site_renderer.cli")
    return cli.main


def _graph_dict():
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
                "documents": {},
            },
            "comp-foo": {
                "type": "component",
                "verification": {
                    "requirement_results": {"R-FOO-001": "pass"},
                    "criteria": [
                        {"id": "AC-FOO-001", "kind": "generated-test", "result": "pass"}
                    ],
                },
                "provenance": {"generated_at": "2026-01-01T00:00:00Z", "model": "anthropic:x"},
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "# Foo\n\nThe foo component.\n",
                    "requirements/R-FOO-001.md": "# R-FOO-001\n\nFoo MUST work.\n",
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


def test_ac_docs_004_reads_only_corpus_graph_and_own_asset(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    graph_file = repo_root / "verification" / "corpus-graph.json"
    graph_file.write_bytes(
        (json.dumps(_graph_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    )
    out_dir = tmp_path / "out"

    main = _cli_main()
    monkeypatch.chdir(repo_root)

    asset = _real(Path(docs_site_renderer.__file__).resolve().parent.parent / "static" / "app.js")
    allowed = {_real(graph_file), asset}
    out_root = _real(tmp_path) + os.sep + "out"

    _STATE["events"] = []
    _STATE["recording"] = True
    try:
        code = main(["--repo-root=" + str(repo_root), "--out=" + str(out_dir)])
    finally:
        _STATE["recording"] = False

    assert code == 0
    assert (out_dir / "index.html").is_file()

    disallowed = []
    for path, mode, flags in list(_STATE["events"]):
        if _is_write(mode, flags):
            continue
        real = _real(path)
        if real in allowed:
            continue
        if _is_under(real, out_root):
            continue  # its own freshly written output
        if real.startswith("/dev/"):
            continue
        if os.path.isdir(real):
            continue
        if real.endswith(_CODE_SUFFIXES):
            continue  # Python import machinery loading code, not data
        disallowed.append(real)

    assert disallowed == []