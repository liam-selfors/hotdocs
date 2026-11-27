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

_FILTERS = (
    ("all", "all"),
    ("passing", "passing"),
    ("failing", "failing"),
    ("missing", "missing"),
    ("not-attempted", "not yet attempted"),
)

_LABELS = {
    "passing": "passing",
    "failing": "failing",
    "missing": "missing",
    "not-attempted": "not yet attempted",
}

_CSS = """
body { font-family: sans-serif; margin: 1.5em; color: #222; }
.filters button { margin-right: 0.4em; }
ul.nodes { list-style: none; padding: 0; }
li.node { margin: 0.4em 0; padding: 0.5em 0.8em; border-left: 0.5em solid #999; }
li.node[hidden] { display: none; }
.status-passing { background: #e6f6e6; border-left-color: #2e8b2e; }
.status-failing { background: #fbe3e3; border-left-color: #c0392b; }
.status-missing { background: #fff2d9; border-left-color: #e08e0b; }
.status-not-attempted { background: #ececec; border-left-color: #7f7f7f; font-style: italic; }
.node-id { font-weight: bold; margin-right: 0.6em; }
.node-kind { color: #555; margin-right: 0.6em; }
.status-label { text-transform: none; }
.attempt { font-family: monospace; margin-left: 1em; }
.retry-feedback { display: block; margin-left: 1em; font-family: monospace; }
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


def _load_tracker(repo_root):
    base = Path(repo_root) / "gen" / "provenance-tracker"
    if not base.is_dir():
        base = _tool_root() / "gen" / "provenance-tracker"
    path = base / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


def _read_attempts(repo_root, component_id):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def _component_node(tracker, repo_root, component_id, result):
    if _get(result, "hit"):
        verification = _get(result, "verification_report")
        license_scan = _get(result, "license_scan")
        if _get(verification, "overall") == "pass" and not _get(license_scan, "blocked"):
            status = "passing"
            attempts = []
        else:
            status = "failing"
            attempts = _read_attempts(repo_root, component_id)
    else:
        attempts = _read_attempts(repo_root, component_id)
        status = "missing" if attempts else "not-attempted"
    retry_feedback = []
    if status in ("failing", "missing"):
        retry_feedback = list(tracker.last_requirement_failures(component_id, repo_root))
    return {
        "id": component_id,
        "kind": "component",
        "status": status,
        "attempts": attempts,
        "retry_feedback": retry_feedback,
    }


def _capability_node(capability_id, result):
    report = _get(result, "capability_scenario_report")
    entry = _get(report, capability_id) if report is not None else None
    status = "passing" if _get(entry, "overall") == "pass" else "failing"
    return {
        "id": capability_id,
        "kind": "capability",
        "status": status,
        "attempts": [],
        "retry_feedback": [],
    }


def _esc(value):
    return html.escape(str(value), quote=True)


def _render_node(node):
    status = node["status"]
    parts = [
        '<li class="node status-%s" data-node-id="%s" data-kind="%s" data-status="%s">'
        % (_esc(status), _esc(node["id"]), _esc(node["kind"]), _esc(status)),
        '<span class="node-id">%s</span>' % _esc(node["id"]),
        '<span class="node-kind">%s</span>' % _esc(node["kind"]),
        '<span class="status-label">%s</span>' % _esc(_LABELS[status]),
    ]
    for attempt in node["attempts"]:
        attempt_id = attempt.get("attempt_id", "")
        parts.append(
            '<div class="attempt" data-attempt-id="%s">%s</div>'
            % (_esc(attempt_id), _esc(attempt_id))
        )
    if node["retry_feedback"]:
        parts.append(
            '<code class="retry-feedback">%s</code>'
            % _esc("--retry-feedback=" + ",".join(node["retry_feedback"]))
        )
    parts.append("</li>")
    return "".join(parts)


def _render_page(snapshot, asset_text):
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Provenance tracker</title>",
        "<style>" + _CSS + "</style>",
        "</head>",
        "<body>",
        "<h1>Provenance tracker</h1>",
        '<p class="scope">Scope: <span class="scope-name">%s</span></p>'
        % _esc(snapshot["scope"]),
    ]
    if snapshot["changed_ids"] is not None:
        lines.append(
            '<p class="changed-ids">Changed: %s</p>'
            % _esc(", ".join(snapshot["changed_ids"]))
        )
    lines.append(
        '<p class="ready">%s</p>' % ("ready" if snapshot["ready"] else "not ready")
    )
    lines.append('<ul class="not-ready-reasons">')
    for reason in snapshot["not_ready_reasons"]:
        lines.append("<li>%s</li>" % _esc(reason))
    lines.append("</ul>")
    lines.append('<div class="filters">')
    for value, label in _FILTERS:
        lines.append(
            '<button type="button" data-filter="%s">%s</button>' % (value, label)
        )
    lines.append("</div>")
    lines.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        lines.append(_render_node(node))
    lines.append("</ul>")
    data = json.dumps(snapshot, ensure_ascii=False).replace("</", "<\\/")
    lines.append(
        '<script type="application/json" id="tracker-snapshot">' + data + "</script>"
    )
    lines.append(
        '<script type="module">' + asset_text + "\ninit(document);\n" + "</script>"
    )
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def render_tracker_ui(out_dir, repo_root, changed_ids=None, model=None, seed=0,
                      llm_backend=None):
    out_dir = Path(out_dir)
    repo_root = Path(repo_root)
    graph_path = repo_root / "verification" / "corpus-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    tracker = _load_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)

    nodes = []
    for component_id, result in _get(report, "components").items():
        nodes.append(_component_node(tracker, repo_root, component_id, result))
    for capability_id, result in _get(report, "capabilities").items():
        nodes.append(_capability_node(capability_id, result))
    nodes.sort(key=lambda node: node["id"])
    ids = {node["id"] for node in nodes}
    edges = [
        edge for edge in graph.get("edges", [])
        if edge["from"] in ids and edge["to"] in ids
    ]
    snapshot = {
        "scope": _get(report, "scope"),
        "changed_ids": changed_ids,
        "ready": _get(report, "ready"),
        "not_ready_reasons": list(_get(report, "not_ready_reasons")),
        "nodes": nodes,
        "edges": edges,
    }
    asset_text = (Path(__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(
        _render_page(snapshot, asset_text), encoding="utf-8"
    )
    return snapshot


class _UsageError(Exception):
    pass


def _parse(argv):
    if list(argv[:3]) != ["track", "ui", "build"]:
        raise _UsageError("expected 'track ui build'")
    rest = list(argv[3:])
    values = {}
    changed = None
    i = 0
    while i < len(rest):
        token = rest[i]
        name, sep, value = token.partition("=")
        if name not in _FLAGS:
            raise _UsageError("unknown argument %s" % token)
        if not sep:
            if i + 1 >= len(rest):
                raise _UsageError("%s needs a value" % name)
            value = rest[i + 1]
            i += 1
        i += 1
        if name == "--changed":
            changed = (changed or []) + value.split(",")
        else:
            values[name] = value
    try:
        seed = int(values.get("--seed", "0"))
    except ValueError:
        raise _UsageError("--seed must be an integer")
    repo_root = Path(values.get("--repo-root", "."))
    out_dir = Path(values.get("--out", repo_root / ".hotdocs" / "ui"))
    return out_dir, repo_root, changed, values.get("--model"), seed


def _usage_error(cause):
    print("usage error: %s" % cause, file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        out_dir, repo_root, changed, model, seed = _parse(argv)
    except _UsageError as exc:
        return _usage_error(exc)
    try:
        render_tracker_ui(out_dir, repo_root, changed, model, seed)
    except FileNotFoundError as exc:
        return _usage_error(
            "missing %s; run hotdocs corpus-graph build first" % exc.filename
        )
    except json.JSONDecodeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except ValueError as exc:
        return _usage_error(exc)
    print(out_dir / "index.html")
    return 0
