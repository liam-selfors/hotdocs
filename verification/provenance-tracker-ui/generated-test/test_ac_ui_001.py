import dataclasses
import json
import re
from pathlib import Path

import pytest

import provenance_tracker_ui


SNAPSHOT_OPEN = '<script type="application/json" id="tracker-snapshot">'


FAKE_TRACKER_TEMPLATE = '''
import json
from pathlib import Path

_LOG_PATH = __LOG_PATH__
_REASONS = __REASONS__
_READY = __READY__


def _log(entry):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\\n")


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({
        "fn": "check_readiness",
        "repo_root": str(repo_root),
        "changed_ids": list(changed_ids) if changed_ids is not None else None,
        "model": model,
        "seed": seed,
    })
    return {
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": _READY,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [
                        {"id": "AC-FOO-001", "covers": "R-FOO-001",
                         "kind": "compiled", "result": "pass"}
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 0.9,
                    "overall": "pass",
                },
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": list(_REASONS),
    }


def last_requirement_failures(component_id, repo_root):
    _log({"fn": "last_requirement_failures", "component_id": component_id})
    return []
'''


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def to_plain(value):
    if isinstance(value, dict):
        return {k: to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_plain(dataclasses.asdict(value))
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        return to_plain(value.to_dict())
    if hasattr(value, "__dict__") and not isinstance(value, (str, int, float, bool)):
        return to_plain({k: v for k, v in vars(value).items() if not k.startswith("_")})
    return value


def normalize(value):
    return json.loads(json.dumps(to_plain(value)))


def build_repo(tmp_path, reasons, ready):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = (
        FAKE_TRACKER_TEMPLATE
        .replace("__LOG_PATH__", repr(str(log_path)))
        .replace("__REASONS__", repr(list(reasons)))
        .replace("__READY__", repr(bool(ready)))
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            }
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    verification = repo_root / "verification"
    verification.mkdir()
    (verification / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return repo_root, log_path


def read_log(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def extract_snapshot_json(html):
    start = html.find(SNAPSHOT_OPEN)
    assert start != -1, "tracker-snapshot script element not found"
    assert html.count(SNAPSHOT_OPEN) == 1, "tracker-snapshot inlined more than once"
    body_start = start + len(SNAPSHOT_OPEN)
    # A browser ends the script element at the first "</script" it sees.
    end = html.lower().find("</script", body_start)
    assert end != -1, "tracker-snapshot element is never closed"
    return json.loads(html[body_start:end])


def strip_script_and_style_bodies(html):
    html = re.sub(
        r"(<script\b[^>]*>).*?(</script\s*>)", r"\1\2", html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(
        r"(<style\b[^>]*>).*?(</style\s*>)", r"\1\2", html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return html


def assert_no_external_refs(html):
    markup = strip_script_and_style_bodies(html)
    for tag in re.findall(r"<[a-zA-Z][^>]*>", markup):
        for m in re.finditer(
            r"\s(src|href)\s*=\s*(\"([^\"]*)\"|'([^']*)'|([^\s>]+))",
            tag, flags=re.IGNORECASE,
        ):
            value = next(g for g in (m.group(3), m.group(4), m.group(5)) if g is not None)
            value = value.strip()
            assert value == "" or value.startswith("#") or value.lower().startswith("data:"), (
                f"external resource reference {m.group(1)}={value!r} in tag {tag!r}"
            )


def snapshot_node_ids(snapshot):
    return [field(n, "id") for n in field(snapshot, "nodes")]


def test_ac_ui_001_single_self_contained_index_html(tmp_path):
    repo_root, log_path = build_repo(tmp_path, reasons=[], ready=True)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    calls = [c for c in read_log(log_path) if c["fn"] == "check_readiness"]
    assert len(calls) == 1, f"expected the faked check_readiness to be called once, got {calls}"

    files = sorted(p.relative_to(out_dir) for p in out_dir.rglob("*"))
    assert files == [Path("index.html")], f"out_dir contents: {files}"

    html = (out_dir / "index.html").read_text(encoding="utf-8")

    assert "comp-foo" in snapshot_node_ids(snapshot)

    inlined = extract_snapshot_json(html)
    assert inlined == normalize(snapshot)

    assert re.search(r"<[a-zA-Z][a-zA-Z0-9]*\b[^>]*\sdata-node-id=\"comp-foo\"", html), (
        'no node element with data-node-id="comp-foo"'
    )

    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "WebAssembly" not in html
    assert_no_external_refs(html)


def test_ac_ui_001_script_close_in_reasons_is_escaped(tmp_path):
    reasons = ["comp-foo: </script><script>alert(1)</script> injected reason"]
    repo_root, log_path = build_repo(tmp_path, reasons=reasons, ready=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    inlined = extract_snapshot_json(html)
    expected = normalize(snapshot)
    assert inlined == expected
    assert list(field(snapshot, "not_ready_reasons")) == reasons