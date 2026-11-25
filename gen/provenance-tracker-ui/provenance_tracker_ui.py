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

FLAGS = {"--changed", "--repo-root", "--out", "--model", "--seed"}

CSS = """
body { font-family: sans-serif; margin: 2em; color: #222; }
.filters button { margin-right: 0.5em; }
ul.nodes { list-style: none; padding: 0; }
li.node { margin: 0.4em 0; padding: 0.4em 0.6em; border-left: 6px solid #999; }
li.node.status-passing { border-left-color: #2e7d32; background: #e8f5e9; }
li.node.status-failing { border-left-color: #c62828; background: #ffebee; }
li.node.status-missing { border-left-color: #ef6c00; background: #fff3e0; }
li.node.status-not-attempted { border-left-color: #757575; background: #f5f5f5; font-style: italic; }
.kind { color: #555; margin-left: 0.5em; }
.status-label { font-weight: bold; margin-left: 0.5em; }
.retry-feedback { display: block; margin-top: 0.3em; font-family: monospace; }
"""


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_dependency(repo_root, slug, module_name):
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    path = directory / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _read_attempts(repo_root, component_id):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def _component_status(result, attempts):
    if _get(result, "hit"):
        overall = _get(_get(result, "verification_report"), "overall")
        blocked = _get(_get(result, "license_scan"), "blocked")
        if overall == "pass" and not blocked:
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


def _render_node(node):
    esc = html.escape
    parts = [
        f'<li class="node status-{esc(node["status"])}" '
        f'data-node-id="{esc(node["id"])}" data-kind="{esc(node["kind"])}" '
        f'data-status="{esc(node["status"])}">',
        f'<span class="node-id">{esc(node["id"])}</span>',
        f'<span class="kind">{esc(node["kind"])}</span>',
        f'<span class="status-label">{esc(STATUS_LABELS[node["status"]])}</span>',
        '<ol class="attempts">',
    ]
    for attempt in node["attempts"]:
        attempt_id = esc(str(attempt["attempt_id"]))
        parts.append(
            f'<li class="attempt" data-attempt-id="{attempt_id}">{attempt_id}</li>'
        )
    parts.append("</ol>")
    if node["retry_feedback"]:
        text = "--retry-feedback=" + ",".join(node["retry_feedback"])
        parts.append(f'<code class="retry-feedback">{esc(text)}</code>')
    parts.append("</li>")
    return "".join(parts)


def _render_page(snapshot, changed_ids, asset_text):
    esc = html.escape
    snapshot_json = json.dumps(snapshot, sort_keys=True, ensure_ascii=True).replace(
        "</", "<\\/"
    )
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
        f'<p class="scope">Scope: <span class="scope-name">{esc(str(snapshot["scope"]))}</span></p>',
    ]
    if changed_ids is not None:
        lines.append(
            f'<p class="changed-ids">Changed: {esc(", ".join(changed_ids))}</p>'
        )
    lines.append('<div class="filters">')
    for value, label in FILTERS:
        lines.append(f'<button type="button" data-filter="{value}">{label}</button>')
    lines.append("</div>")
    lines.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        lines.append(_render_node(node))
    lines.append("</ul>")
    lines.append(
        '<script type="application/json" id="tracker-snapshot">'
        + snapshot_json
        + "</script>"
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
    tracker = _load_dependency(repo_root, "provenance-tracker", "provenance_tracker")
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)

    graph_path = Path(repo_root) / "verification" / "corpus-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    entries = []
    components = _get(report, "components")
    for component_id in components:
        result = _get(components, component_id)
        attempts = _read_attempts(repo_root, component_id)
        status = _component_status(result, attempts)
        node_attempts = []
        retry_feedback = []
        if status in ("failing", "missing"):
            node_attempts = attempts
            retry_feedback = list(
                tracker.last_requirement_failures(component_id, repo_root)
            )
        entries.append(
            {
                "id": component_id,
                "kind": "component",
                "status": status,
                "attempts": node_attempts,
                "retry_feedback": retry_feedback,
            }
        )
    capabilities = _get(report, "capabilities")
    for capability_id in capabilities:
        result = _get(capabilities, capability_id)
        entries.append(
            {
                "id": capability_id,
                "kind": "capability",
                "status": _capability_status(capability_id, result),
                "attempts": [],
                "retry_feedback": [],
            }
        )
    nodes = sorted(entries, key=lambda node: node["id"])
    node_ids = {node["id"] for node in nodes}
    edges = [
        edge
        for edge in graph["edges"]
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

    asset_text = (Path(__file__).parent / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    page = _render_page(snapshot, changed_ids, asset_text)
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
    changed = None
    values = {}
    index = 3
    while index < len(argv):
        token = argv[index]
        name, eq, value = token.partition("=")
        if name not in FLAGS:
            return _usage_error(f"unknown argument {token}")
        if not eq:
            if index + 1 >= len(argv):
                return _usage_error(f"{name} requires a value")
            index += 1
            value = argv[index]
        if name == "--changed":
            changed = (changed or []) + value.split(",")
        else:
            values[name] = value
        index += 1
    try:
        seed = int(values.get("--seed", "0"))
    except ValueError:
        return _usage_error(f"--seed must be an integer, got {values['--seed']}")
    repo_root = Path(values.get("--repo-root", "."))
    if "--out" in values:
        out_dir = Path(values["--out"])
    else:
        out_dir = repo_root / ".hotdocs" / "ui"
    model = values.get("--model")

    graph_path = repo_root / "verification" / "corpus-graph.json"
    if not graph_path.is_file():
        return _usage_error(
            f"missing {graph_path}; run hotdocs corpus-graph build first"
        )
    try:
        render_tracker_ui(out_dir, repo_root, changed, model, seed)
    except json.JSONDecodeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        return _usage_error(str(error))
    print(out_dir / "index.html")
    return 0
