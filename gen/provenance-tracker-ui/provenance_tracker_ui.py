"""Provenance Tracker UI: one static, self-contained readiness page.

`render_tracker_ui` reads `provenance-tracker`'s `check_readiness` and
`last_requirement_failures`, `verification/corpus-graph.json`, and
`.hotdocs/attempts/<component_id>/*.json`, then writes a single
`out_dir/index.html` with the `TrackerSnapshot` inlined as JSON and every
node rendered at build time. `main(argv)` implements
`hotdocs track ui build`.
"""

import html
import importlib.util
import json
import os
import sys
from pathlib import Path

_STATUS_LABELS = {
    "passing": "passing",
    "failing": "failing",
    "missing": "missing",
    "not-attempted": "not yet attempted",
}

_FLAGS = ("--changed", "--repo-root", "--out", "--model", "--seed")

_CSS = """
body { font-family: sans-serif; margin: 2em; color: #222; }
ul.nodes { list-style: none; padding: 0; }
li.node { margin: 0.4em 0; padding: 0.5em 0.8em; border-left: 6px solid; }
li.node .node-id { font-weight: bold; }
li.node .node-kind { color: #555; font-size: 0.9em; }
li.node .status-label { margin-left: 0.5em; font-style: italic; }
li.node ol.attempts { margin: 0.3em 0 0.3em 1.5em; font-family: monospace; }
li.node .retry-feedback { display: inline-block; margin-top: 0.3em; padding: 0.2em 0.4em; background: #fff; border: 1px solid #999; }
.status-passing { border-color: #2e7d32; background: #e8f5e9; }
.status-failing { border-color: #c62828; background: #ffebee; }
.status-missing { border-color: #ef6c00; background: #fff3e0; }
.status-not-attempted { border-color: #757575; background: #f0f0f0; border-left-style: dashed; }
.hidden { display: none; }
button.selected { font-weight: bold; }
"""

_JS = """
(function () {
  var nodes = document.querySelectorAll("li.node");
  var buttons = document.querySelectorAll("button[data-filter]");
  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      var wanted = button.getAttribute("data-filter");
      nodes.forEach(function (node) {
        var show = wanted === "all" || node.getAttribute("data-status") === wanted;
        node.classList.toggle("hidden", !show);
      });
      buttons.forEach(function (other) {
        other.classList.toggle("selected", other === button);
      });
    });
  });
})();
"""


class _UsageError(Exception):
    pass


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(os.path.abspath(__file__)).parents:
        if parent.name == "gen":
            return parent.parent


def _load_provenance_tracker(repo_root):
    relative = Path("gen") / "provenance-tracker"
    base = Path(repo_root) / relative
    if not base.is_dir():
        base = _tool_root() / relative
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
        for path in sorted(directory.glob("*.json"), key=lambda p: p.name)
    ]


def _component_passes(result):
    return (
        _get(_get(result, "verification_report"), "overall") == "pass"
        and not _get(_get(result, "license_scan"), "blocked")
        and not _get(_get(result, "secret_scan"), "flagged")
    )


def _component_node(component_id, result, repo_root, tracker):
    hit = _get(result, "hit")
    node = {
        "id": component_id,
        "kind": "component",
        "status": "passing",
        "attempts": [],
        "retry_feedback": [],
    }
    if hit and _component_passes(result):
        return node
    attempts = _read_attempts(repo_root, component_id)
    if hit:
        node["status"] = "failing"
    elif attempts:
        node["status"] = "missing"
    else:
        node["status"] = "not-attempted"
        return node
    node["attempts"] = attempts
    node["retry_feedback"] = list(
        tracker.last_requirement_failures(component_id, repo_root)
    )
    return node


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


def _node_html(node):
    esc = html.escape
    node_id = esc(node["id"])
    status = node["status"]
    kind = node["kind"]
    parts = [
        f'<li class="node status-{status}" data-node-id="{node_id}" '
        f'data-kind="{kind}" data-status="{status}">',
        f'<span class="node-id">{node_id}</span> ',
        f'<span class="node-kind">{kind}</span> ',
        f'<span class="status-label">{_STATUS_LABELS[status]}</span>',
        '<ol class="attempts">',
    ]
    for attempt in node["attempts"]:
        attempt_id = esc(str(attempt["attempt_id"]))
        parts.append(
            f'<li class="attempt" data-attempt-id="{attempt_id}">{attempt_id}</li>'
        )
    parts.append("</ol>")
    if node["retry_feedback"]:
        suggestion = "--retry-feedback=" + ",".join(node["retry_feedback"])
        parts.append(f'<code class="retry-feedback">{esc(suggestion)}</code>')
    parts.append("</li>")
    return "".join(parts)


def _page(snapshot):
    esc = html.escape
    scope_html = (
        f'<p class="scope">Scope: <span class="scope-name">'
        f'{esc(snapshot["scope"])}</span>'
    )
    if snapshot["changed_ids"] is not None:
        scope_html += (
            ' &middot; changed: <span class="changed-ids">'
            f'{esc(", ".join(snapshot["changed_ids"]))}</span>'
        )
    scope_html += "</p>"
    buttons = "\n".join(
        f'<button type="button" data-filter="{name}">{label}</button>'
        for name, label in (
            ("all", "all"),
            ("passing", "passing"),
            ("failing", "failing"),
            ("missing", "missing"),
            ("not-attempted", "not yet attempted"),
        )
    )
    nodes_html = "\n".join(_node_html(node) for node in snapshot["nodes"])
    data = json.dumps(snapshot, sort_keys=True).replace("</", "<\\/")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        "<title>Provenance tracker</title>\n"
        f"<style>{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        "<h1>Provenance tracker</h1>\n"
        f"{scope_html}\n"
        f'<div class="filters">\n{buttons}\n</div>\n'
        f'<ul class="nodes">\n{nodes_html}\n</ul>\n'
        f'<script type="application/json" id="tracker-snapshot">{data}</script>\n'
        f"<script>{_JS}</script>\n"
        "</body>\n"
        "</html>\n"
    )


def render_tracker_ui(
    out_dir,
    repo_root,
    changed_ids=None,
    model=None,
    seed=0,
    llm_backend=None,
):
    graph_path = Path(repo_root) / "verification" / "corpus-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(
        repo_root,
        changed_ids=changed_ids,
        model=model,
        seed=seed,
        llm_backend=llm_backend,
    )
    components = _get(report, "components")
    capabilities = _get(report, "capabilities")
    nodes = [
        _component_node(cid, _get(components, cid), repo_root, tracker)
        for cid in components
    ]
    nodes.extend(
        _capability_node(pid, _get(capabilities, pid)) for pid in capabilities
    )
    nodes.sort(key=lambda node: node["id"])
    ids = {node["id"] for node in nodes}
    edges = [
        dict(edge)
        for edge in graph["edges"]
        if edge["from"] in ids and edge["to"] in ids
    ]
    snapshot = {
        "scope": _get(report, "scope"),
        "changed_ids": changed_ids,
        "ready": _get(report, "ready"),
        "not_ready_reasons": _get(report, "not_ready_reasons"),
        "nodes": nodes,
        "edges": edges,
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_bytes(_page(snapshot).encode("utf-8"))
    return snapshot


def _parse_args(args):
    values = {}
    changed = []
    i = 0
    while i < len(args):
        name, eq, value = args[i].partition("=")
        if name not in _FLAGS:
            raise _UsageError(f"unknown argument: {args[i]}")
        if not eq:
            i += 1
            if i >= len(args):
                raise _UsageError(f"{name} requires a value")
            value = args[i]
        if name == "--changed":
            changed.extend(value.split(","))
        else:
            values[name] = value
        i += 1
    try:
        seed = int(values.get("--seed", "0"))
    except ValueError:
        raise _UsageError(f"--seed must be an integer: {values['--seed']}")
    repo_root = Path(values.get("--repo-root", "."))
    out_dir = Path(values.get("--out", repo_root / ".hotdocs" / "ui"))
    return {
        "out_dir": out_dir,
        "repo_root": repo_root,
        "changed_ids": changed or None,
        "model": values.get("--model"),
        "seed": seed,
    }


def main(argv):
    try:
        if list(argv[:3]) != ["track", "ui", "build"]:
            raise _UsageError("usage: hotdocs track ui build [--changed=<id>...] "
                              "[--repo-root=<dir>] [--out=<dir>] [--model=<model>] "
                              "[--seed=<n>]")
        options = _parse_args(list(argv[3:]))
    except _UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        render_tracker_ui(**options)
    except FileNotFoundError as exc:
        print(f"missing input: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"invalid JSON: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(str(options["out_dir"] / "index.html"))
    return 0
