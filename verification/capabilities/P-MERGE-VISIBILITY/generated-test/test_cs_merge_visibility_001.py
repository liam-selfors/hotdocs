# hotdocs-criterion: sha256:cbda39f096a23517db4118670dbd83cf6fade8487a98c4ae2d0477f6aebf99fc
import hashlib
import json
from pathlib import Path

import provenance_tracker
import provenance_tracker_ui


COMPONENTS = ["comp-a", "comp-b", "comp-c"]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def spec_key(repo_root, component_id):
    slug = component_id[len("comp-"):]
    d = Path(repo_root) / "specs" / "components" / slug
    h = hashlib.sha256()
    for p in sorted(d.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(d)).encode())
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return "sha256:" + h.hexdigest()


CHECKER_BODY = (
    "\n"
    "def _log(name, cid):\n"
    "    with open(LOG, 'a') as fh:\n"
    "        fh.write(name + ' ' + str(cid) + '\\n')\n"
    "\n"
    "def _cid(args, kwargs):\n"
    "    for v in list(args) + list(kwargs.values()):\n"
    "        if isinstance(v, str) and v.startswith('comp-'):\n"
    "            return v\n"
    "    return None\n"
    "\n"
    "def _key_arg(args, kwargs):\n"
    "    for v in list(args) + list(kwargs.values()):\n"
    "        if isinstance(v, str) and v.startswith('sha256:'):\n"
    "            return v\n"
    "    return None\n"
    "\n"
    "def _spec_key(cid):\n"
    "    slug = cid[len('comp-'):]\n"
    "    d = REPO_ROOT / 'specs' / 'components' / slug\n"
    "    h = hashlib.sha256()\n"
    "    for p in sorted(d.rglob('*')):\n"
    "        if p.is_file():\n"
    "            h.update(str(p.relative_to(d)).encode())\n"
    "            h.update(b'\\0')\n"
    "            h.update(p.read_bytes())\n"
    "            h.update(b'\\0')\n"
    "    return 'sha256:' + h.hexdigest()\n"
    "\n"
    "def _state():\n"
    "    if STATE.exists():\n"
    "        return json.loads(STATE.read_text())\n"
    "    return {}\n"
    "\n"
    "def _miss(cid, key):\n"
    "    return {'component_id': cid, 'hit': False, 'provenance_key': key,\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'reason': 'no provenance for current spec state'}\n"
    "\n"
    "def current_sealed_key(*args, **kwargs):\n"
    "    _log('current_sealed_key', _cid(args, kwargs))\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(*args, **kwargs):\n"
    "    cid = _cid(args, kwargs)\n"
    "    _log('current_provenance_key', cid)\n"
    "    return _spec_key(cid)\n"
    "\n"
    "def check_provenance(*args, **kwargs):\n"
    "    cid = _cid(args, kwargs)\n"
    "    key = _key_arg(args, kwargs)\n"
    "    if key is None and cid is not None:\n"
    "        key = _spec_key(cid)\n"
    "    entry = _state().get(key)\n"
    "    if cid is None and entry is not None:\n"
    "        cid = entry['component_id']\n"
    "    _log('check_provenance', cid)\n"
    "    if entry is None:\n"
    "        return _miss(cid, key)\n"
    "    scans = {'license_scan': {'blocked': False}, 'secret_scan': {'flagged': False}}\n"
    "    report = {'overall': entry['overall'],\n"
    "              'requirement_results': entry['requirement_results'],\n"
    "              'license_scan': {'blocked': False}, 'secret_scan': {'flagged': False}}\n"
    "    result = {'component_id': cid, 'hit': True, 'provenance_key': key,\n"
    "              'verification_report': report,\n"
    "              'reason': None if entry['overall'] == 'pass' else 'verification failed'}\n"
    "    result.update(scans)\n"
    "    return result\n"
    "\n"
    "def check_sealed_provenance(*args, **kwargs):\n"
    "    cid = _cid(args, kwargs)\n"
    "    _log('check_sealed_provenance', cid)\n"
    "    return _miss(cid, None)\n"
)

CSV_BODY = (
    "\n"
    "def _log(name):\n"
    "    with open(LOG, 'a') as fh:\n"
    "        fh.write(name + '\\n')\n"
    "\n"
    "def check_capability_provenance(*args, **kwargs):\n"
    "    _log('check_capability_provenance')\n"
    "    return {'hit': False, 'capability_scenario_report': {}}\n"
    "\n"
    "def run_capability_gates(*args, **kwargs):\n"
    "    _log('run_capability_gates')\n"
    "    return {'hit': False, 'capability_scenario_report': {}}\n"
)


def write_component(root, component_id):
    slug = component_id[len("comp-"):]
    upper = slug.upper()
    d = root / "specs" / "components" / slug
    (d / "requirements").mkdir(parents=True)
    (d / "acceptance").mkdir(parents=True)
    (d / "interface").mkdir(parents=True)
    (d / "component.md").write_text(
        "---\n"
        "id: " + component_id + "\n"
        "title: Component " + upper + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n\n"
        "# Component " + upper + "\n\nA fixture component.\n"
    )
    (d / "requirements" / ("R-" + upper + "-001.md")).write_text(
        "# R-" + upper + "-001\n\nThe component MUST do its one thing.\n"
    )
    (d / "acceptance" / ("AC-" + upper + "-001.md")).write_text(
        "# AC-" + upper + "-001\n\nCovers: R-" + upper + "-001\n\n"
        "Given input When called Then it does its one thing.\n"
    )
    (d / "interface" / "library.md").write_text("# Library\n\n`do_thing() -> None`\n")
    (d / "constraints.md").write_text("# Constraints\n\nNone.\n")
    gen_dir = root / "gen" / slug
    gen_dir.mkdir(parents=True)
    (gen_dir / (slug.replace("-", "_") + ".py")).write_text("def do_thing():\n    return None\n")


def build_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for cid in COMPONENTS:
        write_component(root, cid)
    (root / "verification").mkdir()
    graph = {
        "nodes": [{"id": cid, "kind": "component"} for cid in COMPONENTS],
        "edges": [],
    }
    (root / "verification" / "corpus-graph.json").write_text(json.dumps(graph))

    log = tmp_path / "fake-calls.log"
    log.write_text("")
    state = root / ".fake-provenance-state.json"

    checker_dir = root / "gen" / "provenance-checker"
    checker_dir.mkdir(parents=True)
    (checker_dir / "provenance_checker.py").write_text(
        "import hashlib\n"
        "import json\n"
        "from pathlib import Path\n\n"
        "REPO_ROOT = Path(" + repr(str(root)) + ")\n"
        "LOG = Path(" + repr(str(log)) + ")\n"
        "STATE = Path(" + repr(str(state)) + ")\n"
        + CHECKER_BODY
    )

    csv_dir = root / "gen" / "capability-scenario-verifier"
    csv_dir.mkdir(parents=True)
    (csv_dir / "capability_scenario_verifier.py").write_text(
        "from pathlib import Path\n\n"
        "LOG = Path(" + repr(str(log)) + ")\n"
        + CSV_BODY
    )
    return root, log, state


def simulate_generate(root, state_path, component_id, passed, timestamp_tag):
    """What `hotdocs generate` leaves behind: provenance for the current spec
    state, and one AttemptRecord written via write_attempt_record."""
    upper = component_id[len("comp-"):].upper()
    rid = "R-" + upper + "-001"
    key = spec_key(root, component_id)
    overall = "pass" if passed else "fail"
    requirement_results = {rid: overall}

    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    state[key] = {
        "component_id": component_id,
        "overall": overall,
        "requirement_results": requirement_results,
    }
    state_path.write_text(json.dumps(state))

    generation_result = {
        "component_id": component_id,
        "model": "anthropic:claude-sonnet-5",
        "seed": 0,
        "files": ["gen/" + component_id[len("comp-"):] + "/module.py"],
        "model_call_error": None,
        "tag": timestamp_tag,
    }
    verification_report = {
        "component_id": component_id,
        "overall": overall,
        "requirement_results": requirement_results,
        "criteria": [
            {
                "criterion_id": "AC-" + upper + "-001",
                "covers": rid,
                "result": overall,
                **({} if passed else {"failure_origin": "implementation"}),
            }
        ],
    }
    provenance_tracker.write_attempt_record(
        component_id, generation_result, verification_report, key, root
    )
    return key


def attempt_files(root, component_id):
    d = root / ".hotdocs" / "attempts" / component_id
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.json"))


def run_main(argv):
    try:
        rc = provenance_tracker.main(argv)
    except SystemExit as exc:
        rc = exc.code
    return 0 if rc is None else rc


def is_passing_hit(result):
    if not field(result, "hit"):
        return False
    report = field(result, "verification_report")
    return field(report, "overall") == "pass"


def node_by_id(snapshot):
    return {field(n, "id"): n for n in field(snapshot, "nodes")}


def test_cs_merge_visibility_001(tmp_path, capsys):
    root, log, state_path = build_repo(tmp_path)

    # Step 1: the change touches three components; a and b verify, c fails.
    keys_step1 = {}
    keys_step1["comp-a"] = simulate_generate(root, state_path, "comp-a", True, "1")
    keys_step1["comp-b"] = simulate_generate(root, state_path, "comp-b", True, "1")
    keys_step1["comp-c"] = simulate_generate(root, state_path, "comp-c", False, "1")
    for cid in COMPONENTS:
        assert len(attempt_files(root, cid)) == 1

    # First query: a live, durable query, no CLI output from step 1 needed.
    log.write_text("")
    report1 = provenance_tracker.check_readiness(root)
    comps1 = field(report1, "components")
    assert set(comps1) == set(COMPONENTS)
    assert field(report1, "ready") is False
    assert is_passing_hit(comps1["comp-a"])
    assert is_passing_hit(comps1["comp-b"])
    assert not is_passing_hit(comps1["comp-c"])
    reasons1 = list(field(report1, "not_ready_reasons"))
    assert any("comp-c" in r for r in reasons1), reasons1
    assert not any("comp-a" in r or "comp-b" in r for r in reasons1), reasons1
    calls1 = log.read_text()
    for cid in COMPONENTS:
        assert ("check_provenance " + cid) in calls1

    # The failing component's reason is recoverable from durable records.
    assert provenance_tracker.last_requirement_failures("comp-c", root) == ["R-C-001"]
    assert provenance_tracker.last_requirement_failures("comp-a", root) == []

    # The same answer through the CLI query.
    capsys.readouterr()
    assert run_main(["verify", "--repo-root", str(root), "--format", "json"]) == 1
    cli1 = json.loads(capsys.readouterr().out)
    assert cli1["ready"] is False
    assert any("comp-c" in r for r in cli1["not_ready_reasons"])

    # And through the visible tracker view.
    snap1 = provenance_tracker_ui.render_tracker_ui(tmp_path / "ui1", root)
    nodes1 = node_by_id(snap1)
    assert field(nodes1["comp-a"], "status") == "passing"
    assert field(nodes1["comp-b"], "status") == "passing"
    assert field(nodes1["comp-c"], "status") == "failing"
    assert len(field(nodes1["comp-c"], "attempts")) == 1
    assert list(field(nodes1["comp-c"], "retry_feedback")) == ["R-C-001"]
    assert (tmp_path / "ui1" / "index.html").is_file()

    # Step 2: edit the failing component's spec and regenerate only it.
    req_c = root / "specs" / "components" / "c" / "requirements" / "R-C-001.md"
    req_c.write_text("# R-C-001\n\nThe component MUST do its one thing, clarified.\n")
    assert spec_key(root, "comp-c") != keys_step1["comp-c"]
    key_c2 = simulate_generate(root, state_path, "comp-c", True, "2")

    # Second query.
    log.write_text("")
    report2 = provenance_tracker.check_readiness(root)
    comps2 = field(report2, "components")
    assert set(comps2) == set(COMPONENTS)
    assert field(report2, "ready") is True
    assert list(field(report2, "not_ready_reasons")) == []

    # Unchanged components: still ready, provenance hits on the very same key,
    # and never regenerated (no new attempt written for them).
    for cid in ("comp-a", "comp-b"):
        assert is_passing_hit(comps2[cid])
        assert field(comps2[cid], "provenance_key") == keys_step1[cid]
        assert len(attempt_files(root, cid)) == 1
    # The third: its fresh result.
    assert is_passing_hit(comps2["comp-c"])
    assert field(comps2["comp-c"], "provenance_key") == key_c2
    assert len(attempt_files(root, "comp-c")) == 2
    assert provenance_tracker.last_requirement_failures("comp-c", root) == []

    calls2 = log.read_text()
    for cid in COMPONENTS:
        assert ("check_provenance " + cid) in calls2

    capsys.readouterr()
    assert run_main(["verify", "--repo-root", str(root), "--format", "json"]) == 0
    cli2 = json.loads(capsys.readouterr().out)
    assert cli2["ready"] is True

    snap2 = provenance_tracker_ui.render_tracker_ui(tmp_path / "ui2", root)
    nodes2 = node_by_id(snap2)
    for cid in COMPONENTS:
        assert field(nodes2[cid], "status") == "passing"
    assert field(snap2, "ready") is True