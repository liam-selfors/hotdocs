# hotdocs-criterion: sha256:ea8336566baa75d3d5a417aea9c543ec1a757710e56c164daaf281283980a9aa
"""CS-MERGE-VISIBILITY-001: merge status is visible and recoverable.

Three components are touched by one change. Two generate and verify and
one fails verification. A provenance-tracker query then shows two ready
and one not ready, with a reason. After a spec edit to the failing
component and a second generate of it alone, a second query shows the
two unchanged components still ready (provenance hits, not regenerated)
alongside the third's fresh, passing result. Neither query needs the
first run's CLI output.
"""

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import provenance_tracker
import provenance_tracker_ui


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENTS = {
    "comp-alpha": ["R-ALPHA-001"],
    "comp-beta": ["R-BETA-001"],
    "comp-gamma": ["R-GAMMA-001", "R-GAMMA-002"],
}


def _slug(cid):
    return cid[len("comp-"):]


def _spec_key(repo_root, cid):
    d = repo_root / "specs" / "components" / _slug(cid)
    h = hashlib.sha256()
    for p in sorted(d.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(d)).encode("utf-8"))
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return "sha256:" + h.hexdigest()


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    for cid, rids in COMPONENTS.items():
        slug = _slug(cid)
        base = repo_root / "specs" / "components" / slug
        _write(
            base / "component.md",
            "---\n"
            "id: " + cid + "\n"
            "title: Component " + slug + "\n"
            "status: draft\n"
            "owners: [pipeline-team]\n"
            "depends_on: []\n"
            "---\n\n"
            "# Component " + slug + "\n\n"
            "## Purpose\n\nA fixture component.\n",
        )
        _write(base / "constraints.md", "# Constraints\n\nNone.\n")
        _write(base / "interface" / "library.md", "# Library\n\n```\nrun() -> None\n```\n")
        for i, rid in enumerate(rids, start=1):
            _write(
                base / "requirements" / (rid + ".md"),
                "# " + rid + "\n\nThe component MUST do thing " + str(i) + ".\n",
            )
            ac = "AC-" + rid[len("R-"):]
            _write(
                base / "acceptance" / (ac + ".md"),
                "# " + ac + "\n\nCovers: " + rid + "\nKind: compiled\n\n"
                "Given a setup, when run, then thing " + str(i) + " holds.\n",
            )
    graph = {
        "nodes": [{"id": cid, "kind": "component"} for cid in sorted(COMPONENTS)],
        "edges": [],
    }
    _write(repo_root / "verification" / "corpus-graph.json", json.dumps(graph, indent=2))


FAKE_PROVENANCE_CHECKER_BODY = (
    "import hashlib\n"
    "import json\n"
    "\n"
    "def _log(name, cid):\n"
    "    with open(LOG, 'a', encoding='utf-8') as f:\n"
    "        f.write(name + ' ' + str(cid) + '\\n')\n"
    "\n"
    "def _cid(args, kwargs):\n"
    "    for v in list(args) + list(kwargs.values()):\n"
    "        if isinstance(v, str) and v.startswith('comp-'):\n"
    "            return v\n"
    "        if isinstance(v, dict) and isinstance(v.get('component_id'), str):\n"
    "            return v['component_id']\n"
    "        c = getattr(v, 'component_id', None)\n"
    "        if isinstance(c, str):\n"
    "            return c\n"
    "    return None\n"
    "\n"
    "def _key(cid):\n"
    "    d = REPO / 'specs' / 'components' / cid[len('comp-'):]\n"
    "    h = hashlib.sha256()\n"
    "    for p in sorted(d.rglob('*')):\n"
    "        if p.is_file():\n"
    "            h.update(str(p.relative_to(d)).encode('utf-8'))\n"
    "            h.update(b'\\0')\n"
    "            h.update(p.read_bytes())\n"
    "            h.update(b'\\0')\n"
    "    return 'sha256:' + h.hexdigest()\n"
    "\n"
    "def _miss(cid, key):\n"
    "    return {'component_id': cid, 'key': key, 'hit': False, 'provenance': None,\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def current_sealed_key(*args, **kwargs):\n"
    "    _log('current_sealed_key', _cid(args, kwargs))\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(*args, **kwargs):\n"
    "    cid = _cid(args, kwargs)\n"
    "    _log('current_provenance_key', cid)\n"
    "    return _key(cid)\n"
    "\n"
    "def check_provenance(*args, **kwargs):\n"
    "    cid = _cid(args, kwargs)\n"
    "    _log('check_provenance', cid)\n"
    "    key = _key(cid)\n"
    "    rec = REPO / '.fake-provenance' / cid[len('comp-'):] / (key[len('sha256:'):] + '.json')\n"
    "    if not rec.is_file():\n"
    "        return _miss(cid, key)\n"
    "    data = json.loads(rec.read_text(encoding='utf-8'))\n"
    "    return {'component_id': cid, 'key': key, 'hit': True,\n"
    "            'provenance': data['provenance'],\n"
    "            'verification_report': data['verification_report'],\n"
    "            'license_scan': {'blocked': False, 'findings': []},\n"
    "            'secret_scan': {'flagged': False, 'findings': []}}\n"
    "\n"
    "def check_sealed_provenance(*args, **kwargs):\n"
    "    cid = _cid(args, kwargs)\n"
    "    _log('check_sealed_provenance', cid)\n"
    "    return _miss(cid, None)\n"
)

FAKE_CAPABILITY_VERIFIER_BODY = (
    "def _log(name, cap):\n"
    "    with open(LOG, 'a', encoding='utf-8') as f:\n"
    "        f.write(name + ' ' + str(cap) + '\\n')\n"
    "\n"
    "def _cap(args, kwargs):\n"
    "    for v in list(args) + list(kwargs.values()):\n"
    "        if isinstance(v, str) and v.startswith('P-'):\n"
    "            return v\n"
    "    return None\n"
    "\n"
    "def _result(cap):\n"
    "    return {'capability_id': cap, 'hit': True, 'key': None,\n"
    "            'capability_scenario_report': {}, 'model_call_error': None}\n"
    "\n"
    "def check_capability_provenance(*args, **kwargs):\n"
    "    cap = _cap(args, kwargs)\n"
    "    _log('check_capability_provenance', cap)\n"
    "    return _result(cap)\n"
    "\n"
    "def run_capability_gates(*args, **kwargs):\n"
    "    cap = _cap(args, kwargs)\n"
    "    _log('run_capability_gates', cap)\n"
    "    return _result(cap)\n"
)


def _install_fakes(repo_root, log_path):
    header = (
        "from pathlib import Path\n"
        "REPO = Path(" + repr(str(repo_root)) + ")\n"
        "LOG = Path(" + repr(str(log_path)) + ")\n"
    )
    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        header + FAKE_PROVENANCE_CHECKER_BODY,
    )
    _write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        header + FAKE_CAPABILITY_VERIFIER_BODY,
    )


def _generate(repo_root, cid, failing):
    """Simulate one `hotdocs generate <cid>` attempt and its recording."""
    rids = COMPONENTS[cid]
    key = _spec_key(repo_root, cid)
    requirement_results = {rid: ("fail" if rid in failing else "pass") for rid in rids}
    criteria = []
    for rid in rids:
        crit = {"covers": rid, "result": requirement_results[rid]}
        if requirement_results[rid] == "fail":
            crit["failure_origin"] = "implementation"
        criteria.append(crit)
    overall = "fail" if failing else "pass"
    verification = {
        "component_id": cid,
        "overall": overall,
        "requirement_results": requirement_results,
        "criteria": criteria,
    }
    generation = {
        "component_id": cid,
        "files": ["gen/" + _slug(cid) + "/" + _slug(cid).replace("-", "_") + ".py"],
        "model": "anthropic:claude-sonnet-5",
        "model_call_error": None,
    }
    if overall == "pass":
        _write(
            repo_root / ".fake-provenance" / _slug(cid) / (key[len("sha256:"):] + ".json"),
            json.dumps(
                {
                    "provenance": {"component_id": cid, "spec_bundle_hash": key},
                    "verification_report": verification,
                }
            ),
        )
    provenance_tracker.write_attempt_record(cid, generation, verification, key, repo_root)
    return key


def _attempt_count(repo_root, cid):
    d = repo_root / ".hotdocs" / "attempts" / cid
    return len(list(d.glob("*.json"))) if d.is_dir() else 0


def _log_lines(log_path):
    if not log_path.is_file():
        return []
    return [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _overall(result):
    vr = field(result, "verification_report")
    return None if vr is None else field(vr, "overall")


def _node_map(snapshot):
    return {field(n, "id"): n for n in field(snapshot, "nodes")}


def test_cs_merge_visibility_001(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake-calls.log"
    _build_corpus(repo_root)
    _install_fakes(repo_root, log_path)

    # Step 1: one change, three components; two verify, one fails.
    _generate(repo_root, "comp-alpha", failing=[])
    _generate(repo_root, "comp-beta", failing=[])
    gamma_key_1 = _generate(repo_root, "comp-gamma", failing=["R-GAMMA-002"])

    # First query, from durable state alone (no CLI output kept).
    report1 = provenance_tracker.check_readiness(repo_root)
    assert field(report1, "ready") is False
    comps1 = field(report1, "components")
    assert set(comps1) == set(COMPONENTS)
    for cid in ("comp-alpha", "comp-beta"):
        assert field(comps1[cid], "hit") is True
        assert _overall(comps1[cid]) == "pass"
    assert field(comps1["comp-gamma"], "hit") is False

    reasons1 = list(field(report1, "not_ready_reasons"))
    assert len(reasons1) == 1, reasons1
    assert "comp-gamma" in reasons1[0]
    assert not any("comp-alpha" in r or "comp-beta" in r for r in reasons1)

    # Why not ready: the failing requirement is recoverable from records.
    assert list(provenance_tracker.last_requirement_failures("comp-gamma", repo_root)) == ["R-GAMMA-002"]
    assert list(provenance_tracker.last_requirement_failures("comp-alpha", repo_root)) == []

    snap1 = provenance_tracker_ui.render_tracker_ui(tmp_path / "ui1", repo_root)
    assert (tmp_path / "ui1" / "index.html").is_file()
    nodes1 = _node_map(snap1)
    assert field(nodes1["comp-alpha"], "status") == "passing"
    assert field(nodes1["comp-beta"], "status") == "passing"
    assert field(nodes1["comp-gamma"], "status") == "missing"
    assert list(field(nodes1["comp-gamma"], "retry_feedback")) == ["R-GAMMA-002"]

    alpha_before = json.dumps(comps1["comp-alpha"], sort_keys=True, default=str)
    beta_before = json.dumps(comps1["comp-beta"], sort_keys=True, default=str)
    lines_after_q1 = len(_log_lines(log_path))

    # Step 2: spec edit to the failing component, regenerate only it.
    req = repo_root / "specs" / "components" / "gamma" / "requirements" / "R-GAMMA-002.md"
    req.write_text(
        "# R-GAMMA-002\n\nThe component MUST do thing 2, clarified.\n", encoding="utf-8"
    )
    time.sleep(1.1)  # keep attempt ids strictly ordered by timestamp
    gamma_key_2 = _generate(repo_root, "comp-gamma", failing=[])
    assert gamma_key_2 != gamma_key_1

    report2 = provenance_tracker.check_readiness(repo_root)
    assert field(report2, "ready") is True
    assert list(field(report2, "not_ready_reasons")) == []
    comps2 = field(report2, "components")
    assert set(comps2) == set(COMPONENTS)

    # Unchanged components: still provenance hits, identical results.
    for cid, before in (("comp-alpha", alpha_before), ("comp-beta", beta_before)):
        assert field(comps2[cid], "hit") is True
        assert _overall(comps2[cid]) == "pass"
        assert json.dumps(comps2[cid], sort_keys=True, default=str) == before
        # Not regenerated: still exactly the one attempt from step 1.
        assert _attempt_count(repo_root, cid) == 1

    # The third component's fresh result.
    assert field(comps2["comp-gamma"], "hit") is True
    assert _overall(comps2["comp-gamma"]) == "pass"
    assert _attempt_count(repo_root, "comp-gamma") == 2
    assert list(provenance_tracker.last_requirement_failures("comp-gamma", repo_root)) == []

    # The second query read provenance for every component, live.
    new_lines = _log_lines(log_path)[lines_after_q1:]
    for cid in COMPONENTS:
        assert ("check_provenance " + cid) in new_lines, new_lines

    snap2 = provenance_tracker_ui.render_tracker_ui(tmp_path / "ui2", repo_root)
    nodes2 = _node_map(snap2)
    for cid in COMPONENTS:
        assert field(nodes2[cid], "status") == "passing"
    assert field(snap2, "ready") is True