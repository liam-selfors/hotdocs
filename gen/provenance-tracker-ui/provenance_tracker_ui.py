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

_VALUE_FLAGS = ("--changed", "--repo-root", "--out", "--model", "--seed")

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
li.node { margin: 0.4em 0; padding: 0.5em; border-left: 6px solid #999; }
li.node[hidden] { display: none; }
.status-passing { border-left-color: #2e7d32; background: #e8f5e9; }
.status-failing { border-left-color: #c62828; background: #ffebee; }
.status-missing { border-left-color: #ef6c00; background: #fff3e0; }
.status-not-attempted { border-left-color: #757575; background: #f5f5f5; font-style: italic; }
.node-id { font-weight: bold; }
.node-kind { color: #555; margin-left: 0.5em; }
.node-label { margin-left: 0.5em; }
.attempt { font-family: monospace; margin-left: 1em; }
.retry-feedback { display: block; margin-left: 1em; font-family: monospace; }
.filters button { margin-right: 0.3em; }
"""


class _JsonInputError(ValueError):
    """An existing input file failed to parse as JSON."""


class _UsageError(Exception):
    """A command-line usage error."""


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root() -> Path:
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load_dependency(repo_root: Path, slug: str, module_name: str):
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    path = directory / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path):
    try:
        return json.loads(path.read_bytes().decode("utf-8"))
    except ValueError as exc:
        raise _JsonInputError(f"{path}: {exc}") from exc


def _read_attempts(repo_root: Path, component_id: str) -> list:
    directory = repo_root / ".hotdocs" / "attempts" / component_id
    return [_load_json(p) for p in sorted(directory.glob("*.json"))]


def _component_node(tracker, repo_root: Path, cid: str, result) -> dict:
    hit = _get(result, "hit")
    overall = _get(_get(result, "verification_report"), "overall")
    blocked = _get(_get(result, "license_scan"), "blocked")
    flagged = _get(_get(result, "secret_scan"), "flagged")
    if hit and overall == "pass" and not blocked and not flagged:
        return {"id": cid, "kind": "component", "status": "passing",
                "attempts": [], "retry_feedback": []}
    attempts = _read_attempts(repo_root, cid)
    if hit:
        status = "failing"
    elif attempts:
        status = "missing"
    else:
        status = "not-attempted"
    feedback = []
    if status in ("failing", "missing"):
        feedback = list(tracker.last_requirement_failures(cid, repo_root))
    return {"id": cid, "kind": "component", "status": status,
            "attempts": attempts, "retry_feedback": feedback}


def _capability_node(cid: str, result) -> dict:
    overall = _get(_get(_get(result, "capability_scenario_report"), cid), "overall")
    status = "passing" if overall == "pass" else "failing"
    return {"id": cid, "kind": "capability", "status": status,
            "attempts": [], "retry_feedback": []}


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _render_node(node: dict) -> str:
    status = node["status"]
    parts = [
        f'<li class="node status-{_esc(status)}" data-node-id="{_esc(node["id"])}" '
        f'data-kind="{_esc(node["kind"])}" data-status="{_esc(status)}">',
        f'<span class="node-id">{_esc(node["id"])}</span>',
        f'<span class="node-kind">{_esc(node["kind"])}</span>',
        f'<span class="node-label">{_esc(_LABELS[status])}</span>',
    ]
    for attempt in node["attempts"]:
        attempt_id = _esc(attempt.get("attempt_id", ""))
        parts.append(f'<div class="attempt" data-attempt-id="{attempt_id}">{attempt_id}</div>')
    if node["retry_feedback"]:
        text = "--retry-feedback=" + ",".join(node["retry_feedback"])
        parts.append(f'<code class="retry-feedback">{_esc(text)}</code>')
    parts.append("</li>")
    return "".join(parts)


def _render_page(snapshot: dict, script: str) -> str:
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
        f'<p class="scope">Scope: <span class="scope-name">{_esc(snapshot["scope"])}</span></p>',
    ]
    if snapshot["changed_ids"] is not None:
        ids = ", ".join(snapshot["changed_ids"])
        lines.append(f'<p class="changed-ids">Changed: <span>{_esc(ids)}</span></p>')
    lines.append(f'<p class="ready">Ready: {_esc(json.dumps(snapshot["ready"]))}</p>')
    lines.append('<div class="not-ready-reasons">')
    for reason in snapshot["not_ready_reasons"]:
        lines.append(f'<p class="reason">{_esc(reason)}</p>')
    lines.append("</div>")
    lines.append('<div class="filters">')
    for value, text in _FILTERS:
        lines.append(f'<button type="button" data-filter="{value}">{text}</button>')
    lines.append("</div>")
    lines.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        lines.append(_render_node(node))
    lines.append("</ul>")
    lines.append(f'<script type="application/json" id="tracker-snapshot">{data}</script>')
    lines.append('<script type="module">' + script + "\ninit(document);\n" + "</script>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def render_tracker_ui(
    out_dir: Path, repo_root: Path, changed_ids: list[str] | None = None,
    model: str | None = None, seed: int = 0, llm_backend=None,
):
    out_dir = Path(out_dir)
    repo_root = Path(repo_root)
    tracker = _load_dependency(repo_root, "provenance-tracker", "provenance_tracker")
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)
    graph = _load_json(repo_root / "verification" / "corpus-graph.json")

    nodes = []
    components = _get(report, "components")
    for cid in components:
        nodes.append(_component_node(tracker, repo_root, cid, components[cid]))
    capabilities = _get(report, "capabilities")
    for cid in capabilities:
        nodes.append(_capability_node(cid, capabilities[cid]))
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

    script = (Path(__file__).parent / "static" / "app.js").read_bytes().decode("utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_bytes(_render_page(snapshot, script).encode("utf-8"))
    return snapshot


def _parse(argv: list[str]) -> dict:
    if argv[:3] != ["track", "ui", "build"]:
        raise _UsageError("expected: track ui build")
    rest = argv[3:]
    opts: dict = {}
    i = 0
    while i < len(rest):
        name, eq, value = rest[i].partition("=")
        if name not in _VALUE_FLAGS:
            raise _UsageError(f"unknown argument: {rest[i]}")
        if not eq:
            i += 1
            if i >= len(rest):
                raise _UsageError(f"missing value for {name}")
            value = rest[i]
        i += 1
        if name == "--changed":
            opts.setdefault("--changed", []).extend(value.split(","))
        else:
            opts[name] = value
    try:
        opts["--seed"] = int(opts.get("--seed", "0"))
    except ValueError:
        raise _UsageError(f"--seed must be an integer: {opts['--seed']}")
    return opts


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        opts = _parse(list(argv))
        repo_root = Path(opts.get("--repo-root", Path.cwd()))
        out_dir = Path(opts.get("--out", repo_root / ".hotdocs" / "ui"))
        graph_path = repo_root / "verification" / "corpus-graph.json"
        if not graph_path.exists():
            raise _UsageError(f"missing {graph_path}; run hotdocs corpus-graph build first")
        try:
            render_tracker_ui(
                out_dir, repo_root, opts.get("--changed"),
                opts.get("--model"), opts["--seed"],
            )
        except _JsonInputError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        except ValueError as exc:
            raise _UsageError(str(exc))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    print(out_dir / "index.html")
    return 0
