"""Provenance Tracker UI: a static, self-contained corpus-readiness page."""

import html
import importlib.util
import json
import sys
from pathlib import Path

USAGE = (
    "usage: hotdocs track ui build [--changed=<id>...] [--repo-root=<dir>] "
    "[--out=<dir>] [--model=<model>] [--seed=<n>]"
)

_FLAGS = ("--changed", "--repo-root", "--out", "--model", "--seed")

_STATUS_LABELS = {
    "passing": "passing",
    "failing": "failing",
    "missing": "missing",
    "not-attempted": "not yet attempted",
}

_FILTERS = ("all", "passing", "failing", "missing", "not-attempted")
_FILTER_LABELS = {"all": "all", **_STATUS_LABELS}

_CSS = """
body { font-family: sans-serif; margin: 1.5em; }
ul.nodes { list-style: none; padding: 0; }
li.node { margin: 0.4em 0; padding: 0.5em; border-left: 0.5em solid; }
li.node[hidden] { display: none; }
.status-passing { border-color: #2e7d32; background: #e8f5e9; }
.status-failing { border-color: #c62828; background: #ffebee; }
.status-missing { border-color: #ef6c00; background: #fff3e0; }
.status-not-attempted { border-color: #757575; background: #f5f5f5; font-style: italic; }
.node-id { font-weight: bold; }
.attempt { font-family: monospace; margin-left: 1em; }
.retry-feedback { display: block; margin-left: 1em; }
"""


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_provenance_tracker(repo_root):
    module_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not module_dir.is_dir():
        module_dir = _tool_root() / "gen" / "provenance-tracker"
    path = module_dir / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


def _read_attempts(repo_root, component_id):
    attempt_dir = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(attempt_dir.glob("*.json"))
    ]


def _component_status(result):
    return (
        bool(_get(result, "hit"))
        and _get(_get(result, "verification_report"), "overall") == "pass"
        and _get(_get(result, "license_scan"), "blocked") is not True
        and _get(_get(result, "secret_scan"), "flagged") is not True
    )


def _capability_status(cap_id, result):
    report = _get(_get(result, "capability_scenario_report"), cap_id)
    if _get(report, "overall") == "pass":
        return "passing"
    return "failing"


def _build_nodes(tracker, report, repo_root):
    nodes = []
    components = _get(report, "components") or {}
    capabilities = _get(report, "capabilities") or {}
    for comp_id in components:
        result = components[comp_id]
        attempts = []
        feedback = []
        if _component_status(result):
            status = "passing"
        else:
            attempts = _read_attempts(repo_root, comp_id)
            if _get(result, "hit"):
                status = "failing"
            elif attempts:
                status = "missing"
            else:
                status = "not-attempted"
            if status in ("failing", "missing"):
                feedback = list(tracker.last_requirement_failures(comp_id, repo_root))
        nodes.append({
            "id": comp_id, "kind": "component", "status": status,
            "attempts": attempts, "retry_feedback": feedback,
        })
    for cap_id in capabilities:
        nodes.append({
            "id": cap_id, "kind": "capability",
            "status": _capability_status(cap_id, capabilities[cap_id]),
            "attempts": [], "retry_feedback": [],
        })
    nodes.sort(key=lambda n: n["id"])
    return nodes


def _render_node(node):
    e = html.escape
    status = node["status"]
    parts = [
        f'<li class="node status-{e(status)}" data-node-id="{e(node["id"])}" '
        f'data-kind="{e(node["kind"])}" data-status="{e(status)}">',
        f'<span class="node-id">{e(node["id"])}</span> ',
        f'<span class="node-kind">{e(node["kind"])}</span> ',
        f'<span class="status-label">{e(_STATUS_LABELS[status])}</span>',
    ]
    for attempt in node["attempts"]:
        attempt_id = str(_get(attempt, "attempt_id"))
        parts.append(
            f'<div class="attempt" data-attempt-id="{e(attempt_id)}">{e(attempt_id)}</div>'
        )
    if node["retry_feedback"]:
        text = "--retry-feedback=" + ",".join(node["retry_feedback"])
        parts.append(f'<code class="retry-feedback">{e(text)}</code>')
    parts.append("</li>")
    return "".join(parts)


def _render_page(snapshot, script_text):
    e = html.escape
    snapshot_json = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    snapshot_json = snapshot_json.replace("</", "<\\/")
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Provenance Tracker</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        "<h1>Provenance Tracker</h1>",
        f'<p class="scope">scope: {e(snapshot["scope"])}</p>',
    ]
    if snapshot["changed_ids"] is not None:
        lines.append(
            f'<p class="changed-ids">changed: {e(", ".join(snapshot["changed_ids"]))}</p>'
        )
    lines.append('<ul class="not-ready-reasons">')
    for reason in snapshot["not_ready_reasons"]:
        lines.append(f"<li>{e(reason)}</li>")
    lines.append("</ul>")
    lines.append('<div class="filters">')
    for f in _FILTERS:
        lines.append(f'<button type="button" data-filter="{f}">{_FILTER_LABELS[f]}</button>')
    lines.append("</div>")
    lines.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        lines.append(_render_node(node))
    lines.append("</ul>")
    lines.append(
        f'<script type="application/json" id="tracker-snapshot">{snapshot_json}</script>'
    )
    lines.append('<script type="module">' + script_text + "\ninit(document);\n" + "</script>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def render_tracker_ui(out_dir, repo_root, changed_ids=None, model=None, seed=0,
                      llm_backend=None):
    graph_path = Path(repo_root) / "verification" / "corpus-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)
    nodes = _build_nodes(tracker, report, repo_root)
    node_ids = {n["id"] for n in nodes}
    edges = [
        edge for edge in graph["edges"]
        if edge["from"] in node_ids and edge["to"] in node_ids
    ]
    snapshot = {
        "scope": _get(report, "scope"),
        "changed_ids": changed_ids,
        "ready": _get(report, "ready"),
        "not_ready_reasons": list(_get(report, "not_ready_reasons")),
        "nodes": nodes,
        "edges": edges,
    }
    script_text = (Path(__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    page = _render_page(snapshot, script_text)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_bytes(page.encode("utf-8"))
    return snapshot


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv[:3] != ["track", "ui", "build"]:
        return _usage_error("expected 'track ui build'")
    args = argv[3:]
    changed = []
    opts = {}
    i = 0
    while i < len(args):
        token = args[i]
        name, eq, value = token.partition("=")
        if name not in _FLAGS:
            return _usage_error(f"unknown argument {token}")
        if not eq:
            if i + 1 >= len(args):
                return _usage_error(f"{name} requires a value")
            i += 1
            value = args[i]
        if name == "--changed":
            changed.extend(value.split(","))
        else:
            opts[name] = value
        i += 1
    try:
        seed = int(opts.get("--seed", "0"))
    except ValueError:
        return _usage_error(f"--seed must be an integer: {opts['--seed']}")
    repo_root = Path(opts.get("--repo-root", "."))
    out_dir = Path(opts.get("--out", str(repo_root / ".hotdocs" / "ui")))
    graph_path = repo_root / "verification" / "corpus-graph.json"
    if not graph_path.is_file():
        return _usage_error(f"missing {graph_path}; run hotdocs corpus-graph build first")
    changed_ids = changed if changed else None
    try:
        render_tracker_ui(out_dir, repo_root, changed_ids, opts.get("--model"), seed)
    except json.JSONDecodeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        return _usage_error(str(exc))
    print(out_dir / "index.html")
    return 0
