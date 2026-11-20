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

FILTERS = ["all", "passing", "failing", "missing", "not-attempted"]

CSS = """
body { font-family: sans-serif; margin: 2em; color: #222; }
ul.nodes { list-style: none; padding: 0; }
li.node { margin: 0.4em 0; padding: 0.5em 0.8em; border-left: 6px solid #999; }
li.node .node-id { font-weight: bold; }
li.node .node-kind { color: #555; margin-left: 0.5em; }
li.node .status-label { margin-left: 0.5em; font-style: italic; }
.status-passing { background: #e3f6e3; border-left-color: #2e8b2e; }
.status-failing { background: #fbe1e1; border-left-color: #c62828; }
.status-missing { background: #fff2d6; border-left-color: #e69500; }
.status-not-attempted { background: #ececec; border-left-color: #7a7a7a; border-left-style: dashed; }
.attempt { font-family: monospace; font-size: 0.9em; margin-left: 1em; }
.retry-feedback { display: block; font-family: monospace; margin: 0.3em 0 0 1em; }
.filters button { margin-right: 0.4em; }
"""


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _dep_dir(repo_root, slug):
    candidate = Path(repo_root) / "gen" / slug
    if candidate.is_dir():
        return candidate
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent / "gen" / slug


def _load_tracker(repo_root):
    path = _dep_dir(repo_root, "provenance-tracker") / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


def _read_attempts(repo_root, component_id):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    records = []
    for path in sorted(directory.glob("*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return records


def _component_status(result, attempts):
    if _get(result, "hit"):
        overall = _get(_get(result, "verification_report"), "overall")
        blocked = _get(_get(result, "license_scan"), "blocked")
        flagged = _get(_get(result, "secret_scan"), "flagged")
        if overall == "pass" and not blocked and not flagged:
            return "passing"
        return "failing"
    if attempts:
        return "missing"
    return "not-attempted"


def _capability_status(capability_id, result):
    report = _get(result, "capability_scenario_report")
    if _get(_get(report, capability_id), "overall") == "pass":
        return "passing"
    return "failing"


def _esc(value):
    return html.escape(str(value), quote=True)


def _render_node(node):
    status = node["status"]
    parts = [
        '<li class="node status-%s" data-node-id="%s" data-kind="%s" data-status="%s">'
        % (_esc(status), _esc(node["id"]), _esc(node["kind"]), _esc(status)),
        '<span class="node-id">%s</span>' % _esc(node["id"]),
        ' <span class="node-kind">%s</span>' % _esc(node["kind"]),
        ' <span class="status-label">%s</span>' % _esc(STATUS_LABELS[status]),
    ]
    for record in node["attempts"]:
        attempt_id = _get(record, "attempt_id")
        parts.append(
            '<div class="attempt" data-attempt-id="%s">%s</div>'
            % (_esc(attempt_id), _esc(attempt_id))
        )
    if node["retry_feedback"]:
        parts.append(
            '<code class="retry-feedback">--retry-feedback=%s</code>'
            % _esc(",".join(node["retry_feedback"]))
        )
    parts.append("</li>")
    return "".join(parts)


def _render_page(snapshot, changed_ids, script_text):
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
    ]
    scope_line = '<p class="scope">Scope: <span class="scope-name">%s</span>' % _esc(
        snapshot["scope"]
    )
    if changed_ids is not None:
        scope_line += ' <span class="changed-ids">changed: %s</span>' % _esc(
            ", ".join(changed_ids)
        )
    lines.append(scope_line + "</p>")
    lines.append(
        '<p class="readiness">%s</p>' % ("ready" if snapshot["ready"] else "not ready")
    )
    lines.append('<ul class="not-ready-reasons">')
    for reason in snapshot["not_ready_reasons"]:
        lines.append('<li class="reason">%s</li>' % _esc(reason))
    lines.append("</ul>")
    lines.append('<div class="filters">')
    for f in FILTERS:
        lines.append(
            '<button type="button" data-filter="%s">%s</button>'
            % (_esc(f), _esc(STATUS_LABELS.get(f, f)))
        )
    lines.append("</div>")
    lines.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        lines.append(_render_node(node))
    lines.append("</ul>")
    lines.append('<ul class="edges">')
    for edge in snapshot["edges"]:
        lines.append(
            '<li class="edge">%s -&gt; %s (%s)</li>'
            % (_esc(edge["from"]), _esc(edge["to"]), _esc(edge["kind"]))
        )
    lines.append("</ul>")
    data = json.dumps(snapshot, sort_keys=True, ensure_ascii=True).replace("</", "<\\/")
    lines.append(
        '<script type="application/json" id="tracker-snapshot">' + data + "</script>"
    )
    lines.append(
        '<script type="module">' + script_text + "\ninit(document);\n" + "</script>"
    )
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def render_tracker_ui(
    out_dir,
    repo_root,
    changed_ids=None,
    model=None,
    seed=0,
    llm_backend=None,
):
    tracker = _load_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)

    graph_path = Path(repo_root) / "verification" / "corpus-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    nodes = []
    components = _get(report, "components")
    for component_id, result in components.items():
        attempts = _read_attempts(repo_root, component_id)
        status = _component_status(result, attempts)
        node = {
            "id": component_id,
            "kind": "component",
            "status": status,
            "attempts": [],
            "retry_feedback": [],
        }
        if status in ("failing", "missing"):
            node["attempts"] = attempts
            node["retry_feedback"] = list(
                tracker.last_requirement_failures(component_id, repo_root)
            )
        nodes.append(node)
    capabilities = _get(report, "capabilities")
    for capability_id, result in capabilities.items():
        nodes.append(
            {
                "id": capability_id,
                "kind": "capability",
                "status": _capability_status(capability_id, result),
                "attempts": [],
                "retry_feedback": [],
            }
        )
    nodes.sort(key=lambda n: n["id"])
    ids = {n["id"] for n in nodes}
    edges = [e for e in graph["edges"] if e["from"] in ids and e["to"] in ids]

    snapshot = {
        "scope": _get(report, "scope"),
        "changed_ids": changed_ids,
        "ready": _get(report, "ready"),
        "not_ready_reasons": list(_get(report, "not_ready_reasons")),
        "nodes": nodes,
        "edges": edges,
    }

    script_text = (Path(__file__).parent / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    page = _render_page(snapshot, changed_ids, script_text)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_bytes(page.encode("utf-8"))
    return snapshot


class _UsageError(Exception):
    pass


def _parse(argv):
    if argv[:3] != ["track", "ui", "build"]:
        raise _UsageError("expected 'track ui build'")
    opts = {"changed": None, "repo-root": ".", "out": None, "model": None, "seed": 0}
    rest = argv[3:]
    i = 0
    while i < len(rest):
        token = rest[i]
        name, sep, value = token.partition("=")
        flag = name[2:]
        if not name.startswith("--") or flag not in opts:
            raise _UsageError("unknown argument: %s" % token)
        if not sep:
            i += 1
            if i >= len(rest):
                raise _UsageError("%s requires a value" % name)
            value = rest[i]
        if flag == "changed":
            opts["changed"] = (opts["changed"] or []) + value.split(",")
        elif flag == "seed":
            try:
                opts["seed"] = int(value)
            except ValueError:
                raise _UsageError("--seed must be an integer: %s" % value)
        else:
            opts[flag] = value
        i += 1
    return opts


def _usage_error(cause):
    print("usage error: %s" % cause, file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        opts = _parse(list(argv))
    except _UsageError as exc:
        return _usage_error(exc)
    repo_root = Path(opts["repo-root"])
    out_dir = Path(opts["out"]) if opts["out"] is not None else repo_root / ".hotdocs" / "ui"
    try:
        render_tracker_ui(
            out_dir, repo_root, opts["changed"], opts["model"], opts["seed"]
        )
    except json.JSONDecodeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        return _usage_error("missing %s" % exc.filename)
    except ValueError as exc:
        return _usage_error(exc)
    print(out_dir / "index.html")
    return 0
