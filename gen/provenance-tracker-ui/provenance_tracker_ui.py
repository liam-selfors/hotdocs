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

_STATUS_LABELS = {
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

_CSS = """
body { font-family: sans-serif; margin: 1.5em; }
ul.nodes { list-style: none; padding: 0; }
li.node { margin: 0.4em 0; padding: 0.5em; border-left: 6px solid #888; }
li.node.status-passing { border-left-color: #2e7d32; background: #e8f5e9; }
li.node.status-failing { border-left-color: #c62828; background: #ffebee; }
li.node.status-missing { border-left-color: #ef6c00; background: #fff3e0; }
li.node.status-not-attempted { border-left-color: #757575; background: #f5f5f5; font-style: italic; }
.node-label { margin-left: 0.6em; font-weight: bold; }
.attempt { margin-left: 1em; font-family: monospace; }
.retry-feedback { display: block; margin-left: 1em; font-family: monospace; }
button { margin-right: 0.3em; }
"""


def _get(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def _tool_root():
    here = Path(__file__).resolve().parent
    for p in [here, *here.parents]:
        if p.name == "gen":
            return p.parent


def _load_provenance_tracker(repo_root):
    dep_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / "provenance-tracker"
    name = "provenance_tracker"
    spec = importlib.util.spec_from_file_location(name, dep_dir / "provenance_tracker.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _read_attempts(repo_root, component_id):
    attempt_dir = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(attempt_dir.glob("*.json"))
    ]


def _esc(value):
    return html.escape(str(value), quote=True)


def _render_node(node):
    status = node["status"]
    parts = [
        f'<li class="node status-{_esc(status)}" data-node-id="{_esc(node["id"])}" '
        f'data-kind="{_esc(node["kind"])}" data-status="{_esc(status)}">',
        f'<span class="node-id">{_esc(node["id"])}</span>',
        f'<span class="node-label">{_esc(_STATUS_LABELS[status])}</span>',
    ]
    for attempt in node["attempts"]:
        attempt_id = _get(attempt, "attempt_id")
        parts.append(
            f'<div class="attempt" data-attempt-id="{_esc(attempt_id)}">{_esc(attempt_id)}</div>'
        )
    if node["retry_feedback"]:
        text = "--retry-feedback=" + ",".join(node["retry_feedback"])
        parts.append(f'<code class="retry-feedback">{_esc(text)}</code>')
    parts.append("</li>")
    return "".join(parts)


def _render_page(snapshot, script_text):
    data = json.dumps(snapshot, sort_keys=True, ensure_ascii=False).replace("</", "<\\/")
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Provenance Tracker</title>",
        "<style>" + _CSS + "</style>",
        "</head>",
        "<body>",
        "<h1>Provenance Tracker</h1>",
        f'<p class="scope">Scope: {_esc(snapshot["scope"])}</p>',
    ]
    if snapshot["changed_ids"] is not None:
        lines.append(
            f'<p class="changed-ids">Changed: {_esc(", ".join(snapshot["changed_ids"]))}</p>'
        )
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
    lines.append(
        '<script type="application/json" id="tracker-snapshot">' + data + "</script>"
    )
    lines.append('<script type="module">' + script_text + "\ninit(document);\n</script>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def render_tracker_ui(out_dir, repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    out_dir = Path(out_dir)
    repo_root = Path(repo_root)
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)

    graph_path = repo_root / "verification" / "corpus-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    nodes = []
    for cid, result in _get(report, "components").items():
        attempts = _read_attempts(repo_root, cid)
        if _get(result, "hit"):
            passing = (
                _get(_get(result, "verification_report"), "overall") == "pass"
                and not _get(_get(result, "license_scan"), "blocked")
                and not _get(_get(result, "secret_scan"), "flagged")
            )
            status = "passing" if passing else "failing"
        else:
            status = "missing" if attempts else "not-attempted"
        if status == "passing":
            attempts = []
        feedback = []
        if status in ("failing", "missing"):
            feedback = list(tracker.last_requirement_failures(cid, repo_root))
        nodes.append({
            "id": cid, "kind": "component", "status": status,
            "attempts": attempts, "retry_feedback": feedback,
        })
    for pid, result in _get(report, "capabilities").items():
        csr = _get(result, "capability_scenario_report")
        overall = _get(_get(csr, pid), "overall")
        nodes.append({
            "id": pid, "kind": "capability",
            "status": "passing" if overall == "pass" else "failing",
            "attempts": [], "retry_feedback": [],
        })
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

    script_text = (Path(__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_bytes(_render_page(snapshot, script_text).encode("utf-8"))
    return snapshot


class _UsageError(Exception):
    pass


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _parse(argv):
    if argv[:3] != ["track", "ui", "build"]:
        raise _UsageError("expected 'track ui build'")
    opts = {"changed": None, "repo-root": ".", "out": None, "model": None, "seed": 0}
    tokens = argv[3:]
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if "=" in token:
            flag, value = token.split("=", 1)
        else:
            flag, value = token, None
        name = flag[2:]
        if not flag.startswith("--") or name not in opts:
            raise _UsageError(f"unknown argument: {token}")
        if value is None:
            if i + 1 >= len(tokens):
                raise _UsageError(f"{flag} requires a value")
            i += 1
            value = tokens[i]
        if name == "changed":
            opts["changed"] = (opts["changed"] or []) + value.split(",")
        elif name == "seed":
            try:
                opts["seed"] = int(value)
            except ValueError:
                raise _UsageError(f"--seed must be an integer: {value}")
        else:
            opts[name] = value
        i += 1
    return opts


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        opts = _parse(list(argv))
    except _UsageError as exc:
        return _usage_error(str(exc))
    repo_root = Path(opts["repo-root"])
    out_dir = Path(opts["out"]) if opts["out"] is not None else repo_root / ".hotdocs" / "ui"
    try:
        render_tracker_ui(out_dir, repo_root, opts["changed"], opts["model"], opts["seed"])
    except json.JSONDecodeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        return _usage_error(f"missing {exc.filename}")
    except ValueError as exc:
        return _usage_error(str(exc))
    print(str(out_dir / "index.html"))
    return 0
