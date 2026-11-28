"""Provenance tracker UI: one static, self-contained corpus-readiness page."""

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

_FLAGS = ("--changed", "--repo-root", "--out", "--model", "--seed")


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_tracker(root: Path):
    dep = root / "gen" / "provenance-tracker"
    if not dep.is_dir():
        dep = _tool_root() / "gen" / "provenance-tracker"
    return _load("provenance_tracker", dep / "provenance_tracker.py")


def _load_ui_style():
    path = _tool_root() / "gen" / "ui-style" / "ui_style.py"
    return _load("ui_style", path)


def _read_attempts(root: Path, component_id: str) -> list:
    attempts_dir = root / ".hotdocs" / "attempts" / component_id
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(attempts_dir.glob("*.json"))
    ]


def _component_status(result, attempts) -> str:
    if _get(result, "hit"):
        verification = _get(result, "verification_report")
        license_scan = _get(result, "license_scan")
        if _get(verification, "overall") == "pass" and not _get(license_scan, "blocked"):
            return "passing"
        return "failing"
    if attempts:
        return "missing"
    return "not-attempted"


def _capability_status(capability_id, result) -> str:
    report = _get(result, "capability_scenario_report")
    if _get(_get(report, capability_id), "overall") == "pass":
        return "passing"
    return "failing"


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _render_node(node) -> str:
    status = node["status"]
    parts = [
        f'<li class="node status-{_esc(status)} {_TONES[status]}" '
        f'data-node-id="{_esc(node["id"])}" data-kind="{_esc(node["kind"])}" '
        f'data-status="{_esc(status)}">',
        f'<span class="node-id">{_esc(node["id"])}</span>',
        f'<span class="node-kind muted">{_esc(node["kind"])}</span>',
        f'<span class="node-status">{_esc(_LABELS[status])}</span>',
    ]
    for record in node["attempts"]:
        attempt_id = record.get("attempt_id")
        parts.append(
            f'<div class="attempt" data-attempt-id="{_esc(attempt_id)}">{_esc(attempt_id)}</div>'
        )
    if node["retry_feedback"]:
        text = "--retry-feedback=" + ",".join(node["retry_feedback"])
        parts.append(f'<code class="retry-feedback">{_esc(text)}</code>')
    parts.append("</li>")
    return "\n".join(parts)


def _render_page(snapshot, style: str, script: str) -> str:
    data = json.dumps(snapshot, sort_keys=True).replace("</", "<\\/")
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Provenance tracker</title>",
        style,
        "</head>",
        "<body>",
        "<h1>Provenance tracker</h1>",
        f'<p class="scope">scope: {_esc(snapshot["scope"])}</p>',
    ]
    if snapshot["changed_ids"] is not None:
        changed = ", ".join(snapshot["changed_ids"])
        parts.append(f'<p class="changed-ids">changed: {_esc(changed)}</p>')
    parts.append('<div class="filters">')
    for value, label in _FILTERS:
        parts.append(f'<button type="button" data-filter="{value}">{label}</button>')
    parts.append("</div>")
    parts.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        parts.append(_render_node(node))
    parts.append("</ul>")
    parts.append(
        '<script type="application/json" id="tracker-snapshot">' + data + "</script>"
    )
    parts.append('<script type="module">' + script + "\ninit(document);\n" + "</script>")
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts) + "\n"


def render_tracker_ui(
    out_dir,
    repo_root,
    changed_ids=None,
    model=None,
    seed=0,
    llm_backend=None,
):
    root = Path(repo_root)
    tracker = _load_tracker(root)
    graph = json.loads(
        (root / "verification" / "corpus-graph.json").read_text(encoding="utf-8")
    )
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)

    nodes = []
    for component_id, result in _get(report, "components").items():
        attempts = _read_attempts(root, component_id)
        status = _component_status(result, attempts)
        retry_feedback = []
        if status == "passing":
            attempts = []
        elif status in ("failing", "missing"):
            retry_feedback = list(tracker.last_requirement_failures(component_id, repo_root))
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

    style = _load_ui_style().style_element()
    script = (Path(__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    page = _render_page(snapshot, style, script)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_bytes(page.encode("utf-8"))
    return snapshot


class _UsageError(Exception):
    pass


def _parse(argv):
    if argv[:3] != ["track", "ui", "build"]:
        raise _UsageError("expected 'track ui build'")
    values = {flag: [] for flag in _FLAGS}
    rest = argv[3:]
    index = 0
    while index < len(rest):
        token = rest[index]
        flag, sep, value = token.partition("=")
        if flag not in values:
            raise _UsageError(f"unknown argument {token}")
        if not sep:
            index += 1
            if index >= len(rest):
                raise _UsageError(f"{flag} needs a value")
            value = rest[index]
        values[flag].append(value)
        index += 1
    return values


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        values = _parse(list(argv))
        seed = int(values["--seed"][-1]) if values["--seed"] else 0
    except _UsageError as exc:
        return _usage_error(str(exc))
    except ValueError:
        return _usage_error("--seed must be an integer")

    changed_ids = None
    if values["--changed"]:
        changed_ids = [part for value in values["--changed"] for part in value.split(",")]
    repo_root = Path(values["--repo-root"][-1]) if values["--repo-root"] else Path(".")
    out_dir = Path(values["--out"][-1]) if values["--out"] else repo_root / ".hotdocs" / "ui"
    model = values["--model"][-1] if values["--model"] else None

    graph_path = repo_root / "verification" / "corpus-graph.json"
    if not graph_path.exists():
        return _usage_error(f"missing {graph_path}; run hotdocs corpus-graph build first")

    try:
        render_tracker_ui(out_dir, repo_root, changed_ids, model, seed)
    except json.JSONDecodeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        return _usage_error(str(exc))

    print(out_dir / "index.html")
    return 0
