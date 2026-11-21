# hotdocs-criterion: sha256:ea8336566baa75d3d5a417aea9c543ec1a757710e56c164daaf281283980a9aa
import importlib.util
import json
import sys
import time
from pathlib import Path

import provenance_tracker
import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def maybe_field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


COMPONENTS = ["comp-alpha", "comp-beta", "comp-gamma"]


FAKE_PROVENANCE_CHECKER = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "_HERE = Path(__file__).resolve().parent\n"
    "_STATE = _HERE / 'state.json'\n"
    "_LOG = _HERE / 'calls.log'\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    with open(_LOG, 'a') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
    "\n"
    "def _state():\n"
    "    return json.loads(_STATE.read_text())\n"
    "\n"
    "\n"
    "def _component_id(args, kwargs):\n"
    "    for v in list(args) + list(kwargs.values()):\n"
    "        if isinstance(v, str) and v.startswith('comp-'):\n"
    "            return v\n"
    "    for v in list(args) + list(kwargs.values()):\n"
    "        cid = getattr(v, 'component_id', None)\n"
    "        if isinstance(cid, str):\n"
    "            return cid\n"
    "        if isinstance(v, dict) and isinstance(v.get('component_id'), str):\n"
    "            return v['component_id']\n"
    "    return None\n"
    "\n"
    "\n"
    "def _result(cid):\n"
    "    entry = _state().get(cid)\n"
    "    if entry is None or not entry.get('hit'):\n"
    "        key = entry.get('key') if entry else None\n"
    "        return {\n"
    "            'component_id': cid,\n"
    "            'hit': False,\n"
    "            'key': key,\n"
    "            'manifest': None,\n"
    "            'verification_report': None,\n"
    "            'license_scan': None,\n"
    "            'secret_scan': None,\n"
    "        }\n"
    "    return {\n"
    "        'component_id': cid,\n"
    "        'hit': True,\n"
    "        'key': entry['key'],\n"
    "        'manifest': {'component_id': cid, 'spec_bundle_hash': entry['key']},\n"
    "        'verification_report': {'overall': entry['overall']},\n"
    "        'license_scan': {'blocked': False},\n"
    "        'secret_scan': {'flagged': False},\n"
    "    }\n"
    "\n"
    "\n"
    "def current_sealed_key(*args, **kwargs):\n"
    "    cid = _component_id(args, kwargs)\n"
    "    _log('current_sealed_key ' + str(cid))\n"
    "    return None\n"
    "\n"
    "\n"
    "def current_provenance_key(*args, **kwargs):\n"
    "    cid = _component_id(args, kwargs)\n"
    "    _log('current_provenance_key ' + str(cid))\n"
    "    entry = _state().get(cid) or {}\n"
    "    return entry.get('key', 'sha256:none')\n"
    "\n"
    "\n"
    "def check_provenance(*args, **kwargs):\n"
    "    cid = _component_id(args, kwargs)\n"
    "    _log('check_provenance ' + str(cid))\n"
    "    return _result(cid)\n"
    "\n"
    "\n"
    "def check_sealed_provenance(*args, **kwargs):\n"
    "    cid = _component_id(args, kwargs)\n"
    "    _log('check_sealed_provenance ' + str(cid))\n"
    "    return _result(cid)\n"
)


FAKE_CAPABILITY_VERIFIER = (
    "from pathlib import Path\n"
    "\n"
    "_LOG = Path(__file__).resolve().parent / 'calls.log'\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    with open(_LOG, 'a') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
    "\n"
    "def check_capability_provenance(*args, **kwargs):\n"
    "    _log('check_capability_provenance')\n"
    "    return {'hit': True, 'capability_scenario_report': {}}\n"
    "\n"
    "\n"
    "def run_capability_gates(*args, **kwargs):\n"
    "    _log('run_capability_gates')\n"
    "    return {'hit': True, 'capability_scenario_report': {}}\n"
)


FAKE_GATE_RUNNER = (
    "from pathlib import Path\n"
    "\n"
    "_LOG = Path(__file__).resolve().parent / 'calls.log'\n"
    "\n"
    "\n"
    "def run_component_gates(*args, **kwargs):\n"
    "    with open(_LOG, 'a') as fh:\n"
    "        fh.write('run_component_gates\\n')\n"
    "    raise RuntimeError('component-gate-runner must never be called by a readiness query')\n"
)


def _slug(cid):
    return cid[len("comp-"):]


def _rid(cid, n=1):
    return "R-" + _slug(cid).upper() + "-" + str(n).zfill(3)


def _acid(cid, n=1):
    return "AC-" + _slug(cid).upper() + "-" + str(n).zfill(3)


def _write_component(repo_root, cid, requirement_text):
    slug = _slug(cid)
    base = repo_root / "specs" / "components" / slug
    (base / "requirements").mkdir(parents=True, exist_ok=True)
    (base / "acceptance").mkdir(parents=True, exist_ok=True)
    (base / "interface").mkdir(parents=True, exist_ok=True)
    (base / "component.md").write_text(
        "---\n"
        "id: " + cid + "\n"
        "title: " + slug.capitalize() + " Component\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + " Component\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used to exercise readiness reporting.\n"
    )
    rid = _rid(cid)
    (base / "requirements" / (rid + ".md")).write_text(
        "# " + rid + "\n\n" + requirement_text + "\n"
    )
    acid = _acid(cid)
    (base / "acceptance" / (acid + ".md")).write_text(
        "# " + acid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "Given the component is loaded\n"
        "When it is called\n"
        "Then it returns a value\n"
    )
    (base / "interface" / "library.md").write_text(
        "# Library\n\n```\nrun() -> str\n```\n"
    )


def _build_fixture(repo_root):
    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Fixture** - a small test corpus.\n"
    )
    for cid in COMPONENTS:
        _write_component(repo_root, cid, "The component MUST return a value.")
    (repo_root / "verification").mkdir(parents=True, exist_ok=True)
    graph = {
        "nodes": [{"id": cid, "kind": "component"} for cid in COMPONENTS],
        "edges": [],
    }
    (repo_root / "verification" / "corpus-graph.json").write_text(json.dumps(graph))

    pc = repo_root / "gen" / "provenance-checker"
    pc.mkdir(parents=True, exist_ok=True)
    (pc / "provenance_checker.py").write_text(FAKE_PROVENANCE_CHECKER)
    csv = repo_root / "gen" / "capability-scenario-verifier"
    csv.mkdir(parents=True, exist_ok=True)
    (csv / "capability_scenario_verifier.py").write_text(FAKE_CAPABILITY_VERIFIER)
    cgr = repo_root / "gen" / "component-gate-runner"
    cgr.mkdir(parents=True, exist_ok=True)
    (cgr / "component_gate_runner.py").write_text(FAKE_GATE_RUNNER)


def _set_state(repo_root, state):
    path = repo_root / "gen" / "provenance-checker" / "state.json"
    path.write_text(json.dumps(state))


def _calls(repo_root, dep_slug):
    log = repo_root / "gen" / dep_slug / "calls.log"
    if not log.is_file():
        return []
    return [line for line in log.read_text().splitlines() if line.strip()]


def _clear_calls(repo_root, dep_slug):
    log = repo_root / "gen" / dep_slug / "calls.log"
    if log.is_file():
        log.unlink()


def _lint_clean(repo_root):
    gen = next(p for p in Path(provenance_tracker.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec_linter = load_module(path, "spec_linter")
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def _record(repo_root, cid, key, passed):
    rid = _rid(cid)
    generation = {
        "component_id": cid,
        "model": "fake:model",
        "files": ["gen/" + _slug(cid) + "/" + _slug(cid).replace("-", "_") + ".py"],
        "model_call_error": None,
    }
    outcome = "pass" if passed else "fail"
    criterion = {"covers": rid, "result": outcome}
    if not passed:
        criterion["failure_origin"] = "implementation"
    verification = {
        "component_id": cid,
        "overall": outcome,
        "requirement_results": {rid: outcome},
        "criteria": [criterion],
    }
    return provenance_tracker.write_attempt_record(cid, generation, verification, key, repo_root)


def _attempt_files(repo_root, cid):
    d = repo_root / ".hotdocs" / "attempts" / cid
    if not d.is_dir():
        return []
    return sorted(d.glob("*.json"))


def test_cs_merge_visibility_001(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    _lint_clean(repo_root)

    key_a = "sha256:" + "a" * 64
    key_b = "sha256:" + "b" * 64
    key_c1 = "sha256:" + "c" * 64
    key_c2 = "sha256:" + "d" * 64

    # Step 1: one change touching all three; alpha and beta generate and verify,
    # gamma fails verification (no passing provenance for its current spec state).
    _record(repo_root, "comp-alpha", key_a, True)
    _record(repo_root, "comp-beta", key_b, True)
    _record(repo_root, "comp-gamma", key_c1, False)
    _set_state(repo_root, {
        "comp-alpha": {"hit": True, "key": key_a, "overall": "pass"},
        "comp-beta": {"hit": True, "key": key_b, "overall": "pass"},
        "comp-gamma": {"hit": False, "key": key_c1},
    })
    _clear_calls(repo_root, "provenance-checker")

    first = provenance_tracker.check_readiness(repo_root)

    assert field(first, "ready") is False
    comps1 = field(first, "components")
    for cid in COMPONENTS:
        assert cid in comps1, cid
    assert maybe_field(comps1["comp-alpha"], "hit") is True
    assert maybe_field(comps1["comp-beta"], "hit") is True
    assert maybe_field(comps1["comp-gamma"], "hit") is False
    reasons1 = list(field(first, "not_ready_reasons"))
    assert any("comp-gamma" in r for r in reasons1), reasons1
    assert not any("comp-alpha" in r for r in reasons1), reasons1
    assert not any("comp-beta" in r for r in reasons1), reasons1
    # The reason for gamma is recoverable from durable data, not CLI output.
    assert provenance_tracker.last_requirement_failures("comp-gamma", repo_root) == [_rid("comp-gamma")]
    assert provenance_tracker.last_requirement_failures("comp-alpha", repo_root) == []

    calls1 = _calls(repo_root, "provenance-checker")
    assert any(c.endswith("comp-alpha") for c in calls1), calls1
    assert any(c.endswith("comp-gamma") for c in calls1), calls1

    # Step 2: spec edit to the failing component, still lint-clean, then a second
    # generate of it alone.
    _write_component(repo_root, "comp-gamma", "The component MUST return a non-empty value.")
    _lint_clean(repo_root)
    time.sleep(1.1)
    _record(repo_root, "comp-gamma", key_c2, True)
    _set_state(repo_root, {
        "comp-alpha": {"hit": True, "key": key_a, "overall": "pass"},
        "comp-beta": {"hit": True, "key": key_b, "overall": "pass"},
        "comp-gamma": {"hit": True, "key": key_c2, "overall": "pass"},
    })
    _clear_calls(repo_root, "provenance-checker")

    second = provenance_tracker.check_readiness(repo_root)

    comps2 = field(second, "components")
    for cid in COMPONENTS:
        assert cid in comps2, cid
    # Unchanged components are still provenance hits, unchanged from the first query.
    assert maybe_field(comps2["comp-alpha"], "hit") is True
    assert maybe_field(comps2["comp-beta"], "hit") is True
    assert comps2["comp-alpha"] == comps1["comp-alpha"]
    assert comps2["comp-beta"] == comps1["comp-beta"]
    # ...and were not regenerated: still exactly one attempt each.
    assert len(_attempt_files(repo_root, "comp-alpha")) == 1
    assert len(_attempt_files(repo_root, "comp-beta")) == 1
    assert len(_attempt_files(repo_root, "comp-gamma")) == 2
    # The third shows its fresh result.
    assert maybe_field(comps2["comp-gamma"], "hit") is True
    assert field(maybe_field(comps2["comp-gamma"], "verification_report"), "overall") == "pass"
    reasons2 = list(field(second, "not_ready_reasons"))
    for cid in COMPONENTS:
        assert not any(cid in r for r in reasons2), reasons2
    assert field(second, "ready") is True
    assert provenance_tracker.last_requirement_failures("comp-gamma", repo_root) == []

    # Readiness queries are pure reads: the gate runner was never invoked.
    assert _calls(repo_root, "component-gate-runner") == []