"""Provenance Tracker UI: a static, self-contained corpus readiness page."""

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

_FILTERS = [
    ("all", "all"),
    ("passing", "passing"),
    ("failing", "failing"),
    ("missing", "missing"),
    ("not-attempted", "not yet attempted"),
]

_STATUS_LABELS = {
    "passing": "passing",
    "failing": "failing",
    "missing": "missing",
    "not-attempted": "not yet attempted",
}

_CSS = """
body { font-family: sans-serif; margin: 2em; }
ul.nodes { list-style: none; padding: 0; }
li.node { margin: 0.4em 0; padding: 0.5em; border-left: 0.5em solid; }
li.node[hidden] { display: none; }
.status-passing { border-color: #2e7d32; background: #e8f5e9; }
.status-failing { border-color: #c62828; background: #ffebee; }
.status-missing { border-color: #ef6c00; background: #fff3e0; }
.status-not-attempted { border-color: #757575; background: #f5f5f5; font-style: italic; }
.node-id { font-weight: bold; }
.retry-feedback { display: block; font-family: monospace; margin-top: 0.3em; }
"""


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    here = Path(__file__).resolve().parent
    for directory in [here, *here.parents]:
        if directory.name == "gen":
            return directory.parent


def _load_provenance_tracker(repo_root):
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
    directory = repo_root / ".hotdocs" / "attempts" / component_id
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def _component_status(result, attempts):
    if _get(result, "hit"):
        passing = (
            _get(_get(result, "verification_report"), "overall") == "pass"
            and not _get(_get(result, "license_scan"), "blocked")
            and not _get(_get(result, "secret_scan"), "flagged")
        )
        return "passing" if passing else "failing"
    return "missing" if attempts else "not-attempted"


def _esc(value):
    return html.escape(str(value), quote=True)


def _render_node(node):
    status = node["status"]
    parts = [
        f'<li class="node status-{_esc(status)}" data-node-id="{_esc(node["id"])}" '
        f'data-kind="{_esc(node["kind"])}" data-status="{_esc(status)}">',
        f'<span class="node-id">{_esc(node["id"])}</span> ',
        f'<span class="node-kind">{_esc(node["kind"])}</span> ',
        f'<span class="node-status">{_esc(_STATUS_LABELS[status])}</span>',
        '<ol class="attempts">',
    ]
    for attempt in node["attempts"]:
        attempt_id = _esc(attempt.get("attempt_id"))
        parts.append(f'<li class="attempt" data-attempt-id="{attempt_id}">{attempt_id}</li>')
    parts.append("</ol>")
    if node["retry_feedback"]:
        text = "--retry-feedback=" + ",".join(node["retry_feedback"])
        parts.append(f'<code class="retry-feedback">{_esc(text)}</code>')
    parts.append("</li>")
    return "".join(parts)


def _render_page(snapshot, asset_text):
    data = json.dumps(snapshot, sort_keys=True).replace("</", "<\\/")
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
        f'<p class="scope">scope: {_esc(snapshot["scope"])}</p>',
    ]
    if snapshot["changed_ids"] is not None:
        changed = ", ".join(str(c) for c in snapshot["changed_ids"])
        lines.append(f'<p class="changed-ids">changed: {_esc(changed)}</p>')
    lines.append('<ul class="not-ready-reasons">')
    for reason in snapshot["not_ready_reasons"]:
        lines.append(f"<li>{_esc(reason)}</li>")
    lines.append("</ul>")
    lines.append('<div class="filters">')
    for value, label in _FILTERS:
        lines.append(f'<button type="button" data-filter="{value}">{label}</button>')
    lines.append("</div>")
    lines.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        lines.append(_render_node(node))
    lines.append("</ul>")
    lines.append(f'<script type="application/json" id="tracker-snapshot">{data}</script>')
    lines.append('<script type="module">' + asset_text + "\ninit(document);\n</script>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def render_tracker_ui(out_dir, repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)
    root = Path(repo_root)
    graph = json.loads((root / "verification" / "corpus-graph.json").read_text(encoding="utf-8"))

    nodes = []
    for component_id, result in _get(report, "components").items():
        attempts = []
        status = _component_status(result, [])
        if status != "passing":
            attempts = _read_attempts(root, component_id)
            status = _component_status(result, attempts)
        retry_feedback = []
        if status in ("failing", "missing"):
            retry_feedback = list(tracker.last_requirement_failures(component_id, repo_root))
        else:
            attempts = attempts if status == "not-attempted" else []
        nodes.append({
            "id": component_id,
            "kind": "component",
            "status": status,
            "attempts": attempts,
            "retry_feedback": retry_feedback,
        })
    for capability_id, result in _get(report, "capabilities").items():
        entry = _get(_get(result, "capability_scenario_report"), capability_id)
        status = "passing" if _get(entry, "overall") == "pass" else "failing"
        nodes.append({
            "id": capability_id,
            "kind": "capability",
            "status": status,
            "attempts": [],
            "retry_feedback": [],
        })
    nodes.sort(key=lambda node: node["id"])
    ids = {node["id"] for node in nodes}
    edges = [edge for edge in graph["edges"] if edge["from"] in ids and edge["to"] in ids]

    snapshot = {
        "scope": _get(report, "scope"),
        "changed_ids": changed_ids,
        "ready": _get(report, "ready"),
        "not_ready_reasons": list(_get(report, "not_ready_reasons")),
        "nodes": nodes,
        "edges": edges,
    }

    asset_text = (Path(__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_bytes(_render_page(snapshot, asset_text).encode("utf-8"))
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
    values = {}
    changed = None
    i = 3
    while i < len(argv):
        token = argv[i]
        name, sep, value = token.partition("=")
        if name not in _FLAGS:
            return _usage_error(f"unknown argument: {token}")
        if not sep:
            i += 1
            if i >= len(argv):
                return _usage_error(f"{name} requires a value")
            value = argv[i]
        if name == "--changed":
            changed = (changed or []) + value.split(",")
        else:
            values[name] = value
        i += 1
    try:
        seed = int(values.get("--seed", "0"))
    except ValueError:
        return _usage_error(f"--seed must be an integer: {values['--seed']}")
    repo_root = Path(values.get("--repo-root", "."))
    out_dir = Path(values["--out"]) if "--out" in values else repo_root / ".hotdocs" / "ui"
    try:
        render_tracker_ui(out_dir, repo_root, changed, values.get("--model"), seed)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        return _usage_error(f"missing file: {exc.filename}")
    except ValueError as exc:
        return _usage_error(str(exc))
    print(str(out_dir / "index.html"))
    return 0
