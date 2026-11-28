"""Capability Scenario Verifier.

Runs the capability scenarios of every product capability whose
`realizes`-set intersects a blast radius against the real, assembled
`gen/` output, and checks/writes per-capability provenance.
"""

import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

GATE_VERSION = "capability_scenario_verifier@3.0.0"
TIMEOUT_SECONDS = 120


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Dependency access


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


def _load(module_name, rel_dir, repo_root):
    base = Path(repo_root) / rel_dir
    if not base.is_dir():
        base = _tool_root() / rel_dir
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg = base / module_name
        spec = importlib.util.spec_from_file_location(
            module_name, pkg / "__init__.py", submodule_search_locations=[str(pkg)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _criterion_compiler(repo_root):
    return _load("criterion_compiler", "pipeline/criterion-compiler", repo_root)


def _test_author_module(repo_root):
    return _load("test_author", "gen/test-author", repo_root)


def _llm_endpoint(repo_root):
    return _load("llm_endpoint", "gen/llm-endpoint", repo_root)


def _run_environment(repo_root):
    return _load("run_environment", "gen/run-environment", repo_root)


# ---------------------------------------------------------------------------
# Corpus reading


def _frontmatter(text):
    fm = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep:
            fm[key.strip()] = value.strip()
    return fm


def _realizes(value):
    inner = value.partition("[")[2].partition("]")[0]
    return [item.strip() for item in inner.split(",") if item.strip()]


def _components(repo_root):
    comps = []
    for md in (repo_root / "specs" / "components").glob("*/component.md"):
        fm = _frontmatter(md.read_text(encoding="utf-8"))
        slug = md.parent.name
        if fm.get("sealed") == "true":
            code_dir = repo_root / fm.get("source_path", "")
        else:
            code_dir = repo_root / "gen" / slug
        comps.append(
            {
                "id": fm.get("id"),
                "slug": slug,
                "realizes": _realizes(fm.get("realizes", "")),
                "code_dir": code_dir,
            }
        )
    return sorted(comps, key=lambda c: c["id"])


def _realizing(cap_id, components):
    return [c for c in components if cap_id in c["realizes"]]


def _product(cap_id, repo_root):
    for md in sorted((repo_root / "specs" / "product").glob("*.md")):
        if _frontmatter(md.read_text(encoding="utf-8")).get("id") == cap_id:
            return md
    return None


def _scenarios(md, repo_root):
    scenarios = []
    current = None
    in_fence = False
    rel_file = md.relative_to(repo_root).as_posix()
    for line in md.read_text(encoding="utf-8").splitlines():
        if in_fence:
            if line.startswith("```"):
                in_fence = False
            else:
                current["gherkin_lines"].append(line)
        elif line.startswith("### CS-"):
            current = {
                "id": line[4:].strip(),
                "covers": "",
                "kind": "",
                "gherkin_lines": [],
                "file": rel_file,
            }
            scenarios.append(current)
        elif line.startswith("#"):
            current = None
        elif current is not None:
            if line.startswith("Covers:"):
                current["covers"] = line[len("Covers:"):].strip()
            elif line.startswith("Kind:"):
                current["kind"] = line[len("Kind:"):].strip()
            elif line.startswith("```gherkin"):
                in_fence = True
    for sc in scenarios:
        sc["gherkin"] = "\n".join(sc.pop("gherkin_lines"))
    return scenarios


def _code_files(code_dir):
    files = []
    for dirpath, dirnames, filenames in os.walk(code_dir):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_file():
                files.append((path.relative_to(code_dir).as_posix(), path))
    return sorted(files, key=lambda item: item[0])


def _test_name(scenario_id):
    return f"test_{scenario_id.lower().replace('-', '_')}.py"


# ---------------------------------------------------------------------------
# Test execution


def _descendants(pid):
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid=,ppid="], capture_output=True, text=True
        ).stdout
    except OSError:
        return []
    children = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2:
            children.setdefault(int(parts[1]), []).append(int(parts[0]))
    found, stack = [], [pid]
    while stack:
        for child in children.get(stack.pop(), []):
            found.append(child)
            stack.append(child)
    return found


def _kill_tree(proc):
    for pid in _descendants(proc.pid) + [proc.pid]:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    proc.wait()


def _run_pytest(env, rel, repo_root, code_dirs):
    cmd = [
        _get(env, "interpreter"),
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        *_get(env, "pytest_args")(),
        rel,
    ]
    environ = dict(os.environ)
    environ["PYTHONPATH"] = os.pathsep.join(
        code_dirs + [str(_get(env, "plugin_dir"))]
    )
    environ.update(_get(env, "env_for")(repo_root))
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(repo_root),
            env=environ,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return "fail"
    try:
        code = proc.wait(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        return "fail"
    return "pass" if code == 0 else "fail"


def _write_and_run(rel, content, repo_root, environment, code_dirs):
    env = environment()
    if not _get(env, "ok"):
        return "fail"
    target = repo_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return _run_pytest(env, rel, repo_root, code_dirs)


# ---------------------------------------------------------------------------
# Dispatch


def _run_compiled(cap_id, sc, repo_root, environment, code_dirs):
    cc = _criterion_compiler(repo_root)
    parsed = cc.ParsedCriterion(
        criterion_id=sc["id"],
        covers=sc["covers"],
        kind=sc["kind"],
        gherkin=sc["gherkin"],
        file=sc["file"],
    )
    out = cc.compile_criterion(parsed, surface=None)
    if _get(out, "status") == "error":
        return "fail"
    rel = f"verification/capabilities/{cap_id}/compiled/{_test_name(sc['id'])}"
    return _write_and_run(rel, _get(out, "source"), repo_root, environment, code_dirs)


def _run_generated(bundle, test_author, repo_root, environment, code_dirs):
    if test_author is None:
        return "fail"
    outcome = test_author(bundle)
    if _get(outcome, "model_call_error"):
        return "fail"
    file = _get(outcome, "file")
    if not file:
        return "fail"
    path = Path(str(_get(file, "path")))
    if path.is_absolute() or path.parts[:1] != ("verification",) or ".." in path.parts:
        return "fail"
    return _write_and_run(
        path.as_posix(), _get(file, "content"), repo_root, environment, code_dirs
    )


def _judge_entry(outcome):
    if isinstance(outcome, dict):
        result = outcome.get("result", outcome.get("verdict"))
        rationale = outcome.get("rationale")
    else:
        result, rationale = outcome, None
    return {"result": result, "rationale": rationale}


def _overall(entries):
    results = [e["result"] for e in entries]
    if not results or "fail" in results:
        return "fail"
    if all(r == "skipped" for r in results):
        return "skipped"
    return "pass"


def _run_capability(cap_id, repo_root, components, judge, test_author):
    product = _product(cap_id, repo_root)
    scenarios = _scenarios(product, repo_root) if product is not None else []
    code_dirs = [str(c["code_dir"]) for c in _realizing(cap_id, components)]
    holder = []

    def environment():
        if not holder:
            holder.append(
                _run_environment(repo_root).prepare_capability(cap_id, repo_root)
            )
        return holder[0]

    entries = []
    try:
        for sc in scenarios:
            kind = sc["kind"]
            entry = {"id": sc["id"], "kind": kind}
            bundle = {
                "capability_id": cap_id,
                "scenario_id": sc["id"],
                "covers": sc["covers"],
                "kind": kind,
                "gherkin": sc["gherkin"],
                "file": sc["file"],
            }
            if kind == "compiled":
                entry["result"] = _run_compiled(
                    cap_id, sc, repo_root, environment, code_dirs
                )
            elif kind == "generated-test":
                entry["result"] = _run_generated(
                    bundle, test_author, repo_root, environment, code_dirs
                )
            elif kind == "llm-judge":
                if judge is None:
                    entry["result"] = "skipped"
                else:
                    entry.update(_judge_entry(judge(bundle)))
            else:
                entry["result"] = "fail"
            entries.append(entry)
    finally:
        for env in holder:
            _get(env, "close")()
    return {"overall": _overall(entries), "scenarios": entries}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    repo_root = Path(repo_root)
    components = _components(repo_root)
    radius = set(blast_radius)
    capabilities = sorted(
        {cap for c in components if c["id"] in radius for cap in c["realizes"]}
    )
    return {
        cap: _run_capability(cap, repo_root, components, judge, test_author)
        for cap in capabilities
    }


# ---------------------------------------------------------------------------
# Provenance


def _versions(cap_id, repo_root):
    env = _run_environment(repo_root).prepare_capability(cap_id, repo_root)
    try:
        python = next(
            (
                _get(a, "versions")
                for a in (_get(env, "assets") or [])
                if _get(a, "kind") == "python"
            ),
            None,
        )
        versions = {"python": python or {}}
        for driver in _get(env, "drivers") or []:
            versions[_get(driver, "name")] = _get(driver, "versions") or {}
    finally:
        _get(env, "close")()
    return versions


def _content_hash(cap_id, repo_root, product, realizing):
    digest = hashlib.sha256()

    def field(data):
        digest.update(data)
        digest.update(b"\0")

    field(product.read_bytes())
    for comp in realizing:
        field(comp["id"].encode("utf-8"))
        for rel, path in _code_files(comp["code_dir"]):
            if path.name != ".provenance.json":
                field(rel.encode("utf-8"))
                field(path.read_bytes())
    lock = repo_root / "environments" / "python" / "requirements.lock"
    if lock.is_file():
        field(lock.read_bytes())
    field(
        json.dumps(
            _versions(cap_id, repo_root), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )
    return "sha256:" + digest.hexdigest()


def _record_path(cap_id, repo_root):
    return repo_root / "verification" / "capabilities" / cap_id / ".provenance.json"


def _require_product(cap_id, repo_root):
    product = _product(cap_id, repo_root)
    if product is None:
        raise UnknownCapabilityError(f"unknown capability: {cap_id}")
    return product


def check_capability_provenance(capability_id, repo_root):
    repo_root = Path(repo_root)
    product = _require_product(capability_id, repo_root)
    realizing = _realizing(capability_id, _components(repo_root))
    try:
        record = json.loads(
            _record_path(capability_id, repo_root).read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        record = None
    if (
        isinstance(record, dict)
        and record.get("gate_version") == GATE_VERSION
        and record.get("content_hash")
        == _content_hash(capability_id, repo_root, product, realizing)
    ):
        return {
            "hit": True,
            "capability_scenario_report": record.get("capability_scenario_report"),
        }
    return {"hit": False, "capability_scenario_report": None}


# ---------------------------------------------------------------------------
# Built callables


def _criterion_hash(criterion_bundle):
    payload = {
        "criterion_text": criterion_bundle["criterion_text"],
        "requirement_text": criterion_bundle["requirement_text"],
        "interface": criterion_bundle["interface"],
        "glossary": criterion_bundle["glossary"],
        "testing": "",
    }
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_test_author(repo_root, product, realizing, model, seed, llm_backend):
    def interface_text():
        parts = []
        for comp in realizing:
            parts.append(f"## {comp['id']}")
            idir = repo_root / "specs" / "components" / comp["slug"] / "interface"
            for path in sorted(idir.rglob("*.md")):
                parts.append(path.read_text(encoding="utf-8"))
        return "\n".join(parts)

    def call(bundle):
        cap_id = bundle["capability_id"]
        glossary_path = repo_root / "specs" / "glossary.md"
        criterion_bundle = {
            "component_id": f"capabilities/{cap_id}",
            "criterion_id": bundle["scenario_id"],
            "covers": bundle["covers"],
            "criterion_text": bundle["gherkin"],
            "requirement_text": product.read_text(encoding="utf-8"),
            "interface": interface_text(),
            "glossary": glossary_path.read_text(encoding="utf-8")
            if glossary_path.is_file()
            else "",
            "dependency_interfaces": {},
            "module_names": [c["slug"].replace("-", "_") for c in realizing],
        }
        rel = (
            f"verification/capabilities/{cap_id}/generated-test/"
            f"{_test_name(bundle['scenario_id'])}"
        )
        committed = repo_root / rel
        if committed.is_file():
            content = committed.read_text(encoding="utf-8")
            header = f"# hotdocs-criterion: sha256:{_criterion_hash(criterion_bundle)}"
            if content.split("\n", 1)[0] == header:
                return {
                    "model_call_error": None,
                    "file": {"path": rel, "content": content},
                }
        return _test_author_module(repo_root).author_test(
            criterion_bundle,
            model,
            seed=seed,
            repo_root=repo_root,
            llm_backend=llm_backend,
        )

    return call


def _parse_judge_text(text):
    lines = text.splitlines()
    fences = [i for i, line in enumerate(lines) if line.startswith("```")]
    if fences:
        start = fences[0] + 1
        end = fences[1] if len(fences) > 1 else len(lines)
        return "\n".join(lines[start:end]).strip()
    return text.strip()


def _build_judge(repo_root, realizing, model, llm_backend):
    def call(bundle):
        sections = []
        for comp in realizing:
            for rel, path in _code_files(comp["code_dir"]):
                sections.append(
                    f"--- {comp['id']}: {rel} ---\n"
                    + path.read_text(encoding="utf-8", errors="replace")
                )
        prompt = (
            "You are judging whether a product capability scenario holds for "
            "the real, fully assembled code below.\n\n"
            f"Scenario {bundle['scenario_id']} (covers: {bundle['covers']}):\n"
            f"```gherkin\n{bundle['gherkin']}\n```\n\n"
            "Code of every realizing component:\n\n"
            + "\n\n".join(sections)
            + "\n\nReply with only JSON of the form "
            '{"result": "pass" | "fail", "rationale": "..."}.\n'
        )
        response = _llm_endpoint(repo_root).complete(prompt, model, backend=llm_backend)
        error = _get(response, "model_call_error")
        if error:
            return {
                "result": "fail",
                "rationale": f"judge unavailable: {_get(error, 'message')}",
            }
        try:
            parsed = json.loads(_parse_judge_text(_get(response, "text") or ""))
        except ValueError as exc:
            return {"result": "fail", "rationale": f"judge unavailable: unparseable reply: {exc}"}
        result = parsed.get("result") if isinstance(parsed, dict) else None
        if result not in ("pass", "fail"):
            return {
                "result": "fail",
                "rationale": f"judge unavailable: invalid result {result!r}",
            }
        return {"result": result, "rationale": parsed.get("rationale")}

    return call


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    repo_root = Path(repo_root)
    checked = check_capability_provenance(capability_id, repo_root)
    if checked["hit"]:
        return checked
    if model is None:
        raise ModelRequiredError(
            f"capability {capability_id} needs a fresh run and no model was given"
        )
    product = _require_product(capability_id, repo_root)
    components = _components(repo_root)
    realizing = _realizing(capability_id, components)
    content_hash = _content_hash(capability_id, repo_root, product, realizing)
    report = {
        capability_id: _run_capability(
            capability_id,
            repo_root,
            components,
            _build_judge(repo_root, realizing, model, llm_backend),
            _build_test_author(repo_root, product, realizing, model, seed, llm_backend),
        )
    }
    record = {
        "capability_id": capability_id,
        "gate_version": GATE_VERSION,
        "content_hash": content_hash,
        "realizing_components": sorted(c["id"] for c in realizing),
        "capability_scenario_report": report,
        "model": model,
        "seed": seed,
    }
    path = _record_path(capability_id, repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"hit": False, "capability_scenario_report": report}
