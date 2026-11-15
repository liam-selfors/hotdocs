import dataclasses
import json
import re
from pathlib import Path

import provenance_tracker_ui


SNAPSHOT_RE = re.compile(
    r'<script type="application/json" id="tracker-snapshot">(.*?)</script>',
    re.DOTALL,
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def to_plain(value):
    """Convert a returned TrackerSnapshot (dict or object) to plain JSON data."""
    if isinstance(value, dict):
        plain = {k: to_plain(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        plain = [to_plain(v) for v in value]
    elif hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        plain = to_plain(value.to_dict())
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        plain = to_plain(dataclasses.asdict(value))
    elif value is None or isinstance(value, (str, int, float, bool)):
        plain = value
    else:
        plain = to_plain(vars(value))
    return plain


def normalize(value):
    return json.loads(json.dumps(to_plain(value)))


FAKE_TEMPLATE = '''
import copy
import json
from pathlib import Path

_REPORT = json.loads({report_json!r})
_FEEDBACK = json.loads({feedback_json!r})
_LOG = Path({log_path!r})


def _log(record):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({{"fn": "check_readiness", "repo_root": str(repo_root),
          "changed_ids": changed_ids, "model": model, "seed": seed}})
    report = copy.deepcopy(_REPORT)
    report["scope"] = "blast-radius" if changed_ids is not None else "whole-corpus"
    return report


def last_requirement_failures(component_id, repo_root):
    _log({{"fn": "last_requirement_failures", "component_id": component_id}})
    return list(_FEEDBACK.get(component_id, []))


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    raise NotImplementedError("not used by this test")
'''


def _verification_report(overall):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": overall,
            }
        ],
        "requirement_results": {"R-FOO-001": overall},
        "interface_drift": False,
        "mutation_score": None,
        "overall": overall,
    }


def _make_repo(tmp_path, name, report, feedback):
    repo_root = tmp_path / name / "repo"
    log_path = tmp_path / name / "invocations.log"
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        FAKE_TEMPLATE.format(
            report_json=json.dumps(report),
            feedback_json=json.dumps(feedback),
            log_path=str(log_path),
        ),
        encoding="utf-8",
    )
    graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
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
    (repo_root / "verification").mkdir(parents=True)
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    out_dir = tmp_path / name / "out"
    return repo_root, out_dir, log_path


def _read_log(log_path):
    assert log_path.exists(), "faked provenance-tracker was never invoked"
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _strip_code_bodies(html):
    html = re.sub(
        r"(<script\b[^>]*>).*?(</script>)", r"\1\2", html, flags=re.DOTALL | re.IGNORECASE
    )
    html = re.sub(
        r"(<style\b[^>]*>).*?(</style>)", r"\1\2", html, flags=re.DOTALL | re.IGNORECASE
    )
    return html


def _is_local_reference(target):
    t = target.strip().lower()
    return (
        t == ""
        or t.startswith("#")
        or t.startswith("data:")
        or t.startswith("javascript:")
        or t.startswith("about:")
    )


def _external_refs(html):
    markup = _strip_code_bodies(html)
    bad = []
    for tag in re.findall(r"<[a-zA-Z][^>]*>", markup):
        for m in re.finditer(
            r"""\b(src|href)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
            tag,
            flags=re.IGNORECASE,
        ):
            target = next(g for g in m.groups()[1:] if g is not None)
            if not _is_local_reference(target):
                bad.append(tag)
    return bad


def _extract_snapshot_json(html):
    m = SNAPSHOT_RE.search(html)
    assert m is not None, "no tracker-snapshot script element found"
    return m.group(1)


def test_single_self_contained_index_html(tmp_path):
    report = {
        "scope": "whole-corpus",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report("pass"),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }
    repo_root, out_dir, log_path = _make_repo(tmp_path, "s1", report, {})

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    calls = [c for c in _read_log(log_path) if c["fn"] == "check_readiness"]
    assert len(calls) == 1

    entries = sorted(p.name for p in Path(out_dir).iterdir())
    assert entries == ["index.html"]
    index = Path(out_dir) / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")

    assert len(SNAPSHOT_RE.findall(html)) == 1
    parsed = json.loads(_extract_snapshot_json(html))
    expected = normalize(snapshot)
    assert parsed == expected

    node_ids = [field(n, "id") for n in field(snapshot, "nodes")]
    assert "comp-foo" in node_ids

    markup = SNAPSHOT_RE.sub("", html)
    assert re.search(
        r'<[a-zA-Z][a-zA-Z0-9-]*\b[^>]*\bdata-node-id="comp-foo"', markup
    ), "no node element with data-node-id=\"comp-foo\""

    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "WebAssembly" not in html

    bad = _external_refs(html)
    assert bad == [], f"external src/href references found: {bad}"


def test_script_close_in_reason_does_not_break_snapshot(tmp_path):
    reason = (
        "comp-foo: verification failed </script><script>alert(1)</script> "
        "— run hotdocs generate comp-foo"
    )
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report("fail"),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [reason],
    }
    repo_root, out_dir, log_path = _make_repo(
        tmp_path, "s2", report, {"comp-foo": ["R-FOO-001"]}
    )

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    calls = [c for c in _read_log(log_path) if c["fn"] == "check_readiness"]
    assert len(calls) == 1

    index = Path(out_dir) / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")

    raw = _extract_snapshot_json(html)
    parsed = json.loads(raw)
    expected = normalize(snapshot)
    assert parsed == expected
    assert reason in parsed["not_ready_reasons"]
    assert "</" not in raw