"""Builds the self-contained provenance tracker UI page (R-UI-001..009)."""
from __future__ import annotations

import html
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


class UsageError(Exception):
    """CLI usage error for this component's own argv, distinct from provenance-tracker's."""


class _JSONParseError(ValueError):
    """An existing JSON input (corpus-graph.json or an AttemptRecord) failed to parse."""


_MODULE_CACHE: dict[str, Any] = {}


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        if ancestor.name == "gen":
            return ancestor.parent
    raise RuntimeError("cannot locate tool root: no ancestor directory named 'gen'")


def _load_dependency_module(repo_root: Path, dep_subpath: str, module_name: str) -> Any:
    bases = [Path(repo_root) / dep_subpath, _tool_root() / dep_subpath]
    for base in bases:
        flat = base / f"{module_name}.py"
        pkg = base / module_name / "__init__.py"
        if flat.is_file():
            path = flat
        elif pkg.is_file():
            path = pkg
        else:
            continue
        key = str(path.resolve())
        cached = _MODULE_CACHE.get(key)
        if cached is not None:
            return cached
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        # Must be registered before exec_module: dataclasses defined in the
        # loaded module resolve sys.modules[cls.__module__] while their class
        # body executes.
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        _MODULE_CACHE[key] = module
        return module
    raise RuntimeError(
        f"cannot find module {module_name!r} under {bases[0]} or {bases[1]}"
    )


def _read_corpus_graph(repo_root: Path) -> dict:
    path = Path(repo_root) / "verification" / "corpus-graph.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing corpus graph: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise _JSONParseError(f"invalid JSON in {path}: {e}") from e


def _read_attempts(repo_root: Path, component_id: str) -> list:
    d = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    if not d.is_dir():
        return []
    records = []
    for f in sorted(d.glob("*.json")):  # attempt_id-prefixed filenames sort chronologically
        try:
            records.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            raise _JSONParseError(f"invalid JSON in {f}: {e}") from e
    return records


def _build_component_node(repo_root: Path, provenance_tracker: Any, comp_id: str, val: Any) -> dict:
    hit = _get(val, "hit")
    attempts: list = []
    if hit:
        vr = _get(val, "verification_report")
        overall = _get(vr, "overall") if vr is not None else None
        lic = _get(val, "license_scan")
        lic_blocked = bool(_get(lic, "blocked", False)) if lic is not None else False
        sec = _get(val, "secret_scan")
        sec_flagged = bool(_get(sec, "flagged", False)) if sec is not None else False
        if overall == "pass" and not lic_blocked and not sec_flagged:
            status = "passing"
        else:
            status = "failing"
            attempts = _read_attempts(repo_root, comp_id)
    else:
        attempts = _read_attempts(repo_root, comp_id)
        status = "missing" if attempts else "not-attempted"

    if status in ("failing", "missing"):
        feedback_raw = provenance_tracker.last_requirement_failures(comp_id, repo_root)
        retry_feedback = list(feedback_raw) if feedback_raw else []
    else:
        retry_feedback = []

    return {
        "id": comp_id,
        "kind": "component",
        "status": status,
        "attempts": attempts,
        "retry_feedback": retry_feedback,
    }


def _build_capability_node(cap_id: str, val: Any) -> dict:
    csr = _get(val, "capability_scenario_report")
    entry = _get(csr, cap_id) if csr is not None else None
    overall = _get(entry, "overall") if entry is not None else None
    status = "passing" if overall == "pass" else "failing"
    return {
        "id": cap_id,
        "kind": "capability",
        "status": status,
        "attempts": [],
        "retry_feedback": [],
    }


_STATUS_LABELS = {
    "passing": "passing",
    "failing": "failing",
    "missing": "missing",
    "not-attempted": "not yet attempted",
}

_CSS = """
body { font-family: sans-serif; margin: 2em; color: #222; }
h1 { margin-bottom: 0.2em; }
.scope, .ready { margin: 0.2em 0; }
ul.not-ready-reasons { color: #a33; }
ul.nodes { list-style: none; padding: 0; }
li.node {
  border: 1px solid #ccc;
  border-radius: 4px;
  padding: 0.6em 0.8em;
  margin: 0.4em 0;
}
li.node.status-passing { background: #e3f6e3; border-color: #4caf50; }
li.node.status-failing { background: #fbe3e3; border-color: #e53935; }
li.node.status-missing { background: #fff3cd; border-color: #ffb300; }
li.node.status-not-attempted { background: #eceff1; border-color: #90a4ae; }
.node-id { font-weight: bold; margin-right: 0.6em; }
.node-kind { color: #666; margin-right: 0.6em; }
.node-status-label { font-style: italic; }
ul.attempts { margin: 0.4em 0 0.2em 1em; padding: 0; }
li.attempt { font-family: monospace; font-size: 0.85em; }
.retry-feedback {
  font-family: monospace;
  background: #fff;
  border: 1px dashed #999;
  padding: 0.3em 0.5em;
  margin-top: 0.3em;
  display: inline-block;
}
.filters button { margin-right: 0.4em; }
"""

_JS = """
document.addEventListener('DOMContentLoaded', function () {
  var buttons = document.querySelectorAll('.filter-btn');
  var nodes = document.querySelectorAll('.node');
  buttons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var filter = btn.getAttribute('data-filter');
      nodes.forEach(function (node) {
        if (filter === 'all' || node.getAttribute('data-status') === filter) {
          node.style.display = '';
        } else {
          node.style.display = 'none';
        }
      });
    });
  });
});
"""


def _render_node_html(node: dict) -> str:
    nid = html.escape(str(node["id"]), quote=True)
    kind = html.escape(str(node["kind"]), quote=True)
    status = html.escape(str(node["status"]), quote=True)
    label = html.escape(_STATUS_LABELS[node["status"]])
    parts = [
        f'<li class="node status-{status}" data-node-id="{nid}" data-kind="{kind}" data-status="{status}">',
        f'<span class="node-id">{nid}</span>',
        f'<span class="node-kind">{kind}</span>',
        f'<span class="node-status-label">{label}</span>',
    ]
    if node["status"] in ("failing", "missing"):
        parts.append('<ul class="attempts">')
        for att in node["attempts"]:
            att_id = att.get("attempt_id", "") if isinstance(att, dict) else getattr(att, "attempt_id", "")
            att_id_esc = html.escape(str(att_id), quote=True)
            parts.append(f'<li class="attempt" data-attempt-id="{att_id_esc}">{att_id_esc}</li>')
        parts.append("</ul>")
        if node["retry_feedback"]:
            feedback_text = "--retry-feedback=" + ",".join(str(r) for r in node["retry_feedback"])
            parts.append(f'<div class="retry-feedback">{html.escape(feedback_text)}</div>')
    parts.append("</li>")
    return "".join(parts)


def _render_html(snapshot: dict) -> str:
    json_text = json.dumps(snapshot, sort_keys=True, ensure_ascii=True)
    json_text = json_text.replace("</", "<\\/")

    scope = str(snapshot["scope"])
    changed_ids_html = ""
    if snapshot["changed_ids"]:
        ids_str = ", ".join(html.escape(str(c)) for c in snapshot["changed_ids"])
        changed_ids_html = f" (changed: {ids_str})"

    reasons_html = "\n".join(
        f'<li class="not-ready-reason">{html.escape(str(r))}</li>'
        for r in snapshot["not_ready_reasons"]
    )

    nodes_html = "\n".join(_render_node_html(n) for n in snapshot["nodes"])

    ready_bool = bool(snapshot["ready"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Provenance Tracker</title>
<style>
{_CSS}
</style>
</head>
<body>
<h1>Provenance Tracker</h1>
<p class="scope" data-scope="{html.escape(scope, quote=True)}">Scope: {html.escape(scope)}{changed_ids_html}</p>
<p class="ready" data-ready="{"true" if ready_bool else "false"}">Ready: {"yes" if ready_bool else "no"}</p>
<ul class="not-ready-reasons">
{reasons_html}
</ul>
<div class="filters">
<button class="filter-btn" data-filter="all">All</button>
<button class="filter-btn" data-filter="passing">Passing</button>
<button class="filter-btn" data-filter="failing">Failing</button>
<button class="filter-btn" data-filter="missing">Missing</button>
<button class="filter-btn" data-filter="not-attempted">Not yet attempted</button>
</div>
<ul class="nodes">
{nodes_html}
</ul>
<script type="application/json" id="tracker-snapshot">{json_text}</script>
<script>
{_JS}
</script>
</body>
</html>
"""


def render_tracker_ui(
    out_dir,
    repo_root,
    changed_ids: list | None = None,
    model: str | None = None,
    seed: int = 0,
    llm_backend=None,
) -> dict:
    repo_root = Path(repo_root)
    out_dir = Path(out_dir)

    provenance_tracker = _load_dependency_module(repo_root, "gen/provenance-tracker", "provenance_tracker")

    report = provenance_tracker.check_readiness(repo_root, changed_ids, model, seed, llm_backend)

    graph = _read_corpus_graph(repo_root)

    components_result = _get(report, "components", {}) or {}
    capabilities_result = _get(report, "capabilities", {}) or {}
    not_ready_reasons = list(_get(report, "not_ready_reasons", []) or [])
    scope = _get(report, "scope")
    ready = _get(report, "ready")

    nodes: dict[str, dict] = {}
    for comp_id, val in components_result.items():
        nodes[comp_id] = _build_component_node(repo_root, provenance_tracker, comp_id, val)
    for cap_id, val in capabilities_result.items():
        nodes[cap_id] = _build_capability_node(cap_id, val)

    node_ids = set(nodes.keys())
    node_list = [nodes[k] for k in sorted(nodes.keys())]

    edges = graph.get("edges", []) if isinstance(graph, dict) else []
    edge_list = [
        {"from": e.get("from"), "to": e.get("to"), "kind": e.get("kind")}
        for e in edges
        if isinstance(e, dict) and e.get("from") in node_ids and e.get("to") in node_ids
    ]

    snapshot = {
        "scope": scope,
        "changed_ids": list(changed_ids) if changed_ids is not None else None,
        "ready": ready,
        "not_ready_reasons": not_ready_reasons,
        "nodes": node_list,
        "edges": edge_list,
    }

    html_doc = _render_html(snapshot)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html_doc, encoding="utf-8")

    return snapshot


def _parse_args(argv: list[str]) -> dict:
    if len(argv) < 3 or list(argv[0:3]) != ["track", "ui", "build"]:
        raise UsageError("expected argv beginning with 'track ui build'")
    rest = argv[3:]
    known = {"--changed", "--repo-root", "--out", "--model", "--seed"}

    changed: list[str] = []
    repo_root_val = None
    out_val = None
    model_val = None
    seed_val = 0

    i = 0
    while i < len(rest):
        tok = rest[i]
        if not tok.startswith("--"):
            raise UsageError(f"unexpected argument: {tok}")
        if "=" in tok:
            flag, val = tok.split("=", 1)
            i += 1
        else:
            flag = tok
            if i + 1 >= len(rest):
                raise UsageError(f"missing value for {flag}")
            val = rest[i + 1]
            i += 2

        if flag not in known:
            raise UsageError(f"unknown flag: {flag}")

        if flag == "--changed":
            changed.extend(part for part in val.split(",") if part)
        elif flag == "--repo-root":
            repo_root_val = val
        elif flag == "--out":
            out_val = val
        elif flag == "--model":
            model_val = val
        elif flag == "--seed":
            try:
                seed_val = int(val)
            except ValueError:
                raise UsageError(f"--seed must be an integer, got {val!r}")

    repo_root = Path(repo_root_val) if repo_root_val is not None else Path.cwd()
    out_dir = Path(out_val) if out_val is not None else (repo_root / ".hotdocs" / "ui")

    return {
        "changed_ids": changed if changed else None,
        "repo_root": repo_root,
        "out": out_dir,
        "model": model_val,
        "seed": seed_val,
    }


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    try:
        args = _parse_args(list(argv))
    except UsageError as e:
        print(f"usage error: {e}", file=sys.stderr)
        return 2

    try:
        render_tracker_ui(args["out"], args["repo_root"], args["changed_ids"], args["model"], args["seed"])
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2
    except _JSONParseError as e:
        print(str(e), file=sys.stderr)
        return 1
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    except Exception as e:
        if type(e).__name__ == "UsageError":
            print(str(e), file=sys.stderr)
            return 2
        raise

    print(str(args["out"] / "index.html"))
    return 0


if __name__ == "__main__":
    sys.exit(main())