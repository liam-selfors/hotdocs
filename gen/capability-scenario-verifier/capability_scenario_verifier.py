"""Capability Scenario Verifier.

Runs the capability scenarios of every product capability whose
`realizes`-set intersects a blast radius, against the real assembled
`gen/` output, and checks and writes per-capability provenance.
"""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

GATE_VERSION = "capability_scenario_verifier@2.2.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


# ---------------------------------------------------------------------------
# helpers

def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    here = Path(__file__).resolve()
    return next((p.parent for p in here.parents if p.name == "gen"), here.parents[1])


def _load_file(file, name):
    package = file.name == "__init__.py"
    spec = importlib.util.spec_from_file_location(
        name, file, submodule_search_locations=[str(file.parent)] if package else None
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dep(repo_root, rel_dir, name):
    base = Path(repo_root) / rel_dir
    if not base.is_dir():
        base = _tool_root() / rel_dir
    file = base / f"{name}.py"
    if not file.is_file():
        file = base / name / "__init__.py"
    return _load_file(file, name)


def _provision(repo_root):
    """The python adapter's provision report when ok, else None."""
    rel = Path("gen") / "kind-python" / "kind_python.py"
    file = Path(repo_root) / rel
    if not file.is_file():
        file = _tool_root() / rel
    if not file.is_file():
        return None
    result = _load_file(file, "kind_python").provision(Path(repo_root))
    return result if _get(result, "ok") else None


def _frontmatter(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip("'\"")
    return fields


def _list(value):
    return [v.strip().strip("'\"") for v in value.strip("[]").split(",") if v.strip()]


def _components(repo_root):
    comps = []
    for md in sorted((repo_root / "specs" / "components").glob("*/component.md")):
        fm = _frontmatter(md)
        cid = fm.get("id", "")
        slug = cid.removeprefix("comp-")
        if fm.get("sealed") == "true":
            code_dir = repo_root / fm.get("source_path", "")
        else:
            code_dir = repo_root / "gen" / slug
        comps.append({
            "id": cid,
            "slug": slug,
            "realizes": _list(fm.get("realizes", "")),
            "code_dir": code_dir,
            "spec_dir": md.parent,
        })
    return sorted(comps, key=lambda c: c["id"])


def _capabilities(repo_root):
    return {
        _frontmatter(md).get("id"): md
        for md in sorted((repo_root / "specs" / "product").glob("*.md"))
    }


_HEADING = re.compile(r"^### (CS-\S+)[^\n]*$", re.M)
_GHERKIN = re.compile(r"^```gherkin[^\n]*\n(.*?)^```", re.M | re.S)


def _field(name, body):
    m = re.search(rf"^{name}:[ \t]*(.*?)[ \t]*$", body, re.M)
    return m.group(1).strip("`") if m else ""


def _scenarios(text):
    parts = _HEADING.split(text)
    out = []
    for sid, body in zip(parts[1::2], parts[2::2]):
        m = _GHERKIN.search(body)
        out.append({
            "id": sid,
            "covers": _field("Covers", body),
            "kind": _field("Kind", body),
            "gherkin": m.group(1) if m else "",
        })
    return out


def _code_files(code_dir):
    files = []
    for dirpath, dirnames, filenames in os.walk(code_dir):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name != ".provenance.json":
                p = Path(dirpath) / name
                files.append((p.relative_to(code_dir).as_posix(), p))
    return sorted(files)


def _test_name(scenario_id):
    return f"test_{scenario_id.lower().replace('-', '_')}.py"


def _write(repo_root, rel, content):
    target = repo_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# running scenarios

def _run_test(repo_root, rel, interpreter, pythonpath):
    if interpreter is None:
        return "fail"
    env = dict(os.environ, PYTHONPATH=pythonpath)
    try:
        proc = subprocess.run(
            [str(interpreter), "-m", "pytest", "-q", "-p", "no:cacheprovider", rel],
            cwd=repo_root, env=env, timeout=120, capture_output=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "fail"
    return "pass" if proc.returncode == 0 else "fail"


def _compiled_test(repo_root, cap_id, sc, rel_file):
    cc = _load_dep(repo_root, "pipeline/criterion-compiler", "criterion_compiler")
    parsed = cc.ParsedCriterion(
        criterion_id=sc["id"], covers=sc["covers"], kind=sc["kind"],
        gherkin=sc["gherkin"], file=rel_file,
    )
    res = cc.compile_criterion(parsed, surface=None)
    if _get(res, "status") == "error":
        return None
    rel = f"verification/capabilities/{cap_id}/compiled/{_test_name(sc['id'])}"
    _write(repo_root, rel, _get(res, "source"))
    return rel


def _generated_test(repo_root, bundle, test_author):
    if test_author is None:
        return None
    outcome = test_author(bundle)
    file = _get(outcome, "file")
    if _get(outcome, "model_call_error") or file is None:
        return None
    rel = str(_get(file, "path"))
    parts = PurePosixPath(rel).parts
    if parts[:1] != ("verification",) or ".." in parts:
        return None
    _write(repo_root, rel, _get(file, "content"))
    return rel


def _run_scenario(cap_id, rel_file, sc, repo_root, judge, test_author, interpreter, pythonpath):
    bundle = {
        "capability_id": cap_id,
        "scenario_id": sc["id"],
        "covers": sc["covers"],
        "kind": sc["kind"],
        "gherkin": sc["gherkin"],
        "file": rel_file,
    }
    kind = sc["kind"]
    entry = {"id": sc["id"], "kind": kind}
    if kind == "llm-judge":
        if judge is None:
            entry["result"] = "skipped"
            return entry
        outcome = judge(bundle)
        if isinstance(outcome, str):
            result, rationale = outcome, ""
        else:
            result = _get(outcome, "result", _get(outcome, "verdict"))
            rationale = _get(outcome, "rationale", "")
        entry["result"] = "pass" if result == "pass" else "fail"
        entry["rationale"] = rationale
        return entry
    if kind == "compiled":
        rel = _compiled_test(repo_root, cap_id, sc, rel_file)
    elif kind == "generated-test":
        rel = _generated_test(repo_root, bundle, test_author)
    else:
        rel = None
    entry["result"] = "fail" if rel is None else _run_test(repo_root, rel, interpreter, pythonpath)
    return entry


def _run_capability(cap_id, cap_path, repo_root, comps, judge, test_author, interpreter):
    realizing = [c for c in comps if cap_id in c["realizes"]]
    pythonpath = os.pathsep.join(str(c["code_dir"]) for c in realizing)
    text = cap_path.read_text(encoding="utf-8") if cap_path else ""
    scenarios = [
        _run_scenario(
            cap_id, cap_path.relative_to(repo_root).as_posix(), sc, repo_root,
            judge, test_author, interpreter, pythonpath,
        )
        for sc in _scenarios(text)
    ]
    results = [s["result"] for s in scenarios]
    if not results or "fail" in results:
        overall = "fail"
    elif all(r == "skipped" for r in results):
        overall = "skipped"
    else:
        overall = "pass"
    return {"overall": overall, "scenarios": scenarios}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    repo_root = Path(repo_root)
    comps = _components(repo_root)
    caps = _capabilities(repo_root)
    blast = set(blast_radius)
    targets = sorted({t for c in comps if c["id"] in blast for t in c["realizes"]})
    provision = _provision(repo_root)
    interpreter = _get(provision, "interpreter") if provision is not None else None
    return {
        t: _run_capability(t, caps.get(t), repo_root, comps, judge, test_author, interpreter)
        for t in targets
    }


# ---------------------------------------------------------------------------
# provenance

def _content_hash(cap_path, realizing, repo_root, versions):
    h = hashlib.sha256()

    def field(data):
        h.update(data)
        h.update(b"\0")

    field(cap_path.read_bytes())
    for c in realizing:
        field(c["id"].encode("utf-8"))
        for rel, f in _code_files(c["code_dir"]):
            field(rel.encode("utf-8"))
            field(f.read_bytes())
    lock = repo_root / "environments" / "python" / "requirements.lock"
    if lock.is_file():
        field(lock.read_bytes())
    field(json.dumps(versions, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return "sha256:" + h.hexdigest()


def _record_path(repo_root, capability_id):
    return repo_root / "verification" / "capabilities" / capability_id / ".provenance.json"


def _check(capability_id, repo_root):
    caps = _capabilities(repo_root)
    if capability_id not in caps:
        raise UnknownCapabilityError(f"unknown capability: {capability_id}")
    cap_path = caps[capability_id]
    comps = _components(repo_root)
    realizing = [c for c in comps if capability_id in c["realizes"]]
    provision = _provision(repo_root)
    versions = _get(provision, "versions") if provision is not None else {}
    key = _content_hash(cap_path, realizing, repo_root, versions)
    try:
        record = json.loads(_record_path(repo_root, capability_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record = None
    hit = (
        isinstance(record, dict)
        and record.get("gate_version") == GATE_VERSION
        and record.get("content_hash") == key
    )
    result = {
        "hit": hit,
        "capability_scenario_report": record.get("capability_scenario_report") if hit else None,
    }
    return result, cap_path, comps, realizing, key


def check_capability_provenance(capability_id, repo_root):
    return _check(capability_id, Path(repo_root))[0]


# ---------------------------------------------------------------------------
# callables built by run_capability_gates

def _make_test_author(capability_id, cap_path, realizing, repo_root, model, seed, llm_backend):
    def call(bundle):
        sid = _get(bundle, "scenario_id")
        parts = []
        for c in realizing:
            parts.append(f"## {c['id']}")
            parts.extend(
                f.read_text(encoding="utf-8")
                for f in sorted((c["spec_dir"] / "interface").rglob("*.md"))
            )
        glossary_path = repo_root / "specs" / "glossary.md"
        criterion_bundle = {
            "component_id": f"capabilities/{capability_id}",
            "criterion_id": sid,
            "covers": _get(bundle, "covers"),
            "criterion_text": _get(bundle, "gherkin"),
            "requirement_text": cap_path.read_text(encoding="utf-8"),
            "interface": "\n".join(parts),
            "glossary": glossary_path.read_text(encoding="utf-8") if glossary_path.is_file() else "",
            "dependency_interfaces": {},
            "module_names": [c["slug"].replace("-", "_") for c in realizing],
        }
        digest = hashlib.sha256(json.dumps(
            {
                "criterion_text": criterion_bundle["criterion_text"],
                "requirement_text": criterion_bundle["requirement_text"],
                "interface": criterion_bundle["interface"],
                "glossary": criterion_bundle["glossary"],
                "testing": "",
            },
            sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        rel = f"verification/capabilities/{capability_id}/generated-test/{_test_name(sid)}"
        target = repo_root / rel
        if target.is_file():
            content = target.read_text(encoding="utf-8")
            if content.split("\n", 1)[0] == f"# hotdocs-criterion: sha256:{digest}":
                return {"model_call_error": None, "file": {"path": rel, "content": content}}
        ta = _load_dep(repo_root, "gen/test-author", "test_author")
        return ta.author_test(
            criterion_bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    return call


def _judge_fail(reason):
    return {"result": "fail", "rationale": f"judge unavailable: {reason}"}


def _make_judge(realizing, repo_root, model, llm_backend):
    def call(bundle):
        sections = []
        for c in realizing:
            for rel, f in _code_files(c["code_dir"]):
                text = f.read_text(encoding="utf-8", errors="replace")
                sections.append(f"### {c['id']}: {rel}\n{text}")
        prompt = (
            "You are judging whether an assembled system satisfies a capability scenario.\n\n"
            f"Covers: {_get(bundle, 'covers')}\n\n"
            f"Scenario (Gherkin):\n{_get(bundle, 'gherkin')}\n\n"
            "Full code of the realizing components:\n\n"
            + "\n\n".join(sections)
            + '\n\nReply with only JSON: {"result": "pass" | "fail", "rationale": "..."}\n'
        )
        le = _load_dep(repo_root, "gen/llm-endpoint", "llm_endpoint")
        resp = le.complete(prompt, model, backend=llm_backend)
        error = _get(resp, "model_call_error")
        if error:
            return _judge_fail(_get(error, "message"))
        text = _get(resp, "text").strip()
        lines = text.splitlines()
        fences = [i for i, line in enumerate(lines) if line.startswith("```")]
        if fences:
            text = "\n".join(lines[fences[0] + 1:(fences[1:2] or [None])[0]])
        try:
            parsed = json.loads(text)
        except ValueError:
            return _judge_fail("unparseable reply")
        result = parsed.get("result") if isinstance(parsed, dict) else None
        if result not in ("pass", "fail"):
            return _judge_fail(f"invalid result {result!r}")
        return {"result": result, "rationale": parsed.get("rationale", "")}

    return call


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    repo_root = Path(repo_root)
    result, cap_path, comps, realizing, key = _check(capability_id, repo_root)
    if result["hit"]:
        return result
    if model is None:
        raise ModelRequiredError(f"a model is required to run capability {capability_id}")
    provision = _provision(repo_root)
    interpreter = _get(provision, "interpreter") if provision is not None else None
    report = {
        capability_id: _run_capability(
            capability_id, cap_path, repo_root, comps,
            _make_judge(realizing, repo_root, model, llm_backend),
            _make_test_author(capability_id, cap_path, realizing, repo_root, model, seed, llm_backend),
            interpreter,
        )
    }
    record = {
        "capability_id": capability_id,
        "gate_version": GATE_VERSION,
        "content_hash": key,
        "realizing_components": sorted(c["id"] for c in realizing),
        "capability_scenario_report": report,
        "model": model,
        "seed": seed,
    }
    record_path = _record_path(repo_root, capability_id)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"hit": False, "capability_scenario_report": report}
