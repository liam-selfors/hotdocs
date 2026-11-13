"""Capability Scenario Verifier (comp-capability-scenario-verifier).

Runs the capability scenarios of every product capability whose
`realizes`-set intersects a blast radius against the real, fully
assembled `gen/` output, and checks/writes the per-capability
provenance record keyed on the realizing components' actual content.
"""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

GATE_VERSION = "capability_scenario_verifier@2.0.0"

_COMPILER_DIR = "pipeline/criterion-compiler"
_TEST_AUTHOR_DIR = "gen/test-author"
_LLM_ENDPOINT_DIR = "gen/llm-endpoint"
_TEST_TIMEOUT_SECONDS = 120

_SCENARIO_HEADING = re.compile(r"^###\s+(CS-[A-Za-z0-9_-]+)")
_COVERS_LINE = re.compile(r"^Covers:\s*(.*)$")
_KIND_LINE = re.compile(r"^Kind:\s*(.*)$")
_FENCED_REPLY = re.compile(r"^```[^\n]*\n(.*?)\n?```$", re.S)


class UnknownCapabilityError(ValueError):
    """No `specs/product/*.md` declares the requested capability id."""


class ModelRequiredError(ValueError):
    """A provenance miss needs a `model` to run the capability's scenarios."""


# ---------------------------------------------------------------------------
# Dual dict-or-attribute access for every value read from a dependency.
# ---------------------------------------------------------------------------

def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# ---------------------------------------------------------------------------
# Dependency loading (lazy, from repo_root, else the tool root).
# ---------------------------------------------------------------------------

def _tool_root():
    here = Path(__file__).resolve()
    return next(p for p in here.parents if p.name == "gen").parent


def _load(repo_root, rel_dir, module_name):
    directory = Path(repo_root) / rel_dir
    if not directory.is_dir():
        directory = _tool_root() / rel_dir
    flat = directory / f"{module_name}.py"
    if flat.is_file():
        path, locations = flat, None
    else:
        path = directory / module_name / "__init__.py"
        locations = [str(directory / module_name)]
    spec = importlib.util.spec_from_file_location(
        module_name, str(path), submodule_search_locations=locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Corpus reading.
# ---------------------------------------------------------------------------

def _unquote(value):
    return value.strip().strip("'\"")


def _value(value):
    if value == "":
        return []
    if value.startswith("[") and value.endswith("]"):
        return [_unquote(v) for v in value[1:-1].split(",") if v.strip()]
    return _unquote(value)


def _frontmatter(text):
    lines = text.splitlines()
    fields = {}
    if not lines or lines[0].strip() != "---":
        return fields
    key = None
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if stripped.startswith("- ") and isinstance(fields.get(key), list):
            fields[key].append(_unquote(stripped[2:]))
        elif ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            fields[key] = _value(value.strip())
    return fields


def _components(repo_root):
    comps = []
    for path in sorted((repo_root / "specs" / "components").glob("*/component.md")):
        fm = _frontmatter(path.read_text(encoding="utf-8"))
        cid = str(fm.get("id", ""))
        slug = cid.removeprefix("comp-")
        realizes = fm.get("realizes", [])
        if isinstance(realizes, str):
            realizes = [realizes]
        if str(fm.get("sealed", "")).lower() == "true":
            code_dir = repo_root / str(fm.get("source_path", ""))
        else:
            code_dir = repo_root / "gen" / slug
        comps.append({
            "id": cid,
            "slug": slug,
            "spec_dir": path.parent,
            "realizes": list(realizes),
            "code_dir": code_dir,
        })
    return sorted(comps, key=lambda c: c["id"])


def _capabilities(repo_root):
    caps = {}
    for path in sorted((repo_root / "specs" / "product").glob("*.md")):
        caps[_frontmatter(path.read_text(encoding="utf-8")).get("id")] = path
    return caps


def _realizing(components, capability_id):
    return [c for c in components if capability_id in c["realizes"]]


def _intersecting_capabilities(components, blast_radius):
    # SELECT DISTINCT target_id FROM edges
    #   WHERE edge_type = 'realizes' AND source_id IN (<blast-radius ids>)
    edges = [(c["id"], target) for c in components for target in c["realizes"]]
    wanted = set(blast_radius)
    return sorted({target for source, target in edges if source in wanted})


def _parse_scenarios(text):
    scenarios = []
    current = None
    in_fence = False
    capture = False
    for line in text.splitlines():
        stripped = line.strip()
        if in_fence:
            if stripped.startswith("```"):
                in_fence = False
            elif capture:
                current["gherkin_lines"].append(line)
            continue
        if stripped.startswith("```"):
            in_fence = True
            capture = current is not None and stripped[3:].strip() == "gherkin"
            continue
        heading = _SCENARIO_HEADING.match(stripped)
        if heading:
            current = {"id": heading.group(1), "covers": "", "kind": "", "gherkin_lines": []}
            scenarios.append(current)
            continue
        if stripped.startswith("#"):
            current = None
            continue
        if current is None:
            continue
        covers = _COVERS_LINE.match(stripped)
        if covers:
            current["covers"] = covers.group(1).strip()
        kind = _KIND_LINE.match(stripped)
        if kind:
            current["kind"] = kind.group(1).strip()
    return [
        {
            "id": s["id"],
            "covers": s["covers"],
            "kind": s["kind"],
            "gherkin": "\n".join(s["gherkin_lines"]),
        }
        for s in scenarios
    ]


def _code_files(code_dir):
    files = []
    for path in code_dir.rglob("*"):
        rel = path.relative_to(code_dir)
        if "__pycache__" in rel.parts or not path.is_file():
            continue
        files.append((rel.as_posix(), path))
    return sorted(files)


# ---------------------------------------------------------------------------
# Scenario dispatch.
# ---------------------------------------------------------------------------

def _scenario_bundle(capability_id, scenario, file_rel):
    return {
        "capability_id": capability_id,
        "scenario_id": scenario["id"],
        "covers": scenario["covers"],
        "kind": scenario["kind"],
        "gherkin": scenario["gherkin"],
        "file": file_rel,
    }


def _write(repo_root, rel, content):
    target = repo_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _run_test(repo_root, rel, realizing):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(str(c["code_dir"].absolute()) for c in realizing)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", rel],
            cwd=str(repo_root),
            env=env,
            timeout=_TEST_TIMEOUT_SECONDS,
            capture_output=True,
        )
    except (subprocess.TimeoutExpired, OSError):
        return "fail"
    return "pass" if proc.returncode == 0 else "fail"


def _run_compiled(repo_root, capability_id, scenario, file_rel, realizing):
    compiler = _load(repo_root, _COMPILER_DIR, "criterion_compiler")
    parsed = compiler.ParsedCriterion(
        criterion_id=scenario["id"],
        covers=scenario["covers"],
        kind=scenario["kind"],
        gherkin=scenario["gherkin"],
        file=file_rel,
    )
    outcome = compiler.compile_criterion(parsed, surface=None)
    if _get(outcome, "status") == "error":
        return "fail"
    name = "test_" + scenario["id"].lower().replace("-", "_") + ".py"
    rel = f"verification/capabilities/{capability_id}/compiled/{name}"
    _write(repo_root, rel, _get(outcome, "source"))
    return _run_test(repo_root, rel, realizing)


def _run_generated(repo_root, bundle, realizing, test_author):
    if test_author is None:
        return "fail"
    outcome = test_author(bundle)
    test_file = _get(outcome, "file")
    if _get(outcome, "model_call_error") or not test_file:
        return "fail"
    rel = str(_get(test_file, "path"))
    parts = PurePosixPath(rel)
    if parts.is_absolute() or parts.parts[:1] != ("verification",) or ".." in parts.parts:
        return "fail"
    _write(repo_root, rel, _get(test_file, "content"))
    return _run_test(repo_root, rel, realizing)


def _judge_outcome(outcome):
    if isinstance(outcome, dict) or hasattr(outcome, "result") or hasattr(outcome, "verdict"):
        result = _get(outcome, "result")
        if result is None:
            result = _get(outcome, "verdict")
        return result, _get(outcome, "rationale")
    return outcome, None


def _overall(scenarios):
    results = [s["result"] for s in scenarios]
    if not results or "fail" in results:
        return "fail"
    if all(r == "skipped" for r in results):
        return "skipped"
    return "pass"


def _run_capability(repo_root, capability_id, cap_path, realizing, judge, test_author):
    scenarios = []
    if cap_path is not None:
        file_rel = cap_path.relative_to(repo_root).as_posix()
        for scenario in _parse_scenarios(cap_path.read_text(encoding="utf-8")):
            kind = scenario["kind"]
            entry = {"id": scenario["id"], "kind": kind}
            bundle = _scenario_bundle(capability_id, scenario, file_rel)
            if kind == "compiled":
                entry["result"] = _run_compiled(repo_root, capability_id, scenario, file_rel, realizing)
            elif kind == "generated-test":
                entry["result"] = _run_generated(repo_root, bundle, realizing, test_author)
            elif kind == "llm-judge":
                if judge is None:
                    entry["result"] = "skipped"
                else:
                    result, rationale = _judge_outcome(judge(bundle))
                    entry["result"] = result
                    entry["rationale"] = rationale
            else:
                entry["result"] = "fail"
            scenarios.append(entry)
    return {"overall": _overall(scenarios), "scenarios": scenarios}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    repo_root = Path(repo_root)
    components = _components(repo_root)
    capabilities = _capabilities(repo_root)
    report = {}
    for capability_id in _intersecting_capabilities(components, blast_radius):
        report[capability_id] = _run_capability(
            repo_root,
            capability_id,
            capabilities.get(capability_id),
            _realizing(components, capability_id),
            judge,
            test_author,
        )
    return report


# ---------------------------------------------------------------------------
# Provenance.
# ---------------------------------------------------------------------------

def _record_path(repo_root, capability_id):
    return repo_root / "verification" / "capabilities" / capability_id / ".provenance.json"


def _content_hash(cap_path, realizing):
    digest = hashlib.sha256()
    digest.update(cap_path.read_bytes() + b"\0")
    for comp in realizing:
        digest.update(comp["id"].encode("utf-8") + b"\0")
        for rel, path in _code_files(comp["code_dir"]):
            if path.name == ".provenance.json":
                continue
            digest.update(rel.encode("utf-8") + b"\0")
            digest.update(path.read_bytes() + b"\0")
    return "sha256:" + digest.hexdigest()


def _state(capability_id, repo_root):
    cap_path = _capabilities(repo_root).get(capability_id)
    if cap_path is None:
        raise UnknownCapabilityError(f"unknown capability: {capability_id}")
    realizing = _realizing(_components(repo_root), capability_id)
    return cap_path, realizing, _content_hash(cap_path, realizing)


def _check(repo_root, capability_id, content_hash):
    try:
        record = json.loads(_record_path(repo_root, capability_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record = None
    if (
        isinstance(record, dict)
        and record.get("gate_version") == GATE_VERSION
        and record.get("content_hash") == content_hash
    ):
        return {"hit": True, "capability_scenario_report": record.get("capability_scenario_report")}
    return {"hit": False, "capability_scenario_report": None}


def check_capability_provenance(capability_id, repo_root):
    repo_root = Path(repo_root)
    _, _, content_hash = _state(capability_id, repo_root)
    return _check(repo_root, capability_id, content_hash)


# ---------------------------------------------------------------------------
# Callables built by run_capability_gates.
# ---------------------------------------------------------------------------

def _make_test_author(repo_root, capability_id, cap_path, realizing, model, seed, llm_backend):
    def test_author(bundle):
        interface_parts = []
        for comp in realizing:
            interface_parts.append(f"## {comp['id']}")
            base = comp["spec_dir"] / "interface"
            for path in sorted(base.rglob("*.md"), key=lambda p: p.relative_to(base).as_posix()):
                interface_parts.append(path.read_text(encoding="utf-8"))
        glossary_path = repo_root / "specs" / "glossary.md"
        glossary = glossary_path.read_text(encoding="utf-8") if glossary_path.is_file() else ""
        criterion_bundle = {
            "component_id": f"capabilities/{capability_id}",
            "criterion_id": bundle["scenario_id"],
            "covers": bundle["covers"],
            "criterion_text": bundle["gherkin"],
            "requirement_text": cap_path.read_text(encoding="utf-8"),
            "interface": "\n".join(interface_parts),
            "glossary": glossary,
            "dependency_interfaces": {},
            "module_names": [comp["slug"].replace("-", "_") for comp in realizing],
        }
        module = _load(repo_root, _TEST_AUTHOR_DIR, "test_author")
        return module.author_test(
            criterion_bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    return test_author


def _unavailable(reason):
    return {"result": "fail", "rationale": f"judge unavailable: {reason}"}


def _make_judge(repo_root, realizing, model, llm_backend):
    def judge(bundle):
        lines = [
            "You are judging one product capability scenario against the real, "
            "fully assembled code of every component that realizes it.",
            f"Capability: {bundle['capability_id']}",
            f"Scenario: {bundle['scenario_id']}",
            f"Covers: {bundle['covers']}",
            "",
            "Scenario (Gherkin):",
            bundle["gherkin"],
            "",
            "Code of the realizing components:",
        ]
        for comp in realizing:
            for rel, path in _code_files(comp["code_dir"]):
                lines.append(f"===== {comp['id']}: {rel} =====")
                lines.append(path.read_text(encoding="utf-8", errors="replace"))
        lines.append("")
        lines.append(
            'Decide whether the code satisfies the scenario. Reply with JSON only: '
            '{"result": "pass" | "fail", "rationale": "..."}'
        )
        endpoint = _load(repo_root, _LLM_ENDPOINT_DIR, "llm_endpoint")
        response = endpoint.complete("\n".join(lines), model, backend=llm_backend)
        error = _get(response, "model_call_error")
        if error:
            return _unavailable(_get(error, "message"))
        text = str(_get(response, "text")).strip()
        fenced = _FENCED_REPLY.match(text)
        if fenced:
            text = fenced.group(1)
        try:
            parsed = json.loads(text)
        except ValueError:
            return _unavailable("unparseable reply")
        result = parsed.get("result") if isinstance(parsed, dict) else None
        if result not in ("pass", "fail"):
            return _unavailable(f"invalid result {result!r}")
        return {"result": result, "rationale": parsed.get("rationale", "")}

    return judge


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    repo_root = Path(repo_root)
    cap_path, realizing, content_hash = _state(capability_id, repo_root)
    checked = _check(repo_root, capability_id, content_hash)
    if checked["hit"]:
        return checked
    if model is None:
        raise ModelRequiredError("a model is required to run capability scenarios on a miss")
    judge = _make_judge(repo_root, realizing, model, llm_backend)
    test_author = _make_test_author(
        repo_root, capability_id, cap_path, realizing, model, seed, llm_backend
    )
    report = {
        capability_id: _run_capability(
            repo_root, capability_id, cap_path, realizing, judge, test_author
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
    _write(
        repo_root,
        _record_path(repo_root, capability_id).relative_to(repo_root).as_posix(),
        json.dumps(record, sort_keys=True, indent=2) + "\n",
    )
    return {"hit": False, "capability_scenario_report": report}
