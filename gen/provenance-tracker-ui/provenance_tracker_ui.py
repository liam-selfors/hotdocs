"""Builds a self-contained provenance-tracker-ui index.html at build time."""

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from html import escape as _html_escape
from pathlib import Path
from typing import Any, Dict, List, Optional

_dependency_cache: Dict[tuple, Any] = {}

STATUS_LABELS = {
    "passing": "passing",
    "failing": "failing",
    "missing": "missing",
    "not-attempted": "not yet attempted",
}


@dataclass
class TrackerSnapshot:
    scope: str
    changed_ids: Optional[List[str]]
    ready: bool
    not_ready_reasons: List[str] = field(default_factory=list)
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _load_dependency_module(repo_root: Path, slug: str, module_name: str):
    key = (str(Path(repo_root).resolve()), slug, module_name)
    cached = _dependency_cache.get(key)
    if cached is not None:
        return cached

    base = Path(repo_root) / "gen" / slug
    pkg_init = base / module_name / "__init__.py"
    flat = base / f"{module_name}.py"

    if pkg_init.exists():
        file_path = pkg_init
        search_locations = [str(file_path.parent)]
    elif flat.exists():
        file_path = flat
        search_locations = None
    else:
        raise ImportError(f"cannot locate dependency module {module_name!r} under {base}")

    spec = importlib.util.spec_from_file_location(
        module_name, file_path, submodule_search_locations=search_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    _dependency_cache[key] = module
    return module


def _load_attempts(repo_root: Path, component_id: str) -> List[Any]:
    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    if not attempts_dir.is_dir():
        return []
    records = []
    for file_path in sorted(attempts_dir.glob("*.json")):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {file_path}: {exc}") from exc
        records.append(data)
    return records


def _load_corpus_graph_edges(repo_root: Path, node_ids: set) -> List[Dict[str, str]]:
    graph_path = Path(repo_root) / "verification" / "corpus-graph.json"
    if not graph_path.is_file():
        raise FileNotFoundError(f"missing corpus graph: {graph_path}")
    try:
        data = json.loads(graph_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {graph_path}: {exc}") from exc

    edges = data.get("edges", []) if isinstance(data, dict) else []
    result = []
    for edge in edges or []:
        src = edge.get("from") if isinstance(edge, dict) else None
        dst = edge.get("to") if isinstance(edge, dict) else None
        kind = edge.get("kind") if isinstance(edge, dict) else None
        if src in node_ids and dst in node_ids:
            result.append({"from": src, "to": dst, "kind": kind})
    return result


def _build_component_node(pt, repo_root: Path, component_id: str, entry: Any) -> Dict[str, Any]:
    hit = bool(_get(entry, "hit"))
    attempts = _load_attempts(repo_root, component_id)

    if hit:
        verification_report = _get(entry, "verification_report")
        overall = _get(verification_report, "overall")
        license_scan = _get(entry, "license_scan")
        license_blocked = bool(_get(license_scan, "blocked", False))
        secret_scan = _get(entry, "secret_scan")
        secret_flagged = bool(_get(secret_scan, "flagged", False))
        if overall == "pass" and not license_blocked and not secret_flagged:
            status = "passing"
        else:
            status = "failing"
    else:
        status = "missing" if attempts else "not-attempted"

    if status in ("failing", "missing"):
        retry_feedback = list(pt.last_requirement_failures(component_id, repo_root) or [])
    else:
        attempts = []
        retry_feedback = []

    return {
        "id": component_id,
        "kind": "component",
        "status": status,
        "attempts": attempts,
        "retry_feedback": retry_feedback,
    }


def _build_capability_node(capability_id: str, entry: Any) -> Dict[str, Any]:
    scenario_report = _get(entry, "capability_scenario_report")
    overall = _get(scenario_report, "overall")
    status = "passing" if overall == "pass" else "failing"
    return {
        "id": capability_id,
        "kind": "capability",
        "status": status,
        "attempts": [],
        "retry_feedback": [],
    }


def render_tracker_ui(
    out_dir,
    repo_root,
    changed_ids: Optional[List[str]] = None,
    model: Optional[str] = None,
    seed: int = 0,
    llm_backend: Any = None,
) -> TrackerSnapshot:
    repo_root = Path(repo_root)
    out_dir = Path(out_dir)

    pt = _load_dependency_module(repo_root, "provenance-tracker", "provenance_tracker")

    report = pt.check_readiness(
        repo_root=repo_root,
        changed_ids=changed_ids,
        model=model,
        seed=seed,
        llm_backend=llm_backend,
    )

    scope = _get(report, "scope")
    ready = _get(report, "ready")
    not_ready_reasons = list(_get(report, "not_ready_reasons", []) or [])
    components = _get(report, "components", {}) or {}
    capabilities = _get(report, "capabilities", {}) or {}

    nodes: List[Dict[str, Any]] = []
    for component_id, entry in components.items():
        nodes.append(_build_component_node(pt, repo_root, component_id, entry))
    for capability_id, entry in capabilities.items():
        nodes.append(_build_capability_node(capability_id, entry))

    nodes.sort(key=lambda n: n["id"])
    node_ids = {n["id"] for n in nodes}

    edges = _load_corpus_graph_edges(repo_root, node_ids)

    snapshot_dict = {
        "scope": scope,
        "changed_ids": list(changed_ids) if changed_ids is not None else None,
        "ready": ready,
        "not_ready_reasons": not_ready_reasons,
        "nodes": nodes,
        "edges": edges,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    html_doc = _render_html(snapshot_dict)
    (out_dir / "index.html").write_text(html_doc, encoding="utf-8")

    return TrackerSnapshot(**snapshot_dict)


def _esc(value: Any) -> str:
    return _html_escape(str(value), quote=True)


def _render_attempts(attempts: List[Any]) -> str:
    if not attempts:
        return '<ul class="attempts"></ul>'
    items = []
    for attempt in attempts:
        attempt_id = _get(attempt, "attempt_id", "")
        timestamp = _get(attempt, "timestamp", "")
        items.append(
            '<li class="attempt" data-attempt-id="' + _esc(attempt_id) + '">'
            '<span class="attempt-timestamp">' + _esc(timestamp) + "</span>"
            "</li>"
        )
    return '<ul class="attempts">' + "".join(items) + "</ul>"


def _render_node(node: Dict[str, Any]) -> str:
    status = node["status"]
    label = STATUS_LABELS.get(status, status)
    pieces = [
        f'<li class="node status-{_esc(status)}" data-node-id="{_esc(node["id"])}" '
        f'data-kind="{_esc(node["kind"])}" data-status="{_esc(status)}">',
        f'<span class="node-id">{_esc(node["id"])}</span>',
        f'<span class="node-kind">{_esc(node["kind"])}</span>',
        f'<span class="node-status-label">{_esc(label)}</span>',
    ]
    if status in ("failing", "missing"):
        pieces.append(_render_attempts(node["attempts"]))
        retry_feedback = node["retry_feedback"]
        if retry_feedback:
            suggestion = "--retry-feedback=" + ",".join(retry_feedback)
            pieces.append(f'<div class="retry-feedback">{_esc(suggestion)}</div>')
    pieces.append("</li>")
    return "".join(pieces)


_CSS = """
body { font-family: sans-serif; margin: 2rem; color: #1a1a1a; }
.filters button { margin-right: 0.5rem; }
ul.nodes { list-style: none; padding: 0; }
li.node { border: 1px solid #ccc; border-radius: 4px; padding: 0.5rem; margin-bottom: 0.5rem; }
li.node.hidden { display: none; }
.node-id { font-weight: bold; margin-right: 0.5rem; }
.node-kind { color: #666; margin-right: 0.5rem; }
.node-status-label { font-style: italic; }
.status-passing { background: #e6ffed; border-color: #2ea44f; }
.status-failing { background: #ffeef0; border-color: #d73a49; }
.status-missing { background: #fff8e6; border-color: #e3a008; }
.status-not-attempted { background: #f0f1f3; border-color: #959da5; }
ul.attempts { margin: 0.25rem 0 0.25rem 1rem; padding: 0; }
.attempt { font-size: 0.85rem; color: #444; }
.retry-feedback { font-family: monospace; background: #f6f8fa; padding: 0.25rem; margin-top: 0.25rem; display: inline-block; }
ul.not-ready-reasons { color: #d73a49; }
"""

_JS = """
(function () {
  var buttons = document.querySelectorAll('.filters button');
  var nodes = document.querySelectorAll('.nodes > .node');
  for (var b = 0; b < buttons.length; b++) {
    buttons[b].addEventListener('click', function (event) {
      var filter = event.target.getAttribute('data-filter');
      for (var n = 0; n < nodes.length; n++) {
        var node = nodes[n];
        if (filter === 'all' || node.getAttribute('data-status') === filter) {
          node.classList.remove('hidden');
        } else {
          node.classList.add('hidden');
        }
      }
    });
  }
})();
"""


def _render_html(snapshot: Dict[str, Any]) -> str:
    json_text = json.dumps(snapshot, ensure_ascii=True, separators=(",", ":"))
    json_text_safe = json_text.replace("</", "<\\/")

    nodes_html = "".join(_render_node(n) for n in snapshot["nodes"])

    scope_label = _esc(snapshot["scope"])
    ready_value = snapshot["ready"]
    ready_class = "true" if ready_value else "false"
    ready_label = _esc(ready_value)

    changed_ids = snapshot["changed_ids"]
    changed_html = ""
    if changed_ids:
        changed_html = '<div class="changed-ids">changed: ' + _esc(", ".join(changed_ids)) + "</div>\n"

    not_ready_reasons = snapshot["not_ready_reasons"]
    reasons_html = ""
    if not_ready_reasons:
        reasons_items = "".join("<li>" + _esc(r) + "</li>" for r in not_ready_reasons)
        reasons_html = '<ul class="not-ready-reasons">' + reasons_items + "</ul>\n"

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        "<title>Provenance Tracker</title>\n"
        "<style>\n" + _CSS + "\n</style>\n"
        "</head>\n"
        "<body>\n"
        "<h1>Provenance Tracker</h1>\n"
        '<div class="scope">scope: <span class="scope-value">' + scope_label + "</span></div>\n"
        + changed_html
        + '<div class="ready ready-' + ready_class + '">ready: ' + ready_label + "</div>\n"
        + reasons_html
        + '<div class="filters">\n'
        '<button type="button" data-filter="all">all</button>\n'
        '<button type="button" data-filter="passing">passing</button>\n'
        '<button type="button" data-filter="failing">failing</button>\n'
        '<button type="button" data-filter="missing">missing</button>\n'
        '<button type="button" data-filter="not-attempted">not yet attempted</button>\n'
        "</div>\n"
        '<ul class="nodes">\n' + nodes_html + "\n</ul>\n"
        '<script type="application/json" id="tracker-snapshot">' + json_text_safe + "</script>\n"
        "<script>\n" + _JS + "\n</script>\n"
        "</body>\n"
        "</html>\n"
    )


def _parse_args(rest: List[str]):
    changed: List[str] = []
    repo_root = None
    out = None
    model = None
    seed = 0

    i = 0
    while i < len(rest):
        token = rest[i]
        if not token.startswith("--"):
            raise ValueError(f"unexpected argument {token!r}")
        if "=" in token:
            flag, value = token.split("=", 1)
            i += 1
        else:
            flag = token
            i += 1
            if i >= len(rest):
                raise ValueError(f"{flag} requires a value")
            value = rest[i]
            i += 1

        if flag == "--changed":
            changed.extend(v for v in value.split(",") if v)
        elif flag == "--repo-root":
            repo_root = value
        elif flag == "--out":
            out = value
        elif flag == "--model":
            model = value
        elif flag == "--seed":
            try:
                seed = int(value)
            except ValueError:
                raise ValueError(f"--seed must be an integer, got {value!r}")
        else:
            raise ValueError(f"unknown flag {flag!r}")

    return changed, repo_root, out, model, seed


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if list(argv[:3]) != ["track", "ui", "build"]:
        print("usage: hotdocs track ui build [--changed=<id>...] [--repo-root=<dir>] [--out=<dir>] [--model=<model>] [--seed=<n>]", file=sys.stderr)
        return 2

    rest = list(argv[3:])

    try:
        changed, repo_root, out, model, seed = _parse_args(rest)
    except ValueError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    repo_root_path = Path(repo_root) if repo_root else Path.cwd()
    out_path = Path(out) if out else repo_root_path / ".hotdocs" / "ui"
    changed_ids = changed if changed else None

    try:
        pt = _load_dependency_module(repo_root_path, "provenance-tracker", "provenance_tracker")
    except Exception as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    try:
        render_tracker_ui(out_path, repo_root_path, changed_ids=changed_ids, model=model, seed=seed)
    except pt.UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(str(out_path / "index.html"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))