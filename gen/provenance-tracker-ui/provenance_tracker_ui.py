"""Provenance Tracker UI: a static, self-contained corpus-readiness page."""

from __future__ import annotations

import html
import importlib.util
import json
import sys
from pathlib import Path

USAGE = (
    "usage: hotdocs track ui build [--changed=<id>...] [--repo-root=<dir>] "
    "[--out=<dir>] [--model=<model>] [--seed=<n>]"
)

STATUS_LABELS = {
    "passing": "passing",
    "failing": "failing",
    "missing": "missing",
    "not-attempted": "not yet attempted",
}

FILTERS = (
    ("all", "all"),
    ("passing", "passing"),
    ("failing", "failing"),
    ("missing", "missing"),
    ("not-attempted", "not yet attempted"),
)

CSS = """body { font-family: sans-serif; margin: 2em; }
ul.nodes { list-style: none; padding: 0; }
li.node { margin: 0.4em 0; padding: 0.5em; border-left: 6px solid; }
li.node.status-passing { border-color: #2e7d32; background: #e8f5e9; }
li.node.status-failing { border-color: #c62828; background: #ffebee; }
li.node.status-missing { border-color: #ef6c00; background: #fff3e0; }
li.node.status-not-attempted { border-color: #757575; background: #f5f5f5; font-style: italic; }
.node-id { font-weight: bold; margin-right: 0.5em; }
.node-kind { margin-right: 0.5em; color: #555; }
.retry-feedback { display: block; margin-top: 0.3em; font-family: monospace; }
"""


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_tracker(repo_root: Path):
    rel = Path("gen") / "provenance-tracker"
    directory = repo_root / rel
    if not directory.is_dir():
        directory = _tool_root() / rel
    path = directory / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


def _read_attempts(repo_root: Path, component_id: str) -> list:
    directory = repo_root / ".hotdocs" / "attempts" / component_id
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def _component_node(node_id, result, repo_root, tracker) -> dict:
    attempts = _read_attempts(repo_root, node_id)
    if _get(result, "hit"):
        overall = _get(_get(result, "verification_report"), "overall")
        blocked = _get(_get(result, "license_scan"), "blocked")
        status = "passing" if overall == "pass" and not blocked else "failing"
    elif attempts:
        status = "missing"
    else:
        status = "not-attempted"
    feedback = []
    if status == "passing":
        attempts = []
    elif status in ("failing", "missing"):
        feedback = list(tracker.last_requirement_failures(node_id, repo_root))
    return {
        "id": node_id,
        "kind": "component",
        "status": status,
        "attempts": attempts,
        "retry_feedback": feedback,
    }


def _capability_node(node_id, result) -> dict:
    report = _get(result, "capability_scenario_report")
    overall = _get(_get(report, node_id), "overall")
    return {
        "id": node_id,
        "kind": "capability",
        "status": "passing" if overall == "pass" else "failing",
        "attempts": [],
        "retry_feedback": [],
    }


def _render_node(node: dict) -> str:
    esc = html.escape
    status = node["status"]
    parts = [
        f'<li class="node status-{esc(status)}" data-node-id="{esc(node["id"])}" '
        f'data-kind="{esc(node["kind"])}" data-status="{esc(status)}">',
        f'<span class="node-id">{esc(node["id"])}</span>',
        f'<span class="node-kind">{esc(node["kind"])}</span>',
        f'<span class="status-label">{esc(STATUS_LABELS[status])}</span>',
    ]
    items = [
        f'<li class="attempt" data-attempt-id="{esc(str(_get(a, "attempt_id")))}">'
        f'{esc(str(_get(a, "attempt_id")))}</li>'
        for a in node["attempts"]
    ]
    if items:
        parts.append('<ol class="attempts">' + "".join(items) + "</ol>")
    if node["retry_feedback"]:
        text = "--retry-feedback=" + ",".join(node["retry_feedback"])
        parts.append(f'<code class="retry-feedback">{esc(text)}</code>')
    parts.append("</li>")
    return "".join(parts)


def _render_page(snapshot: dict, script: str) -> str:
    esc = html.escape
    data = json.dumps(snapshot, sort_keys=True, ensure_ascii=False).replace("</", "<\\/")
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Provenance Tracker</title>",
        "<style>",
        CSS,
        "</style>",
        "</head>",
        "<body>",
        "<h1>Provenance Tracker</h1>",
        f'<p class="scope">Scope: {esc(str(snapshot["scope"]))}</p>',
    ]
    if snapshot["changed_ids"] is not None:
        changed = ", ".join(snapshot["changed_ids"])
        lines.append(f'<p class="changed-ids">Changed: {esc(changed)}</p>')
    lines.append('<div class="filters">')
    for value, label in FILTERS:
        lines.append(f'<button type="button" data-filter="{value}">{label}</button>')
    lines.append("</div>")
    lines.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        lines.append(_render_node(node))
    lines.append("</ul>")
    lines.append(f'<script type="application/json" id="tracker-snapshot">{data}</script>')
    lines.append('<script type="module">' + script + "\ninit(document);\n" + "</script>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def render_tracker_ui(
    out_dir: Path,
    repo_root: Path,
    changed_ids: list[str] | None = None,
    model: str | None = None,
    seed: int = 0,
    llm_backend=None,
) -> dict:
    repo_root = Path(repo_root)
    out_dir = Path(out_dir)
    tracker = _load_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)
    graph_path = repo_root / "verification" / "corpus-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    components = _get(report, "components")
    capabilities = _get(report, "capabilities")
    entries = {}
    for node_id, result in components.items():
        entries[node_id] = ("component", result)
    for node_id, result in capabilities.items():
        entries[node_id] = ("capability", result)

    nodes = []
    for node_id in sorted(entries):
        kind, result = entries[node_id]
        if kind == "component":
            nodes.append(_component_node(node_id, result, repo_root, tracker))
        else:
            nodes.append(_capability_node(node_id, result))

    ids = set(entries)
    edges = [e for e in graph["edges"] if e["from"] in ids and e["to"] in ids]

    snapshot = {
        "scope": _get(report, "scope"),
        "changed_ids": changed_ids,
        "ready": _get(report, "ready"),
        "not_ready_reasons": _get(report, "not_ready_reasons"),
        "nodes": nodes,
        "edges": edges,
    }

    script = (Path(__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    page = _render_page(snapshot, script)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_bytes(page.encode("utf-8"))
    return snapshot


class _UsageError(Exception):
    pass


_FLAGS = ("--changed", "--repo-root", "--out", "--model", "--seed")


def _parse(argv: list[str]) -> dict:
    if list(argv[:3]) != ["track", "ui", "build"]:
        raise _UsageError("expected 'track ui build'")
    opts = {"--changed": None, "--repo-root": ".", "--out": None, "--model": None, "--seed": 0}
    i = 3
    while i < len(argv):
        token = argv[i]
        name, eq, value = token.partition("=")
        if name not in _FLAGS:
            raise _UsageError(f"unknown argument {token}")
        if not eq:
            i += 1
            if i >= len(argv):
                raise _UsageError(f"{name} requires a value")
            value = argv[i]
        i += 1
        if name == "--changed":
            opts[name] = (opts[name] or []) + value.split(",")
        elif name == "--seed":
            try:
                opts[name] = int(value)
            except ValueError:
                raise _UsageError(f"--seed must be an integer, got {value}")
        else:
            opts[name] = value
    return opts


def _usage(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        opts = _parse(argv)
    except _UsageError as exc:
        return _usage(str(exc))
    repo_root = Path(opts["--repo-root"])
    out_dir = Path(opts["--out"]) if opts["--out"] is not None else repo_root / ".hotdocs" / "ui"
    graph_path = repo_root / "verification" / "corpus-graph.json"
    if not graph_path.is_file():
        return _usage(f"missing {graph_path}; run hotdocs corpus-graph build first")
    try:
        render_tracker_ui(
            out_dir, repo_root, opts["--changed"], opts["--model"], opts["--seed"]
        )
    except json.JSONDecodeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        return _usage(str(exc))
    print(out_dir / "index.html")
    return 0
