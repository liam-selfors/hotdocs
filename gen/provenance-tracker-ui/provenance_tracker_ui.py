"""Provenance Tracker UI (comp-provenance-tracker-ui).

Builds one static, self-contained ``index.html`` showing corpus readiness:
every component and capability in scope, colored by its current provenance
status, with attempt history and retry-feedback suggestions for anything
failing or missing. Every read happens here, at build time; the written page
only renders data already inlined into it.
"""

from __future__ import annotations

import html
import importlib.util
import json
import sys
from pathlib import Path

__all__ = ["render_tracker_ui", "main"]

_STATUS_LABELS = {
    "passing": "passing",
    "failing": "failing",
    "missing": "missing",
    "not-attempted": "not yet attempted",
}

_NEEDS_RETRY = ("failing", "missing")

_FLAGS = ("--changed", "--repo-root", "--out", "--model", "--seed")

_USAGE = (
    "usage: hotdocs track ui build [--changed=<id>...] [--repo-root=<dir>] "
    "[--out=<dir>] [--model=<model>] [--seed=<n>]"
)

_CSS = """
body { font-family: sans-serif; margin: 1.5em; color: #202124; }
ul.nodes { list-style: none; padding: 0; }
li.node { margin: 0.4em 0; padding: 0.5em 0.8em; border-radius: 4px; }
li.node[hidden] { display: none; }
.node-id { font-family: monospace; font-weight: bold; }
.node-kind { color: #5f6368; font-size: 0.9em; }
.node-status { font-weight: bold; }
.attempt { font-family: monospace; font-size: 0.85em; margin-left: 1em; }
.retry-feedback { display: block; margin: 0.3em 0 0 1em; font-family: monospace;
  background: #ffffff; padding: 0.2em 0.4em; user-select: all; }
.status-passing { background: #e6f4ea; border-left: 6px solid #1e8e3e; }
.status-failing { background: #fce8e6; border-left: 6px solid #d93025; }
.status-missing { background: #fef7e0; border-left: 6px solid #f29900; }
.status-not-attempted { background: #f1f3f4; border-left: 6px dashed #80868b; }
""".strip()

_JS = """
(function () {
  var filter = document.getElementById("status-filter");
  var nodes = document.querySelectorAll("li.node");
  filter.addEventListener("change", function () {
    var want = filter.value;
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      node.hidden = want !== "all" && node.getAttribute("data-status") !== want;
    }
  });
})();
""".strip()


class _JsonParseError(ValueError):
    """A file that exists failed to parse as JSON."""


def _get(obj, key):
    """Dual dict-or-attribute access for values read from a dependency."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_provenance_tracker(repo_root):
    rel = Path("gen") / "provenance-tracker"
    base = Path(repo_root) / rel
    if not base.is_dir():
        base = _tool_root() / rel
    path = base / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path):
    data = path.read_bytes()
    try:
        return json.loads(data)
    except ValueError as exc:
        raise _JsonParseError(f"{path}: {exc}") from exc


def _load_attempts(root: Path, component_id: str) -> list:
    directory = root / ".hotdocs" / "attempts" / component_id
    return [_read_json(p) for p in sorted(directory.glob("*.json"))]


def _component_status(result, attempts) -> str:
    if _get(result, "hit"):
        ok = (
            _get(_get(result, "verification_report"), "overall") == "pass"
            and not _get(_get(result, "license_scan"), "blocked")
            and not _get(_get(result, "secret_scan"), "flagged")
        )
        return "passing" if ok else "failing"
    return "missing" if attempts else "not-attempted"


def _capability_status(capability_id, result) -> str:
    report = _get(_get(result, "capability_scenario_report"), capability_id)
    return "passing" if _get(report, "overall") == "pass" else "failing"


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _node_html(node) -> str:
    nid = _esc(node["id"])
    kind = _esc(node["kind"])
    status = _esc(node["status"])
    parts = [
        f'<li class="node status-{status}" data-node-id="{nid}" '
        f'data-kind="{kind}" data-status="{status}">',
        f'<span class="node-id">{nid}</span> ',
        f'<span class="node-kind">{kind}</span> ',
        f'<span class="node-status">{_esc(_STATUS_LABELS[node["status"]])}</span>',
    ]
    for record in node["attempts"]:
        attempt_id = _esc(record.get("attempt_id"))
        parts.append(
            f'<div class="attempt" data-attempt-id="{attempt_id}">attempt {attempt_id}</div>'
        )
    if node["retry_feedback"]:
        suggestion = "--retry-feedback=" + ",".join(node["retry_feedback"])
        parts.append(f'<code class="retry-feedback">{_esc(suggestion)}</code>')
    parts.append("</li>")
    return "".join(parts)


def _page_html(snapshot) -> str:
    data = json.dumps(snapshot, sort_keys=True, ensure_ascii=False).replace("</", "<\\/")
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Provenance tracker</title>",
        f"<style>\n{_CSS}\n</style>",
        "</head>",
        "<body>",
        "<h1>Provenance tracker</h1>",
        f'<p class="scope">Scope: <span class="scope-name">{_esc(snapshot["scope"])}</span></p>',
    ]
    if snapshot["changed_ids"] is not None:
        changed = ", ".join(str(c) for c in snapshot["changed_ids"])
        lines.append(f'<p class="changed-ids">Changed: {_esc(changed)}</p>')
    lines.append(f'<p class="ready">Ready: {_esc(json.dumps(snapshot["ready"]))}</p>')
    lines.append('<ul class="not-ready-reasons">')
    for reason in snapshot["not_ready_reasons"]:
        lines.append(f'<li class="reason">{_esc(reason)}</li>')
    lines.append("</ul>")
    lines.append('<label>Show <select id="status-filter">')
    lines.append('<option value="all">all</option>')
    for status, label in _STATUS_LABELS.items():
        lines.append(f'<option value="{status}">{_esc(label)}</option>')
    lines.append("</select></label>")
    lines.append('<ul class="nodes">')
    for node in snapshot["nodes"]:
        lines.append(_node_html(node))
    lines.append("</ul>")
    lines.append(f'<script type="application/json" id="tracker-snapshot">{data}</script>')
    lines.append(f"<script>\n{_JS}\n</script>")
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
    """Build one self-contained ``out_dir/index.html`` and return its snapshot."""
    root = Path(repo_root)
    tracker = _load_provenance_tracker(root)
    report = tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)

    graph = _read_json(root / "verification" / "corpus-graph.json")

    nodes = []
    for component_id, result in _get(report, "components").items():
        attempts = _load_attempts(root, component_id)
        status = _component_status(result, attempts)
        if status in _NEEDS_RETRY:
            retry = list(tracker.last_requirement_failures(component_id, repo_root))
        else:
            attempts, retry = [], []
        nodes.append({
            "id": component_id,
            "kind": "component",
            "status": status,
            "attempts": attempts,
            "retry_feedback": retry,
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
        "not_ready_reasons": _get(report, "not_ready_reasons"),
        "nodes": nodes,
        "edges": edges,
    }

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_bytes(_page_html(snapshot).encode("utf-8"))
    return snapshot


def _usage() -> int:
    print(_USAGE, file=sys.stderr)
    return 2


def main(argv) -> int:
    """``hotdocs track ui build`` (interface/cli.md)."""
    argv = list(argv)
    if argv[:3] != ["track", "ui", "build"]:
        return _usage()
    rest = argv[3:]
    opts = {}
    changed = None
    i = 0
    while i < len(rest):
        name, eq, value = rest[i].partition("=")
        if name not in _FLAGS:
            return _usage()
        if not eq:
            i += 1
            if i >= len(rest):
                return _usage()
            value = rest[i]
        if name == "--changed":
            changed = (changed or []) + value.split(",")
        else:
            opts[name] = value
        i += 1

    try:
        seed = int(opts.get("--seed", 0))
    except ValueError:
        return _usage()
    repo_root = Path(opts.get("--repo-root", "."))
    out = Path(opts.get("--out", repo_root / ".hotdocs" / "ui"))

    try:
        render_tracker_ui(out, repo_root, changed, opts.get("--model"), seed)
    except _JsonParseError as exc:
        print(exc, file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2
    print(out / "index.html")
    return 0
