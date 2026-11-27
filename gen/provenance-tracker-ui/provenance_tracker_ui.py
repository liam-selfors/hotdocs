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

_TONES = {
    "passing": "tone-ok",
    "failing": "tone-fail",
    "missing": "tone-warn",
    "not-attempted": "tone-neutral",
}

_LABELS = {
    "passing": "passing",
    "failing": "failing",
    "missing": "missing",
    "not-attempted": "not yet attempted",
}

_FILTERS = [
    ("all", "all"),
    ("passing", "passing"),
    ("failing", "failing"),
    ("missing", "missing"),
    ("not-attempted", "not yet attempted"),
]


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load(repo_root, slug, name):
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    spec = importlib.util.spec_from_file_location(name, directory / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_attempts(repo_root, component_id):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def _component_status(result, attempts):
    if _get(result, "hit"):
        report = _get(result, "verification_report")
        license_scan = _get(result, "license_scan")
        if _get(report, "overall") == "pass" and not _get(license_scan, "blocked"):
            return "passing"
        return "failing"
    if attempts:
        return "missing"
    return "not-attempted"


def _capability_status(capability_id, result):
    scenario_report = _get(result, "capability_scenario_report")
    if _get(_get(scenario_report, capability_id), "overall") == "pass":
        return "passing"
    return "failing"


def _esc(value):
    return html.escape(str(value), quote=True)


def _render_node(node):
    status = node["status"]
    parts = [
        f'<li class="node status-{_esc(status)} {_TONES[status]}" '
        f'data-node-id="{_esc(node["id"])}" data-kind="{_esc(node["kind"])}" '
        f'data-status="{_esc(status)}">',
        f'<span class="node-id">{_esc(node["id"])}</span> ',
        f'<span class="node-kind muted">{_esc(node["kind"])}</span> ',
        f'<span class="node-status">{_LABELS[status]}</span>',
    ]
    if status in ("failing", "missing"):
        parts.append('<ul class="attempts">')
        for attempt in node["attempts"]:
            attempt_id = _esc(attempt["attempt_id"])
            parts.append(f'<li class="attempt" data-attempt-id="{attempt_id}">{attempt_id}</li>')
        parts.append("</ul>")
        if node["retry_feedback"]:
            text = "--retry-feedback=" + ",".join(node["retry_feedback"])
            parts.append(f'<code class="retry-feedback">{_esc(text)}</code>')
    parts.append("</li>")
    return "".join(parts)


def _render_page(snapshot, style_element, script_text):
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Provenance tracker</title>",
        style_element,
        "</head>",
        "<body>",
        "<h1>Provenance tracker</h1>",
        f'<p class="scope">Scope: {_esc(snapshot["scope"])}</p>',
    ]
    if snapshot["changed_ids"] is not None:
        changed = ", ".join(str(c) for c in snapshot["changed_ids"])
        lines.append(f'<p class="changed-ids">Changed: {_esc(changed)}</p>')
    lines.append('<div class="filters">')
    for value, label in _FILTERS:
        lines.append(f'<button type="button" data-filter="{value}">{label}</button>')
    lines.append("</div>")
    lines.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        lines.append(_render_node(node))
    lines.append("</ul>")
    data = json.dumps(snapshot, sort_keys=True).replace("</", "<\\/")
    lines.append(f'<script type="application/json" id="tracker-snapshot">{data}</script>')
    lines.append('<script type="module">' + script_text + "\ninit(document);\n</script>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def render_tracker_ui(out_dir, repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    out_dir = Path(out_dir)
    repo_root = Path(repo_root)
    tracker = _load(repo_root, "provenance-tracker", "provenance_tracker")
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)

    graph_path = repo_root / "verification" / "corpus-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    nodes = []
    for component_id, result in _get(report, "components").items():
        attempts = _load_attempts(repo_root, component_id)
        status = _component_status(result, attempts)
        retry_feedback = []
        if status in ("failing", "missing"):
            retry_feedback = list(tracker.last_requirement_failures(component_id, repo_root))
        else:
            attempts = []
        nodes.append({
            "id": component_id,
            "kind": "component",
            "status": status,
            "attempts": attempts,
            "retry_feedback": retry_feedback,
        })
    for capability_id, result in _get(report, "capabilities").items():
        nodes.append({
            "id": capability_id,
            "kind": "capability",
            "status": _capability_status(capability_id, result),
            "attempts": [],
            "retry_feedback": [],
        })
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

    ui_style = _load(repo_root, "ui-style", "ui_style")
    script_text = (Path(__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    page = _render_page(snapshot, ui_style.style_element(), script_text)

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

    flags = {"--changed", "--repo-root", "--out", "--model", "--seed"}
    changed = None
    repo_root = "."
    out = None
    model = None
    seed = "0"

    tokens = argv[3:]
    i = 0
    while i < len(tokens):
        token = tokens[i]
        name, sep, value = token.partition("=")
        if name not in flags:
            return _usage_error(f"unknown argument {token}")
        if not sep:
            if i + 1 >= len(tokens):
                return _usage_error(f"{name} requires a value")
            i += 1
            value = tokens[i]
        if name == "--changed":
            changed = (changed or []) + value.split(",")
        elif name == "--repo-root":
            repo_root = value
        elif name == "--out":
            out = value
        elif name == "--model":
            model = value
        else:
            seed = value
        i += 1

    try:
        seed_value = int(seed)
    except ValueError:
        return _usage_error(f"--seed must be an integer, got {seed}")

    root = Path(repo_root)
    out_dir = root / ".hotdocs" / "ui" if out is None else Path(out)
    graph_path = root / "verification" / "corpus-graph.json"
    if not graph_path.exists():
        return _usage_error(f"missing {graph_path}; run hotdocs corpus-graph build first")

    try:
        render_tracker_ui(out_dir, root, changed, model, seed_value)
    except json.JSONDecodeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        return _usage_error(str(exc))

    print(out_dir / "index.html")
    return 0
