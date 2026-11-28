# hotdocs-criterion: sha256:35567d5102d83d5883e6b1dce852552aded2a559934694bf37345d10ae486d92
import importlib.util
import json
import sys
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def opt_field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def run_lint(repo_root):
    gen = next(p for p in Path(provenance_tracker.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


COMPONENTS = [
    ("comp-alpha", "alpha", "R-ALPHA-001", "AC-ALPHA-001"),
    ("comp-beta", "beta", "R-BETA-001", "AC-BETA-001"),
    ("comp-gamma", "gamma", "R-GAMMA-001", "AC-GAMMA-001"),
]


def write_corpus(repo_root):
    specs = repo_root / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Widget** - a thing the fixture components handle.\n",
        encoding="utf-8",
    )
    for cid, slug, rid, acid in COMPONENTS:
        cdir = specs / "components" / slug
        (cdir / "requirements").mkdir(parents=True, exist_ok=True)
        (cdir / "acceptance").mkdir(parents=True, exist_ok=True)
        (cdir / "interface").mkdir(parents=True, exist_ok=True)
        (cdir / "component.md").write_text(
            "---\n"
            + "id: " + cid + "\n"
            + "title: " + slug.capitalize() + " Component\n"
            + "status: draft\n"
            + "owners: [pipeline-team]\n"
            + "sealed: true\n"
            + "source_path: legacy/" + slug + "/\n"
            + "---\n\n"
            + "# " + slug.capitalize() + " Component\n\n"
            + "## Purpose\n\nHandles widgets for the " + slug + " fixture.\n",
            encoding="utf-8",
        )
        (cdir / "requirements" / (rid + ".md")).write_text(
            "# " + rid + "\n\nThe component MUST return a widget count.\n",
            encoding="utf-8",
        )
        (cdir / "acceptance" / (acid + ".md")).write_text(
            "# " + acid + "\n\n"
            + "Covers: " + rid + "\n"
            + "Kind: generated-test\n\n"
            + "```gherkin\n"
            + "Given a widget list\n"
            + "When the count is requested\n"
            + "Then the number of widgets is returned\n"
            + "```\n",
            encoding="utf-8",
        )
        (cdir / "interface" / "library.md").write_text(
            "# Library\n\n```\ncount(widgets: list) -> int\n```\n",
            encoding="utf-8",
        )
        (cdir / "constraints.md").write_text(
            "# Constraints\n\nNone beyond the requirements.\n",
            encoding="utf-8",
        )


FAKE_CHECKER_BODY = '''
import hashlib
import json
from pathlib import Path

STATE = Path(STATE_PATH)
LOG = Path(LOG_PATH)
SPECS = Path(REPO_ROOT) / "specs" / "components"


class _Result(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _log(line):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\\n")


def _cid_from(value):
    if isinstance(value, str) and value.startswith("comp-"):
        return value.split("|", 1)[0]
    if isinstance(value, dict):
        for k in ("component_id", "id"):
            v = value.get(k)
            if isinstance(v, str) and v.startswith("comp-"):
                return v
    for k in ("component_id", "id"):
        v = getattr(value, k, None)
        if isinstance(v, str) and v.startswith("comp-"):
            return v
    return None


def _cid(args, kwargs):
    for v in list(args) + list(kwargs.values()):
        c = _cid_from(v)
        if c:
            return c
    raise ValueError("no component id in call")


def _key(cid):
    slug = cid[len("comp-"):]
    h = hashlib.sha256()
    base = SPECS / slug
    for p in sorted(base.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(base)).encode("utf-8"))
            h.update(b"\\0")
            h.update(p.read_bytes())
            h.update(b"\\0")
    return cid + "|sha256:" + h.hexdigest()


def _state():
    if STATE.is_file():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {}


def _result(cid):
    key = _key(cid)
    entry = _state().get(cid)
    hit = bool(entry) and entry.get("key") == key
    if hit:
        overall = entry.get("overall", "pass")
        failing = entry.get("failing", [])
        rr = {r: "fail" for r in failing}
        vr = {
            "component_id": cid,
            "overall": overall,
            "requirement_results": rr,
            "criteria": [],
        }
        reason = None
    else:
        vr = None
        reason = "no provenance for current spec state"
    return _Result({
        "component_id": cid,
        "hit": hit,
        "key": key,
        "provenance_key": key,
        "manifest": ({"component_id": cid, "spec_bundle_hash": key} if hit else None),
        "verification_report": vr,
        "license_scan": ({"blocked": False, "findings": []} if hit else None),
        "secret_scan": ({"flagged": False, "matches": []} if hit else None),
        "reason": reason,
    })


def current_sealed_key(*args, **kwargs):
    _log("current_sealed_key " + _cid(args, kwargs))
    return None


def current_provenance_key(*args, **kwargs):
    cid = _cid(args, kwargs)
    _log("current_provenance_key " + cid)
    return _key(cid)


def check_provenance(*args, **kwargs):
    cid = _cid(args, kwargs)
    _log("check_provenance " + cid)
    return _result(cid)


def check_sealed_provenance(*args, **kwargs):
    cid = _cid(args, kwargs)
    _log("check_sealed_provenance " + cid)
    return _result(cid)
'''


FAKE_SCANNER_BODY = '''

def scan(repo_root):
    return {"flagged": False, "matches": []}
'''


def write_fakes(repo_root, state_path, log_path):
    pc = repo_root / "gen" / "provenance-checker"
    pc.mkdir(parents=True, exist_ok=True)
    (pc / "provenance_checker.py").write_text(
        "STATE_PATH = " + repr(str(state_path)) + "\n"
        + "LOG_PATH = " + repr(str(log_path)) + "\n"
        + "REPO_ROOT = " + repr(str(repo_root)) + "\n"
        + FAKE_CHECKER_BODY,
        encoding="utf-8",
    )
    ss = repo_root / "gen" / "secret-scanner"
    ss.mkdir(parents=True, exist_ok=True)
    (ss / "secret_scanner.py").write_text(FAKE_SCANNER_BODY, encoding="utf-8")


def load_fake_checker(repo_root):
    return load_module(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        "test_cs_merge_visibility_fake_checker",
    )


def generation_result(cid):
    return {
        "component_id": cid,
        "model": "anthropic:claude-sonnet-5",
        "files": ["gen/" + cid[len("comp-"):] + "/module.py"],
        "model_call_error": None,
    }


def verification_report(cid, rid, passed):
    return {
        "component_id": cid,
        "overall": "pass" if passed else "fail",
        "requirement_results": {rid: "pass" if passed else "fail"},
        "criteria": [
            {
                "criterion_id": "AC-" + rid[len("R-"):],
                "covers": rid,
                "result": "pass" if passed else "fail",
                **({} if passed else {"failure_origin": "implementation"}),
            }
        ],
    }


def attempt_count(repo_root, cid):
    d = repo_root / ".hotdocs" / "attempts" / cid
    if not d.is_dir():
        return 0
    return len([p for p in d.glob("*.json") if p.is_file()])


def comp_ready(result):
    if not field(result, "hit"):
        return False
    vr = field(result, "verification_report")
    return vr is not None and field(vr, "overall") == "pass"


def test_cs_merge_visibility_001(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    state_path = tmp_path / "provenance-state.json"
    log_path = tmp_path / "fake-calls.log"
    write_corpus(repo_root)
    write_fakes(repo_root, state_path, log_path)
    run_lint(repo_root)

    fake = load_fake_checker(repo_root)
    ids = [c[0] for c in COMPONENTS]
    rids = {c[0]: c[2] for c in COMPONENTS}

    # Step 1: first `hotdocs generate` - alpha and beta verify, gamma fails.
    state = {}
    for cid in ("comp-alpha", "comp-beta"):
        key = fake.current_provenance_key(cid, repo_root)
        state[cid] = {"key": key, "overall": "pass", "failing": []}
        provenance_tracker.write_attempt_record(
            cid, generation_result(cid), verification_report(cid, rids[cid], True),
            key, repo_root,
        )
    gamma_key_1 = fake.current_provenance_key("comp-gamma", repo_root)
    provenance_tracker.write_attempt_record(
        "comp-gamma", generation_result("comp-gamma"),
        verification_report("comp-gamma", rids["comp-gamma"], False),
        gamma_key_1, repo_root,
    )
    state_path.write_text(json.dumps(state), encoding="utf-8")
    keys_after_first = {cid: state[cid]["key"] for cid in ("comp-alpha", "comp-beta")}

    # First query - no CLI output from the generate run is consulted.
    report1 = provenance_tracker.check_readiness(repo_root)
    assert log_path.is_file() and log_path.read_text(encoding="utf-8").strip()

    comps1 = field(report1, "components")
    assert set(ids) <= set(comps1.keys())
    assert comp_ready(comps1["comp-alpha"])
    assert comp_ready(comps1["comp-beta"])
    assert not comp_ready(comps1["comp-gamma"])
    assert field(report1, "ready") is False
    reasons1 = list(field(report1, "not_ready_reasons"))
    assert any("comp-gamma" in r for r in reasons1), reasons1
    assert not any("comp-alpha" in r for r in reasons1), reasons1
    assert not any("comp-beta" in r for r in reasons1), reasons1
    assert list(provenance_tracker.last_requirement_failures("comp-gamma", repo_root)) == [
        rids["comp-gamma"]
    ]

    # Step 2: spec edit to the failing component, still lint-clean.
    req = repo_root / "specs" / "components" / "gamma" / "requirements" / (rids["comp-gamma"] + ".md")
    req.write_text(
        "# " + rids["comp-gamma"] + "\n\n"
        + "The component MUST return a widget count, zero for an empty list.\n",
        encoding="utf-8",
    )
    run_lint(repo_root)
    gamma_key_2 = fake.current_provenance_key("comp-gamma", repo_root)
    assert gamma_key_2 != gamma_key_1

    # Second `hotdocs generate comp-gamma` - only gamma is regenerated.
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["comp-gamma"] = {"key": gamma_key_2, "overall": "pass", "failing": []}
    state_path.write_text(json.dumps(state), encoding="utf-8")
    provenance_tracker.write_attempt_record(
        "comp-gamma", generation_result("comp-gamma"),
        verification_report("comp-gamma", rids["comp-gamma"], True),
        gamma_key_2, repo_root,
    )

    # Second query.
    report2 = provenance_tracker.check_readiness(repo_root)
    comps2 = field(report2, "components")
    assert set(ids) <= set(comps2.keys())
    for cid in ("comp-alpha", "comp-beta"):
        assert field(comps2[cid], "hit") is True
        assert comp_ready(comps2[cid])
        # Unchanged: provenance still matches the first run's key, no new attempt.
        assert fake.current_provenance_key(cid, repo_root) == keys_after_first[cid]
        assert attempt_count(repo_root, cid) == 1
    assert comp_ready(comps2["comp-gamma"])
    assert attempt_count(repo_root, "comp-gamma") == 2
    reasons2 = list(field(report2, "not_ready_reasons"))
    assert not any(cid in r for r in reasons2 for cid in ids), reasons2
    assert field(report2, "ready") is True
    assert reasons2 == []