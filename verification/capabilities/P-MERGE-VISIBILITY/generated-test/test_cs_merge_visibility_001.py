"""CS-MERGE-VISIBILITY-001 (Covers: P-MERGE-VISIBILITY).

Given a change touching three components where two generate and verify and
one fails verification, followed by a spec edit to the failing component and
a second `hotdocs generate` of it, when a developer queries
provenance-tracker after each step, then the first query shows two
components ready and one not ready with its reason, and the second shows the
two unchanged components still ready (provenance hits, not regenerated)
alongside the third's fresh result, without needing the first run's CLI
output.
"""

import provenance_tracker
import provenance_tracker_ui

import json
import os
from pathlib import Path


COMPONENTS = {
    "comp-alpha": "alpha",
    "comp-beta": "beta",
    "comp-gamma": "gamma",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def maybe_field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


# --------------------------------------------------------------------------
# Fixture construction
# --------------------------------------------------------------------------

def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(repo: Path, cid: str, slug: str, req_ids, req_text_suffix=""):
    base = repo / "specs" / "components" / slug
    _write(
        base / "component.md",
        "---\n"
        f"id: {cid}\n"
        f"title: {slug.capitalize()}\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n\n"
        f"# {slug.capitalize()}\n\n"
        f"Synthetic fixture component {cid}.\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        base / "interface" / "library.md",
        f"# Library\n\n```\n{slug}_run() -> int\n```\n\nReturns an integer.\n",
    )
    for n, rid in enumerate(req_ids, start=1):
        _write(
            base / "requirements" / f"{rid}.md",
            f"# {rid}\n\n`{slug}_run()` MUST return {n}.{req_text_suffix}\n",
        )
        ac_id = rid.replace("R-", "AC-", 1)
        _write(
            base / "acceptance" / f"{ac_id}.md",
            f"# {ac_id}\n\nCovers: {rid}\n\n"
            f"Given nothing\nWhen `{slug}_run()` is called\nThen it returns {n}\n",
        )


def _req_ids(slug):
    up = slug.upper()
    if slug == "gamma":
        return [f"R-{up}-001", f"R-{up}-002"]
    return [f"R-{up}-001"]


def _write_corpus_graph(repo: Path):
    nodes = [
        {"id": cid, "kind": "component", "path": f"specs/components/{slug}/component.md"}
        for cid, slug in COMPONENTS.items()
    ]
    _write(
        repo / "verification" / "corpus-graph.json",
        json.dumps({"nodes": nodes, "edges": []}, indent=2),
    )


FAKE_PROVENANCE_CHECKER = r'''
import json
import os

STATE_PATH = __STATE_PATH__
LOG_PATH = __LOG_PATH__
COMPONENTS = __COMPONENTS__


class _R(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _state():
    with open(STATE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _log(fn, cid):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"fn": fn, "component_id": cid}) + "\n")


def _key_for(cid, version):
    return "sha256:fake-" + cid + "-" + version


def _match_str(s):
    for cid, slug in COMPONENTS.items():
        if s == cid or s == slug:
            return cid, None
        prefix = "sha256:fake-" + cid + "-"
        if s.startswith(prefix):
            return cid, s[len(prefix):]
    return None, None


def _resolve(args, kwargs):
    cid_found, version_found = None, None
    for v in list(args) + list(kwargs.values()):
        cands = []
        if isinstance(v, str):
            cands.append(v)
        elif isinstance(v, os.PathLike):
            p = os.fspath(v)
            cands.append(os.path.basename(p.rstrip("/\\")))
        elif isinstance(v, dict):
            for k in ("component_id", "key", "provenance_key", "spec_bundle_hash"):
                if isinstance(v.get(k), str):
                    cands.append(v.get(k))
        else:
            for k in ("component_id", "key", "provenance_key", "spec_bundle_hash"):
                a = getattr(v, k, None)
                if isinstance(a, str):
                    cands.append(a)
        for s in cands:
            cid, ver = _match_str(s)
            if cid is not None:
                if cid_found is None:
                    cid_found = cid
                if ver is not None and version_found is None:
                    version_found = ver
    return cid_found, version_found


def _result(cid, version):
    st = _state()[cid]
    if version is None:
        version = st["spec_version"]
    key = _key_for(cid, version)
    hit = st.get("provenance_version") == version
    if not hit:
        return _R(
            component_id=cid,
            hit=False,
            key=key,
            provenance_key=key,
            manifest=None,
            verification_report=None,
            license_scan=None,
            secret_scan=None,
        )
    overall = st.get("overall", "pass")
    return _R(
        component_id=cid,
        hit=True,
        key=key,
        provenance_key=key,
        manifest=_R(spec_bundle_hash=key, component_id=cid),
        verification_report=_R(
            overall=overall,
            requirement_results=_R(st.get("requirement_results", {})),
        ),
        license_scan=_R(blocked=False, findings=[]),
        secret_scan=_R(flagged=False, findings=[]),
    )


def current_sealed_key(*args, **kwargs):
    cid, _ = _resolve(args, kwargs)
    _log("current_sealed_key", cid)
    return None


def current_provenance_key(*args, **kwargs):
    cid, _ = _resolve(args, kwargs)
    _log("current_provenance_key", cid)
    return _key_for(cid, _state()[cid]["spec_version"])


def check_provenance(*args, **kwargs):
    cid, version = _resolve(args, kwargs)
    _log("check_provenance", cid)
    return _result(cid, version)


def check_sealed_provenance(*args, **kwargs):
    cid, version = _resolve(args, kwargs)
    _log("check_sealed_provenance", cid)
    return _result(cid, version)
'''


FAKE_GATE_RUNNER = r'''
import json

LOG_PATH = __LOG_PATH__


def _log(fn):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"fn": fn}) + "\n")


def run_component_gates(*args, **kwargs):
    _log("run_component_gates")
    raise AssertionError("component-gate-runner must never be called by a provenance query")
'''


def _install_fakes(repo: Path, state_path: Path, prov_log: Path, gate_log: Path):
    pc = (
        FAKE_PROVENANCE_CHECKER.replace("__STATE_PATH__", repr(str(state_path)))
        .replace("__LOG_PATH__", repr(str(prov_log)))
        .replace("__COMPONENTS__", repr(COMPONENTS))
    )
    _write(repo / "gen" / "provenance-checker" / "provenance_checker.py", pc)
    gr = FAKE_GATE_RUNNER.replace("__LOG_PATH__", repr(str(gate_log)))
    _write(repo / "gen" / "component-gate-runner" / "component_gate_runner.py", gr)


def _set_state(state_path: Path, state: dict):
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _simulate_generate(repo, cid, overall, requirement_results, spec_hash):
    """What `hotdocs generate` leaves behind: generated code plus an AttemptRecord."""
    slug = COMPONENTS[cid]
    _write(repo / "gen" / slug / f"{slug}.py", f"def {slug}_run():\n    return 1\n")
    generation = {
        "component_id": cid,
        "model": "anthropic:claude-sonnet-5",
        "model_call_error": None,
        "files": [f"gen/{slug}/{slug}.py"],
    }
    verification = {
        "component_id": cid,
        "overall": overall,
        "requirement_results": dict(requirement_results),
    }
    return provenance_tracker.write_attempt_record(
        cid, generation, verification, spec_hash, repo
    )


def _run_verify_cli(repo, capsys):
    capsys.readouterr()
    try:
        rc = provenance_tracker.main(["verify", "--repo-root", str(repo)])
    except SystemExit as exc:  # pragma: no cover - either style is acceptable
        rc = exc.code
    out = capsys.readouterr().out
    return rc, out


def _components(report):
    comps = field(report, "components")
    assert isinstance(comps, dict) or hasattr(comps, "keys")
    return comps


def _hit(result):
    return bool(field(result, "hit"))


def _overall(result):
    vr = maybe_field(result, "verification_report")
    return None if vr is None else maybe_field(vr, "overall")


def _key(result):
    return maybe_field(result, "provenance_key", maybe_field(result, "key"))


def _nodes_by_id(snapshot):
    return {field(n, "id"): n for n in field(snapshot, "nodes")}


# --------------------------------------------------------------------------
# The test
# --------------------------------------------------------------------------

def test_cs_merge_visibility_001(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    control = tmp_path / "control"
    control.mkdir()
    state_path = control / "state.json"
    prov_log = control / "provenance_checker_calls.jsonl"
    gate_log = control / "gate_runner_calls.jsonl"

    for cid, slug in COMPONENTS.items():
        _write_component(repo, cid, slug, _req_ids(slug))
    _write_corpus_graph(repo)
    _install_fakes(repo, state_path, prov_log, gate_log)

    # ---- Step 1: a change touching three components; alpha and beta
    # generate and verify, gamma fails verification (no provenance).
    _set_state(
        state_path,
        {
            "comp-alpha": {
                "spec_version": "v1", "provenance_version": "v1", "overall": "pass",
                "requirement_results": {"R-ALPHA-001": "pass"},
            },
            "comp-beta": {
                "spec_version": "v1", "provenance_version": "v1", "overall": "pass",
                "requirement_results": {"R-BETA-001": "pass"},
            },
            "comp-gamma": {
                "spec_version": "v1", "provenance_version": None, "overall": "fail",
                "requirement_results": {"R-GAMMA-001": "pass", "R-GAMMA-002": "fail"},
            },
        },
    )
    _simulate_generate(repo, "comp-alpha", "pass", {"R-ALPHA-001": "pass"},
                       "sha256:fake-comp-alpha-v1")
    _simulate_generate(repo, "comp-beta", "pass", {"R-BETA-001": "pass"},
                       "sha256:fake-comp-beta-v1")
    _simulate_generate(repo, "comp-gamma", "fail",
                       {"R-GAMMA-001": "pass", "R-GAMMA-002": "fail"},
                       "sha256:fake-comp-gamma-v1")

    # First query — a fresh, durable query; no CLI output from the generate
    # runs is kept or consulted.
    report1 = provenance_tracker.check_readiness(repo)
    comps1 = _components(report1)
    for cid in COMPONENTS:
        assert cid in comps1, f"{cid} missing from VerifyReport.components"

    assert field(report1, "ready") is False

    assert _hit(comps1["comp-alpha"]) and _overall(comps1["comp-alpha"]) == "pass"
    assert _hit(comps1["comp-beta"]) and _overall(comps1["comp-beta"]) == "pass"
    gamma1 = comps1["comp-gamma"]
    assert not (_hit(gamma1) and _overall(gamma1) == "pass"), \
        "comp-gamma must not be reported ready"

    reasons1 = list(field(report1, "not_ready_reasons"))
    assert any("comp-gamma" in r for r in reasons1), reasons1
    assert not any("comp-alpha" in r for r in reasons1), reasons1
    assert not any("comp-beta" in r for r in reasons1), reasons1

    # Why not ready: the failing requirement is recoverable from tracking data.
    assert provenance_tracker.last_requirement_failures("comp-gamma", repo) == ["R-GAMMA-002"]

    rc1, out1 = _run_verify_cli(repo, capsys)
    assert rc1 == 1
    lines1 = [ln for ln in out1.strip().splitlines() if ln.strip()]
    assert lines1 and lines1[0].strip() == "not ready", out1
    assert any("comp-gamma" in ln for ln in lines1[1:]), out1

    snap1 = provenance_tracker_ui.render_tracker_ui(tmp_path / "ui1", repo)
    nodes1 = _nodes_by_id(snap1)
    assert field(nodes1["comp-alpha"], "status") == "passing"
    assert field(nodes1["comp-beta"], "status") == "passing"
    assert field(nodes1["comp-gamma"], "status") in ("missing", "failing")
    assert list(field(nodes1["comp-gamma"], "retry_feedback")) == ["R-GAMMA-002"]
    assert field(snap1, "ready") is False
    assert (tmp_path / "ui1" / "index.html").is_file()

    alpha_key1 = _key(comps1["comp-alpha"])
    beta_key1 = _key(comps1["comp-beta"])
    gamma_key1 = _key(gamma1)

    # ---- Step 2: spec edit to the failing component and a second
    # `hotdocs generate` of it only.
    _write(
        repo / "specs" / "components" / "gamma" / "requirements" / "R-GAMMA-002.md",
        "# R-GAMMA-002\n\n`gamma_run()` MUST return 2, even when called twice.\n",
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["comp-gamma"] = {
        "spec_version": "v2", "provenance_version": "v2", "overall": "pass",
        "requirement_results": {"R-GAMMA-001": "pass", "R-GAMMA-002": "pass"},
    }
    _set_state(state_path, state)
    _simulate_generate(repo, "comp-gamma", "pass",
                       {"R-GAMMA-001": "pass", "R-GAMMA-002": "pass"},
                       "sha256:fake-comp-gamma-v2")

    # Second query.
    report2 = provenance_tracker.check_readiness(repo)
    comps2 = _components(report2)
    for cid in COMPONENTS:
        assert cid in comps2

    assert field(report2, "ready") is True
    assert list(field(report2, "not_ready_reasons")) == []

    # The two unchanged components are still ready, as provenance hits on
    # the very same key — not regenerated.
    for cid, key1 in (("comp-alpha", alpha_key1), ("comp-beta", beta_key1)):
        r2 = comps2[cid]
        assert _hit(r2) and _overall(r2) == "pass"
        assert _key(r2) == key1
    attempts_root = repo / ".hotdocs" / "attempts"
    for cid in ("comp-alpha", "comp-beta"):
        assert len(list((attempts_root / cid).glob("*.json"))) == 1, \
            f"{cid} must not have been regenerated"
    assert len(list((attempts_root / "comp-gamma").glob("*.json"))) == 2

    # The third's fresh result.
    gamma2 = comps2["comp-gamma"]
    assert _hit(gamma2) and _overall(gamma2) == "pass"
    assert _key(gamma2) != gamma_key1
    assert provenance_tracker.last_requirement_failures("comp-gamma", repo) == []

    rc2, out2 = _run_verify_cli(repo, capsys)
    assert rc2 == 0
    lines2 = [ln for ln in out2.strip().splitlines() if ln.strip()]
    assert lines2 and lines2[0].strip() == "ready", out2

    snap2 = provenance_tracker_ui.render_tracker_ui(tmp_path / "ui2", repo)
    nodes2 = _nodes_by_id(snap2)
    for cid in COMPONENTS:
        assert field(nodes2[cid], "status") == "passing"
    assert field(snap2, "ready") is True

    # The query read provenance through the (faked) provenance-checker and
    # never triggered component-gate-runner.
    assert prov_log.is_file(), "provenance-checker stand-in was never consulted"
    calls = [json.loads(ln) for ln in prov_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    checked = {c["component_id"] for c in calls
               if c["fn"] in ("check_provenance", "check_sealed_provenance")}
    assert set(COMPONENTS) <= checked
    assert not gate_log.exists(), "a provenance query must never run component gates"