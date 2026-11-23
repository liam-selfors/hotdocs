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

STATUS_LABELS = {
    "passing": "passing",
    "failing": "failing",
    "missing": "missing",
    "not-attempted": "not yet attempted",
}

FILTERS = [
    ("all", "all"),
    ("passing", "passing"),
    ("failing", "failing"),
    ("missing", "missing"),
    ("not-attempted", "not yet attempted"),
]

CSS = """
body { font-family: sans-serif; margin: 1.5em; }
ul.nodes { list-style: none; padding: 0; }
li.node { margin: 0.3em 0; padding: 0.4em 0.6em; border-left: 0.5em solid; }
li.node .node-id { font-weight: bold; margin-right: 0.6em; }
li.node .node-kind { color: #555; margin-right: 0.6em; }
li.node .attempts, li.node .retry-feedback { display: block; margin-top: 0.3em; }
li.node .attempt { display: inline-block; margin-right: 0.6em; font-family: monospace; }
.retry-feedback { font-family: monospace; user-select: all; }
.status-passing { border-color: #2e7d32; background: #e8f5e9; }
.status-failing { border-color: #c62828; background: #ffebee; }
.status-missing { border-color: #ef6c00; background: #fff3e0; }
.status-not-attempted { border-color: #757575; background: #f5f5f5; font-style: italic; }
"""


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    gen_dir = next(p for p in Path(__file__).resolve().parents if p.name == "gen")
    return gen_dir.parent


def _load_tracker(repo_root):
    module_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not module_dir.is_dir():
        module_dir = _tool_root() / "gen" / "provenance-tracker"
    spec = importlib.util.spec_from_file_location(
        "provenance_tracker", module_dir / "provenance_tracker.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


def _read_attempts(repo_root, component_id):
    attempt_dir = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(attempt_dir.glob("*.json"))
    ]


def _component_status(result, attempts):
    if _get(result, "hit"):
        ok = (
            _get(_get(result, "verification_report"), "overall") == "pass"
            and not _get(_get(result, "license_scan"), "blocked")
            and not _get(_get(result, "secret_scan"), "flagged")
        )
        return "passing" if ok else "failing"
    return "missing" if attempts else "not-attempted"


def _capability_status(capability_id, result):
    report = _get(_get(result, "capability_scenario_report"), capability_id)
    return "passing" if _get(report, "overall") == "pass" else "failing"


def _esc(value):
    return html.escape(str(value), quote=True)


def _render_node(node):
    parts = [
        '<li class="node status-%s" data-node-id="%s" data-kind="%s" data-status="%s">'
        % (_esc(node["status"]), _esc(node["id"]), _esc(node["kind"]), _esc(node["status"])),
        '<span class="node-id">%s</span>' % _esc(node["id"]),
        '<span class="node-kind">%s</span>' % _esc(node["kind"]),
        '<span class="node-status">%s</span>' % _esc(STATUS_LABELS[node["status"]]),
    ]
    if node["attempts"]:
        parts.append('<span class="attempts">')
        for record in node["attempts"]:
            attempt_id = record.get("attempt_id")
            parts.append(
                '<span class="attempt" data-attempt-id="%s">%s</span>'
                % (_esc(attempt_id), _esc(attempt_id))
            )
        parts.append("</span>")
    if node["retry_feedback"]:
        parts.append(
            '<code class="retry-feedback">%s</code>'
            % _esc("--retry-feedback=" + ",".join(node["retry_feedback"]))
        )
    parts.append("</li>")
    return "".join(parts)


def _render_page(snapshot, asset_text):
    data = json.dumps(snapshot, sort_keys=True, ensure_ascii=True).replace("</", "<\\/")
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Provenance tracker</title>",
        "<style>" + CSS + "</style>",
        "</head>",
        "<body>",
        "<h1>Provenance tracker</h1>",
        '<p class="scope">scope: %s</p>' % _esc(snapshot["scope"]),
    ]
    if snapshot["changed_ids"] is not None:
        lines.append(
            '<p class="changed-ids">changed: %s</p>'
            % _esc(", ".join(snapshot["changed_ids"]))
        )
    lines.append('<div class="filters">')
    for value, label in FILTERS:
        lines.append(
            '<button type="button" data-filter="%s">%s</button>' % (_esc(value), _esc(label))
        )
    lines.append("</div>")
    lines.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        lines.append(_render_node(node))
    lines.append("</ul>")
    lines.append(
        '<script type="application/json" id="tracker-snapshot">' + data + "</script>"
    )
    lines.append(
        '<script type="module">' + asset_text + "\ninit(document);\n" + "</script>"
    )
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def render_tracker_ui(
    out_dir, repo_root, changed_ids=None, model=None, seed=0, llm_backend=None
):
    tracker = _load_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)

    graph_path = Path(repo_root) / "verification" / "corpus-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    nodes = []
    for component_id, result in (_get(report, "components") or {}).items():
        attempts = _read_attempts(repo_root, component_id)
        status = _component_status(result, attempts)
        retry_feedback = []
        if status in ("failing", "missing"):
            retry_feedback = list(tracker.last_requirement_failures(component_id, repo_root))
        nodes.append({
            "id": component_id,
            "kind": "component",
            "status": status,
            "attempts": [] if status == "passing" else attempts,
            "retry_feedback": retry_feedback,
        })
    for capability_id, result in (_get(report, "capabilities") or {}).items():
        nodes.append({
            "id": capability_id,
            "kind": "capability",
            "status": _capability_status(capability_id, result),
            "attempts": [],
            "retry_feedback": [],
        })
    nodes.sort(key=lambda node: node["id"])

    node_ids = {node["id"] for node in nodes}
    edges = [
        edge for edge in graph["edges"]
        if edge["from"] in node_ids and edge["to"] in node_ids
    ]

    snapshot = {
        "scope": _get(report, "scope"),
        "changed_ids": changed_ids,
        "ready": _get(report, "ready"),
        "not_ready_reasons": _get(report, "not_ready_reasons"),
        "nodes": nodes,
        "edges": edges,
    }

    asset_text = (Path(__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_bytes(_render_page(snapshot, asset_text).encode("utf-8"))
    return snapshot


class _UsageError(Exception):
    pass


def _parse(argv):
    if argv[:3] != ["track", "ui", "build"]:
        raise _UsageError("expected 'track ui build'")
    flags = {"--changed", "--repo-root", "--out", "--model", "--seed"}
    values = {"--changed": []}
    rest = argv[3:]
    i = 0
    while i < len(rest):
        token = rest[i]
        name, sep, value = token.partition("=")
        if name not in flags:
            raise _UsageError("unknown argument: %s" % token)
        if not sep:
            if i + 1 >= len(rest):
                raise _UsageError("%s requires a value" % name)
            i += 1
            value = rest[i]
        if name == "--changed":
            values["--changed"].extend(value.split(","))
        else:
            values[name] = value
        i += 1
    try:
        seed = int(values.get("--seed", "0"))
    except ValueError:
        raise _UsageError("--seed must be an integer")
    repo_root = Path(values.get("--repo-root", "."))
    out = values.get("--out")
    out_dir = Path(out) if out is not None else repo_root / ".hotdocs" / "ui"
    changed = values["--changed"] or None
    return out_dir, repo_root, changed, values.get("--model"), seed


def _usage_error(cause):
    print("usage error: %s" % cause, file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        out_dir, repo_root, changed, model, seed = _parse(list(argv))
    except _UsageError as exc:
        return _usage_error(str(exc))
    try:
        render_tracker_ui(out_dir, repo_root, changed, model, seed)
    except FileNotFoundError as exc:
        return _usage_error("missing %s" % exc.filename)
    except json.JSONDecodeError as exc:
        print("error: invalid JSON: %s" % exc, file=sys.stderr)
        return 1
    except ValueError as exc:
        return _usage_error(str(exc))
    print(out_dir / "index.html")
    return 0
