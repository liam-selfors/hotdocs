# hotdocs-criterion: sha256:3bd6a51342884adcb869c0ddaeb591fc8f4b4d62fee809c82440214f68f3275f
import dataclasses
import json
import re
from pathlib import Path

import provenance_tracker_ui


SNAPSHOT_OPEN = '<script type="application/json" id="tracker-snapshot">'


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def normalize(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return normalize(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    return value


def snapshot_as_plain(snapshot):
    if isinstance(snapshot, dict) or dataclasses.is_dataclass(snapshot):
        return normalize(snapshot)
    names = ["scope", "changed_ids", "ready", "not_ready_reasons", "nodes", "edges"]
    return normalize({n: field(snapshot, n) for n in names})


def verification_report(overall):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
             "result": "pass" if overall == "pass" else "fail"},
        ],
        "requirement_results": {"R-FOO-001": "pass" if overall == "pass" else "fail"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "0" * 64,
                    "versions": {"python": "3.12.4"}, "lockfile_sha256": None}],
        "overall": overall,
    }


def provenance_check_result(overall):
    return {
        "hit": True,
        "reason": None,
        "verification_report": verification_report(overall),
        "license_scan": {"blocked": False, "findings": []},
        "secret_scan": {"flagged": False, "findings": []},
    }


def write_fake_tracker(repo_root, report):
    d = repo_root / "gen" / "provenance-tracker"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import copy\n"
        "\n"
        "_REPORT = " + repr(report) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    r = copy.deepcopy(_REPORT)\n"
        "    r['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return r\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise NotImplementedError('not used by this test')\n"
    )
    (d / "provenance_tracker.py").write_text(src, encoding="utf-8")


def write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": verification_report("pass"),
                "provenance": {"component_id": "comp-foo"},
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {"component.md": "---\nid: comp-foo\n---\n"},
            }
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    v = repo_root / "verification"
    v.mkdir(parents=True, exist_ok=True)
    (v / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def extract_snapshot_json(html):
    assert html.count(SNAPSHOT_OPEN) == 1
    start = html.index(SNAPSHOT_OPEN) + len(SNAPSHOT_OPEN)
    end = html.index("</script>", start)
    return json.loads(html[start:end])


def build(tmp_path, report):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_fake_tracker(repo_root, report)
    write_corpus_graph(repo_root)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)
    return out_dir, snapshot


def is_external(url):
    u = url.strip()
    if u == "" or u.startswith("#") or u.lower().startswith("data:"):
        return False
    return True


def test_single_self_contained_index_html(tmp_path):
    report = {
        "scope": "whole-corpus",
        "ready": True,
        "components": {"comp-foo": provenance_check_result("pass")},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    out_dir, snapshot = build(tmp_path, report)

    files = [p.name for p in out_dir.iterdir()]
    assert files == ["index.html"]
    index = out_dir / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")

    assert extract_snapshot_json(html) == snapshot_as_plain(snapshot)

    assert re.search(r'<[A-Za-z][^>]*\bdata-node-id="comp-foo"[^>]*>', html)

    app_js_path = Path(provenance_tracker_ui.__file__).parent / "static" / "app.js"
    app_js = app_js_path.read_text(encoding="utf-8")
    assert app_js in html
    rest = html.replace(app_js, "", 1)

    assert "fetch(" not in rest
    assert "XMLHttpRequest" not in rest
    assert "WebAssembly" not in rest

    for m in re.finditer(r'\b(src|href)\s*=\s*("([^"]*)"|\'([^\']*)\'|([^\s>]+))', rest, re.IGNORECASE):
        url = m.group(3) if m.group(3) is not None else (
            m.group(4) if m.group(4) is not None else m.group(5)
        )
        assert not is_external(url), "external reference: " + m.group(0)


def test_snapshot_survives_script_close_in_reasons(tmp_path):
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {"comp-foo": provenance_check_result("fail")},
        "capabilities": {},
        "not_ready_reasons": ["comp-foo: verification failed </script><b>x</b> — run hotdocs generate comp-foo"],
    }
    out_dir, snapshot = build(tmp_path, report)

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    parsed = extract_snapshot_json(html)
    plain = snapshot_as_plain(snapshot)
    assert parsed == plain
    assert any("</script>" in r for r in parsed["not_ready_reasons"])