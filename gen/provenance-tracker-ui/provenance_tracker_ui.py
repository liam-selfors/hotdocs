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

_LABELS = {"not-attempted": "not yet attempted"}

_CSS = """body { font-family: sans-serif; margin: 1.5em; color: #222; }
.filters button { margin-right: 0.4em; }
ul.nodes { list-style: none; padding: 0; }
li.node { margin: 0.4em 0; padding: 0.4em 0.6em; border-left: 0.5em solid #888; }
li.status-passing { border-color: #2e7d32; background: #e8f5e9; }
li.status-failing { border-color: #c62828; background: #ffebee; }
li.status-missing { border-color: #ef6c00; background: #fff3e0; }
li.status-not-attempted { border-color: #757575; background: #f5f5f5; font-style: italic; }
.node-id { font-weight: bold; }
.node-kind { color: #555; }
.attempt { font-family: monospace; margin-left: 1em; }
.retry-feedback { display: block; font-family: monospace; margin-left: 1em; }"""


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_provenance_tracker(repo_root):
    dep_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / "provenance-tracker"
    spec = importlib.util.spec_from_file_location(
        "provenance_tracker", dep_dir / "provenance_tracker.py"
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
        passing = (
            _get(_get(result, "verification_report"), "overall") == "pass"
            and not _get(_get(result, "license_scan"), "blocked")
            and not _get(_get(result, "secret_scan"), "flagged")
        )
        return "passing" if passing else "failing"
    return "missing" if attempts else "not-attempted"


def _capability_status(capability_id, result):
    report = _get(_get(result, "capability_scenario_report"), capability_id)
    return "passing" if _get(report, "overall") == "pass" else "failing"


def _component_node(tracker, repo_root, component_id, result):
    attempts = _read_attempts(repo_root, component_id)
    status = _component_status(result, attempts)
    retry_feedback = []
    if status in ("failing", "missing"):
        retry_feedback = list(
            tracker.last_requirement_failures(component_id, repo_root)
        )
    if status == "passing":
        attempts = []
    return {
        "id": component_id,
        "kind": "component",
        "status": status,
        "attempts": attempts,
        "retry_feedback": retry_feedback,
    }


def _capability_node(capability_id, result):
    return {
        "id": capability_id,
        "kind": "capability",
        "status": _capability_status(capability_id, result),
        "attempts": [],
        "retry_feedback": [],
    }


def _render_node(node):
    esc = html.escape
    status = node["status"]
    attempts = "".join(
        '<div class="attempt" data-attempt-id="{0}">{0}</div>'.format(
            esc(str(record.get("attempt_id")))
        )
        for record in node["attempts"]
    )
    retry = ""
    if node["retry_feedback"]:
        retry = '<code class="retry-feedback">{}</code>'.format(
            esc("--retry-feedback=" + ",".join(node["retry_feedback"]))
        )
    return (
        '<li class="node status-{s}" data-node-id="{i}" data-kind="{k}" '
        'data-status="{s}"><span class="node-id">{i}</span> '
        '<span class="node-kind">{k}</span> '
        '<span class="node-status">{label}</span>{a}{r}</li>'
    ).format(
        s=esc(status),
        i=esc(node["id"]),
        k=esc(node["kind"]),
        label=esc(_LABELS.get(status, status)),
        a=attempts,
        r=retry,
    )


def _render_page(snapshot, app_js):
    esc = html.escape
    data = json.dumps(snapshot, sort_keys=True, ensure_ascii=True).replace(
        "</", "<\\/"
    )
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Provenance Tracker</title>",
        "<style>",
        _CSS,
        "</style>",
        "</head>",
        "<body>",
        "<h1>Provenance Tracker</h1>",
        '<p class="scope">Scope: <span class="scope-name">{}</span></p>'.format(
            esc(snapshot["scope"])
        ),
    ]
    if snapshot["changed_ids"] is not None:
        lines.append(
            '<p class="changed-ids">Changed: {}</p>'.format(
                esc(", ".join(snapshot["changed_ids"]))
            )
        )
    lines.append('<div class="filters">')
    for value, text in _FILTERS:
        lines.append(
            '<button type="button" data-filter="{}">{}</button>'.format(
                esc(value), esc(text)
            )
        )
    lines.append("</div>")
    lines.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        lines.append(_render_node(node))
    lines.append("</ul>")
    lines.append(
        '<script type="application/json" id="tracker-snapshot">'
        + data
        + "</script>"
    )
    lines.append(
        '<script type="module">' + app_js + "\ninit(document);\n" + "</script>"
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
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(
        repo_root, changed_ids, model, seed, llm_backend
    )
    graph_path = Path(repo_root) / "verification" / "corpus-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    nodes = [
        _component_node(tracker, repo_root, component_id, result)
        for component_id, result in _get(report, "components").items()
    ]
    nodes.extend(
        _capability_node(capability_id, result)
        for capability_id, result in _get(report, "capabilities").items()
    )
    nodes.sort(key=lambda node: node["id"])
    ids = {node["id"] for node in nodes}
    edges = [
        edge
        for edge in graph["edges"]
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

    app_js = (Path(__file__).parent / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(
        _render_page(snapshot, app_js), encoding="utf-8"
    )
    return snapshot


def _usage_error(cause):
    print("usage error: " + cause, file=sys.stderr)
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
    tokens = argv[3:]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        name, sep, value = token.partition("=")
        if name not in _FLAGS:
            return _usage_error("unknown argument: " + token)
        if not sep:
            index += 1
            if index >= len(tokens):
                return _usage_error(name + " requires a value")
            value = tokens[index]
        if name == "--changed":
            changed = (changed or []) + value.split(",")
        else:
            values[name] = value
        index += 1

    try:
        seed = int(values.get("--seed", "0"))
    except ValueError:
        return _usage_error("--seed must be an integer")
    repo_root = Path(values.get("--repo-root", "."))
    out_dir = Path(values.get("--out", repo_root / ".hotdocs" / "ui"))

    try:
        render_tracker_ui(
            out_dir, repo_root, changed, values.get("--model"), seed
        )
    except json.JSONDecodeError as exc:
        print("error: invalid JSON: " + str(exc), file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        return _usage_error("missing file: " + str(exc.filename))
    except ValueError as exc:
        return _usage_error(str(exc))
    print(str(out_dir / "index.html"))
    return 0
