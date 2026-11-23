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

CSS = (
    "body{font-family:sans-serif;margin:1.5em;}"
    "ul.nodes{list-style:none;padding:0;}"
    "li.node{margin:0.4em 0;padding:0.4em 0.6em;border-left:6px solid;}"
    ".status-passing{border-color:#2e7d32;background:#e8f5e9;}"
    ".status-failing{border-color:#c62828;background:#ffebee;}"
    ".status-missing{border-color:#ef6c00;background:#fff3e0;}"
    ".status-not-attempted{border-color:#757575;background:#f5f5f5;font-style:italic;}"
    ".node-id{font-weight:bold;}"
    ".attempt{font-family:monospace;font-size:0.9em;}"
    ".retry-feedback{display:block;font-family:monospace;}"
)


class _UsageError(Exception):
    pass


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _load_tracker(repo_root):
    rel = Path("gen") / "provenance-tracker"
    base = Path(repo_root) / rel
    if not base.is_dir():
        base = _tool_root() / rel
    path = base / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


def _component_status_hit(result):
    report = _get(result, "verification_report")
    passing = (
        _get(report, "overall") == "pass"
        and not _get(_get(result, "license_scan"), "blocked")
        and not _get(_get(result, "secret_scan"), "flagged")
    )
    return "passing" if passing else "failing"


def _read_attempts(repo_root, component_id):
    attempt_dir = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    records = []
    for path in sorted(attempt_dir.glob("*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return records


def _component_node(tracker, repo_root, component_id, result):
    attempts = []
    retry_feedback = []
    if _get(result, "hit"):
        status = _component_status_hit(result)
    else:
        status = "missing"
    if status != "passing":
        attempts = _read_attempts(repo_root, component_id)
        if status == "missing" and not attempts:
            status = "not-attempted"
    if status in ("failing", "missing"):
        retry_feedback = list(
            tracker.last_requirement_failures(component_id, repo_root)
        )
    return {
        "id": component_id,
        "kind": "component",
        "status": status,
        "attempts": attempts,
        "retry_feedback": retry_feedback,
    }


def _capability_node(capability_id, result):
    report = _get(result, "capability_scenario_report")
    overall = _get(_get(report, capability_id), "overall")
    return {
        "id": capability_id,
        "kind": "capability",
        "status": "passing" if overall == "pass" else "failing",
        "attempts": [],
        "retry_feedback": [],
    }


def _esc(text):
    return html.escape(str(text), quote=True)


def _render_node(node):
    status = node["status"]
    parts = [
        '<li class="node status-%s" data-node-id="%s" data-kind="%s" data-status="%s">'
        % (_esc(status), _esc(node["id"]), _esc(node["kind"]), _esc(status)),
        '<span class="node-id">%s</span> ' % _esc(node["id"]),
        '<span class="node-kind">%s</span> ' % _esc(node["kind"]),
        '<span class="node-status">%s</span>' % _esc(STATUS_LABELS[status]),
    ]
    for record in node["attempts"]:
        attempt_id = _get(record, "attempt_id")
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


def _render_page(snapshot, script_text):
    data = json.dumps(snapshot).replace("</", "<\\/")
    out = [
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
        out.append(
            '<p class="changed-ids">changed: %s</p>'
            % _esc(", ".join(snapshot["changed_ids"]))
        )
    out.append('<div class="filters">')
    for value, label in FILTERS:
        out.append(
            '<button type="button" data-filter="%s">%s</button>'
            % (_esc(value), _esc(label))
        )
    out.append("</div>")
    out.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        out.append(_render_node(node))
    out.append("</ul>")
    out.append(
        '<script type="application/json" id="tracker-snapshot">'
        + data
        + "</script>"
    )
    out.append(
        '<script type="module">' + script_text + "\ninit(document);\n</script>"
    )
    out.append("</body>")
    out.append("</html>")
    return "\n".join(out) + "\n"


def render_tracker_ui(
    out_dir,
    repo_root,
    changed_ids=None,
    model=None,
    seed=0,
    llm_backend=None,
):
    out_dir = Path(out_dir)
    repo_root = Path(repo_root)
    tracker = _load_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)

    graph_path = repo_root / "verification" / "corpus-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    components = _get(report, "components")
    capabilities = _get(report, "capabilities")
    nodes = []
    for component_id, result in components.items():
        nodes.append(_component_node(tracker, repo_root, component_id, result))
    for capability_id, result in capabilities.items():
        nodes.append(_capability_node(capability_id, result))
    nodes.sort(key=lambda n: n["id"])

    node_ids = {n["id"] for n in nodes}
    edges = [
        {"from": e["from"], "to": e["to"], "kind": e["kind"]}
        for e in graph["edges"]
        if e["from"] in node_ids and e["to"] in node_ids
    ]

    snapshot = {
        "scope": _get(report, "scope"),
        "changed_ids": None if changed_ids is None else list(changed_ids),
        "ready": _get(report, "ready"),
        "not_ready_reasons": list(_get(report, "not_ready_reasons")),
        "nodes": nodes,
        "edges": edges,
    }

    script_text = (Path(__file__).parent / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(
        _render_page(snapshot, script_text), encoding="utf-8"
    )
    return snapshot


def _parse(argv):
    if argv[:3] != ["track", "ui", "build"]:
        raise _UsageError("expected 'track ui build'")
    flags = {"--changed", "--repo-root", "--out", "--model", "--seed"}
    values = {}
    changed = None
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
            changed = (changed or []) + value.split(",")
        else:
            values[name] = value
        i += 1
    try:
        seed = int(values.get("--seed", "0"))
    except ValueError:
        raise _UsageError("--seed must be an integer")
    repo_root = Path(values.get("--repo-root", "."))
    out = values.get("--out")
    out_dir = repo_root / ".hotdocs" / "ui" if out is None else Path(out)
    return changed, repo_root, out_dir, values.get("--model"), seed


def _usage_error(cause):
    print("usage error: %s" % cause, file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        changed, repo_root, out_dir, model, seed = _parse(list(argv))
    except _UsageError as exc:
        return _usage_error(str(exc))
    graph_path = repo_root / "verification" / "corpus-graph.json"
    if not graph_path.is_file():
        return _usage_error(
            "missing %s; run hotdocs corpus-graph build first" % graph_path
        )
    try:
        render_tracker_ui(out_dir, repo_root, changed, model, seed)
    except json.JSONDecodeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except ValueError as exc:
        return _usage_error(str(exc))
    print(out_dir / "index.html")
    return 0
