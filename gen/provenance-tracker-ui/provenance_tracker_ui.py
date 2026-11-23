"""Provenance Tracker UI: a static, self-contained corpus-readiness page."""

from __future__ import annotations

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

_LABELS = {
    "passing": "passing",
    "failing": "failing",
    "missing": "missing",
    "not-attempted": "not yet attempted",
}

_FILTERS = (
    ("all", "all"),
    ("passing", "passing"),
    ("failing", "failing"),
    ("missing", "missing"),
    ("not-attempted", "not yet attempted"),
)

_CSS = """
body { font-family: sans-serif; margin: 2em; }
ul.nodes { list-style: none; padding: 0; }
li.node { margin: 0.3em 0; padding: 0.4em 0.6em; border-left: 0.5em solid #999; }
li.node[hidden] { display: none; }
.status-passing { border-left-color: #2e7d32; background: #e8f5e9; }
.status-failing { border-left-color: #c62828; background: #ffebee; }
.status-missing { border-left-color: #ef6c00; background: #fff3e0; }
.status-not-attempted { border-left-color: #757575; background: #f5f5f5; font-style: italic; }
.node-id { font-weight: bold; }
.attempt { margin-left: 1em; font-family: monospace; }
.retry-feedback { display: block; margin-left: 1em; }
"""


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_dependency(repo_root, slug, module_name):
    rel = Path("gen") / slug
    base = Path(repo_root) / rel
    if not base.is_dir():
        base = _tool_root() / rel
    path = base / f"{module_name}.py"
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
        f'<li class="node status-{_esc(status)}" data-node-id="{_esc(node["id"])}" '
        f'data-kind="{_esc(node["kind"])}" data-status="{_esc(status)}">',
        f'<span class="node-id">{_esc(node["id"])}</span> ',
        f'<span class="node-kind">{_esc(node["kind"])}</span> ',
        f'<span class="status-label">{_esc(_LABELS[status])}</span>',
    ]
    for record in node["attempts"]:
        attempt_id = record.get("attempt_id")
        parts.append(
            f'<div class="attempt" data-attempt-id="{_esc(attempt_id)}">'
            f"{_esc(attempt_id)}</div>"
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
        "<title>Provenance tracker</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        "<h1>Provenance tracker</h1>",
        f'<p class="scope">Scope: <span class="scope-value">{_esc(snapshot["scope"])}</span></p>',
    ]
    if snapshot["changed_ids"] is not None:
        changed = ", ".join(str(c) for c in snapshot["changed_ids"])
        lines.append(
            f'<p class="changed-ids">Changed: <span class="changed-ids-value">{_esc(changed)}</span></p>'
        )
    lines.append(f'<p class="ready">Ready: {_esc(json.dumps(snapshot["ready"]))}</p>')
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
    lines.append('<script type="module">' + script_text + "\ninit(document);\n" + "</script>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def render_tracker_ui(
    out_dir: Path,
    repo_root: Path,
    changed_ids: list[str] | None = None,
    model: str | None = None,
    seed: int = 0,
    llm_backend=None,
) -> dict:
    root = Path(repo_root)
    tracker = _load_dependency(repo_root, "provenance-tracker", "provenance_tracker")
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)

    graph = json.loads(
        (root / "verification" / "corpus-graph.json").read_text(encoding="utf-8")
    )

    nodes = []
    for component_id, result in dict(_get(report, "components")).items():
        attempts = _read_attempts(root, component_id)
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
    for capability_id, result in dict(_get(report, "capabilities")).items():
        nodes.append({
            "id": capability_id,
            "kind": "capability",
            "status": _capability_status(capability_id, result),
            "attempts": [],
            "retry_feedback": [],
        })
    nodes.sort(key=lambda n: n["id"])

    ids = {n["id"] for n in nodes}
    edges = [
        edge for edge in graph["edges"]
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

    script_text = (Path(__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    page = _render_page(snapshot, script_text)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_bytes(page.encode("utf-8"))
    return snapshot


class _UsageError(Exception):
    pass


def _usage(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _parse(args):
    values = {}
    i = 0
    while i < len(args):
        token = args[i]
        name, eq, value = token.partition("=")
        if name not in _FLAGS:
            raise _UsageError(f"unknown argument: {token}")
        if not eq:
            i += 1
            if i >= len(args):
                raise _UsageError(f"{name} requires a value")
            value = args[i]
        values.setdefault(name, []).append(value)
        i += 1
    return values


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv[:3] != ["track", "ui", "build"]:
        return _usage("expected: track ui build")
    try:
        values = _parse(argv[3:])
        seed = int(values.get("--seed", ["0"])[-1])
    except _UsageError as exc:
        return _usage(str(exc))
    except ValueError:
        return _usage("--seed must be an integer")

    changed = None
    if "--changed" in values:
        changed = [part for value in values["--changed"] for part in value.split(",")]
    repo_root = Path(values.get("--repo-root", ["."])[-1])
    out_dir = Path(values["--out"][-1]) if "--out" in values else repo_root / ".hotdocs" / "ui"
    model = values.get("--model", [None])[-1]

    graph_path = repo_root / "verification" / "corpus-graph.json"
    if not graph_path.exists():
        return _usage(f"missing {graph_path}; run hotdocs corpus-graph build first")

    try:
        render_tracker_ui(out_dir, repo_root, changed, model, seed)
    except json.JSONDecodeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        return _usage(str(exc))
    print(out_dir / "index.html")
    return 0
