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

TONES = {
    "passing": "tone-ok",
    "failing": "tone-fail",
    "missing": "tone-warn",
    "not-attempted": "tone-neutral",
}

LABELS = {
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

FLAGS = ("--changed", "--repo-root", "--out", "--model", "--seed")


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    here = Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        if candidate.name == "gen":
            return candidate.parent


def _load(repo_root, slug, module_name):
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    path = directory / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _read_attempts(root, component_id):
    directory = root / ".hotdocs" / "attempts" / component_id
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
    report = _get(result, "capability_scenario_report")
    if _get(_get(report, capability_id), "overall") == "pass":
        return "passing"
    return "failing"


def _render_node(node):
    status = node["status"]
    esc = html.escape
    parts = [
        f'<li class="node status-{esc(status)} {TONES[status]}" '
        f'data-node-id="{esc(node["id"])}" data-kind="{esc(node["kind"])}" '
        f'data-status="{esc(status)}">',
        f'<span class="node-id">{esc(node["id"])}</span> ',
        f'<span class="node-kind muted">{esc(node["kind"])}</span> ',
        f'<span class="node-status">{esc(LABELS[status])}</span>',
        '<ol class="attempts">',
    ]
    for record in node["attempts"]:
        attempt_id = esc(str(record["attempt_id"]))
        parts.append(f'<li data-attempt-id="{attempt_id}">{attempt_id}</li>')
    parts.append("</ol>")
    if node["retry_feedback"]:
        suggestion = "--retry-feedback=" + ",".join(node["retry_feedback"])
        parts.append(f'<code class="retry-feedback">{esc(suggestion)}</code>')
    parts.append("</li>")
    return "".join(parts)


def _render_page(snapshot, style_element, script_text):
    esc = html.escape
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Provenance tracker</title>",
        style_element,
        "</head>",
        "<body>",
        "<main>",
        "<h1>Provenance tracker</h1>",
        f'<p class="scope">scope: <span id="scope">{esc(snapshot["scope"])}</span></p>',
    ]
    if snapshot["changed_ids"] is not None:
        changed = esc(", ".join(snapshot["changed_ids"]))
        lines.append(f'<p class="changed-ids">changed: <span id="changed-ids">{changed}</span></p>')
    lines.append('<div class="filters">')
    for value, label in FILTERS:
        lines.append(f'<button type="button" data-filter="{value}">{label}</button>')
    lines.append("</div>")
    lines.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        lines.append(_render_node(node))
    lines.append("</ul>")
    lines.append("</main>")
    data = json.dumps(snapshot, sort_keys=True).replace("</", "<\\/")
    lines.append(f'<script type="application/json" id="tracker-snapshot">{data}</script>')
    lines.append('<script type="module">' + script_text + "\ninit(document);\n" + "</script>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def render_tracker_ui(out_dir, repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    tracker = _load(repo_root, "provenance-tracker", "provenance_tracker")
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)
    root = Path(repo_root)
    graph = json.loads((root / "verification" / "corpus-graph.json").read_text(encoding="utf-8"))

    components = _get(report, "components")
    capabilities = _get(report, "capabilities")
    nodes = []
    for component_id in components:
        result = components[component_id]
        attempts = _read_attempts(root, component_id)
        status = _component_status(result, attempts)
        feedback = []
        if status in ("failing", "missing"):
            feedback = list(tracker.last_requirement_failures(component_id, repo_root))
        else:
            attempts = []
        nodes.append({
            "id": component_id, "kind": "component", "status": status,
            "attempts": attempts, "retry_feedback": feedback,
        })
    for capability_id in capabilities:
        nodes.append({
            "id": capability_id, "kind": "capability",
            "status": _capability_status(capability_id, capabilities[capability_id]),
            "attempts": [], "retry_feedback": [],
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

    ui_style = _load(repo_root, "ui-style", "ui_style")
    script_text = (Path(__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    page = _render_page(snapshot, ui_style.style_element(), script_text)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_bytes(page.encode("utf-8"))
    return snapshot


class _UsageError(Exception):
    pass


def _parse(argv):
    if argv[:3] != ["track", "ui", "build"]:
        raise _UsageError("expected 'track ui build'")
    rest = argv[3:]
    options = {"--changed": None, "--repo-root": ".", "--out": None, "--model": None, "--seed": 0}
    i = 0
    while i < len(rest):
        token = rest[i]
        name, eq, value = token.partition("=")
        if name not in FLAGS:
            raise _UsageError(f"unknown argument {token}")
        if not eq:
            i += 1
            if i >= len(rest):
                raise _UsageError(f"{name} needs a value")
            value = rest[i]
        i += 1
        if name == "--changed":
            options["--changed"] = (options["--changed"] or []) + value.split(",")
        elif name == "--seed":
            try:
                options["--seed"] = int(value)
            except ValueError:
                raise _UsageError(f"--seed must be an integer, got {value}")
        else:
            options[name] = value
    return options


def _usage(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        options = _parse(list(argv))
    except _UsageError as exc:
        return _usage(str(exc))
    repo_root = Path(options["--repo-root"])
    out_dir = Path(options["--out"]) if options["--out"] is not None else repo_root / ".hotdocs" / "ui"
    graph_path = repo_root / "verification" / "corpus-graph.json"
    if not graph_path.is_file():
        return _usage(f"missing {graph_path}; run hotdocs corpus-graph build first")
    try:
        render_tracker_ui(
            out_dir, repo_root, options["--changed"], options["--model"], options["--seed"]
        )
    except json.JSONDecodeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        return _usage(str(exc))
    print(out_dir / "index.html")
    return 0
