"""Provenance Tracker UI: a static, self-contained corpus-readiness page."""

import html
import importlib.util
import json
import sys
from pathlib import Path

_FLAGS = ("--changed", "--repo-root", "--out", "--model", "--seed")

_LABELS = {
    "passing": "passing",
    "failing": "failing",
    "missing": "missing",
    "not-attempted": "not yet attempted",
}

_CSS = """
body { font-family: sans-serif; margin: 1.5em; color: #222; background: #fafafa; }
h1 { font-size: 1.4em; margin: 0 0 0.4em 0; }
.scope, .changed-ids { margin: 0.2em 0; }
.filters { margin: 0.8em 0; }
.filters button { margin-right: 0.4em; }
ul.nodes { list-style: none; padding: 0; }
li.node { margin: 0.4em 0; padding: 0.5em 0.8em; border-left: 0.5em solid #999; background: #fff; }
li.node[hidden] { display: none; }
.node-id { font-weight: bold; font-family: monospace; }
.node-kind { color: #666; margin-left: 0.6em; }
.status-label { margin-left: 0.6em; padding: 0.1em 0.5em; border-radius: 0.3em; }
.status-passing { border-left-color: #2e7d32; }
.status-passing .status-label { background: #c8e6c9; color: #1b5e20; }
.status-failing { border-left-color: #c62828; }
.status-failing .status-label { background: #ffcdd2; color: #b71c1c; }
.status-missing { border-left-color: #ef6c00; }
.status-missing .status-label { background: #ffe0b2; color: #e65100; }
.status-not-attempted { border-left-color: #9e9e9e; border-left-style: dashed; }
.status-not-attempted .status-label { background: #eeeeee; color: #424242; font-style: italic; }
ol.attempts { margin: 0.3em 0 0.3em 1.5em; font-family: monospace; font-size: 0.9em; }
.retry-feedback { display: block; margin-top: 0.3em; font-family: monospace; user-select: all; background: #f0f0f0; padding: 0.2em 0.4em; }
"""

_JS = """
(function () {
  var buttons = document.querySelectorAll("button[data-filter]");
  var nodes = document.querySelectorAll("li.node");
  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener("click", function (ev) {
      var f = ev.currentTarget.getAttribute("data-filter");
      for (var j = 0; j < nodes.length; j++) {
        nodes[j].hidden = !(f === "all" || nodes[j].getAttribute("data-status") === f);
      }
    });
  }
})();
"""


class _UsageError(Exception):
    pass


def _get(obj, key):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    p = Path(__file__).resolve().parent
    while p.name != "gen":
        p = p.parent
    return p.parent


def _load_provenance_tracker(repo_root):
    rel = Path("gen", "provenance-tracker")
    base = Path(repo_root) / rel
    if not base.is_dir():
        base = _tool_root() / rel
    path = base / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = mod
    spec.loader.exec_module(mod)
    return mod


def _read_attempts(repo_root, component_id):
    d = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))]


def _component_node(pt, repo_root, cid, result):
    attempts = []
    feedback = []
    if _get(result, "hit"):
        passing = (
            _get(_get(result, "verification_report"), "overall") == "pass"
            and not _get(_get(result, "license_scan"), "blocked")
            and not _get(_get(result, "secret_scan"), "flagged")
        )
        if passing:
            status = "passing"
        else:
            status = "failing"
            attempts = _read_attempts(repo_root, cid)
    else:
        attempts = _read_attempts(repo_root, cid)
        status = "missing" if attempts else "not-attempted"
    if status in ("failing", "missing"):
        feedback = list(pt.last_requirement_failures(cid, repo_root))
    return {"id": cid, "kind": "component", "status": status,
            "attempts": attempts, "retry_feedback": feedback}


def _capability_node(cid, result):
    entry = _get(_get(result, "capability_scenario_report"), cid)
    status = "passing" if _get(entry, "overall") == "pass" else "failing"
    return {"id": cid, "kind": "capability", "status": status,
            "attempts": [], "retry_feedback": []}


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
        '<ol class="attempts">',
    ]
    for rec in node["attempts"]:
        aid = rec["attempt_id"]
        parts.append('<li class="attempt" data-attempt-id="%s">%s</li>' % (_esc(aid), _esc(aid)))
    parts.append("</ol>")
    if node["retry_feedback"]:
        parts.append('<code class="retry-feedback">%s</code>'
                     % _esc("--retry-feedback=" + ",".join(node["retry_feedback"])))
    parts.append("</li>")
    return "".join(parts)


def _render_html(snapshot):
    data = json.dumps(snapshot, sort_keys=True, ensure_ascii=True).replace("</", "<\\/")
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
        '<p class="scope">Scope: <span id="scope">%s</span></p>' % _esc(snapshot["scope"]),
    ]
    if snapshot["changed_ids"] is not None:
        lines.append('<p class="changed-ids">Changed: <span id="changed-ids">%s</span></p>'
                     % _esc(", ".join(snapshot["changed_ids"])))
    lines.append('<div class="filters">'
                 '<button type="button" data-filter="all">all</button>'
                 '<button type="button" data-filter="passing">passing</button>'
                 '<button type="button" data-filter="failing">failing</button>'
                 '<button type="button" data-filter="missing">missing</button>'
                 '<button type="button" data-filter="not-attempted">not yet attempted</button>'
                 "</div>")
    lines.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        lines.append(_render_node(node))
    lines.append("</ul>")
    lines.append('<script type="application/json" id="tracker-snapshot">' + data + "</script>")
    lines.append("<script>" + _JS + "</script>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def render_tracker_ui(out_dir, repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    pt = _load_provenance_tracker(repo_root)
    report = pt.check_readiness(repo_root, changed_ids, model, seed, llm_backend)
    graph = json.loads(
        (Path(repo_root) / "verification" / "corpus-graph.json").read_text(encoding="utf-8"))

    components = _get(report, "components")
    capabilities = _get(report, "capabilities")
    nodes = [_component_node(pt, repo_root, cid, components[cid]) for cid in components]
    nodes += [_capability_node(cid, capabilities[cid]) for cid in capabilities]
    nodes.sort(key=lambda n: n["id"])
    ids = {n["id"] for n in nodes}
    edges = [e for e in graph["edges"] if e["from"] in ids and e["to"] in ids]

    snapshot = {
        "scope": _get(report, "scope"),
        "changed_ids": changed_ids,
        "ready": _get(report, "ready"),
        "not_ready_reasons": _get(report, "not_ready_reasons"),
        "nodes": nodes,
        "edges": edges,
    }

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_bytes(_render_html(snapshot).encode("utf-8"))
    return snapshot


def _parse(argv):
    if list(argv[:3]) != ["track", "ui", "build"]:
        raise _UsageError("expected 'track ui build'")
    values = {}
    changed = None
    i = 3
    while i < len(argv):
        name, eq, value = argv[i].partition("=")
        if name not in _FLAGS:
            raise _UsageError("unknown argument: %s" % argv[i])
        if not eq:
            i += 1
            if i >= len(argv):
                raise _UsageError("%s requires a value" % name)
            value = argv[i]
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
    out = Path(values["--out"]) if "--out" in values else repo_root / ".hotdocs" / "ui"
    return repo_root, out, changed, values.get("--model"), seed


def main(argv):
    try:
        repo_root, out, changed, model, seed = _parse(argv)
    except _UsageError as e:
        print("usage error: %s" % e, file=sys.stderr)
        return 2
    try:
        render_tracker_ui(out, repo_root, changed, model, seed)
    except json.JSONDecodeError as e:
        print("error: invalid JSON: %s" % e, file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print("error: missing file: %s" % e.filename, file=sys.stderr)
        return 2
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    print(str(out / "index.html"))
    return 0
