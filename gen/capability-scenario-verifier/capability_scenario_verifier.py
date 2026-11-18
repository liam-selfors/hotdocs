"""Capability Scenario Verifier.

Runs the capability scenarios of every product capability whose
`realizes`-set intersects a blast radius, against the real assembled
code, and checks/writes per-capability provenance records.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

GATE_VERSION = "capability_scenario_verifier@2.0.0"

_PYTEST_TIMEOUT_SECONDS = 120
_COMPILER_DIR = "pipeline/criterion-compiler"
_TEST_AUTHOR_DIR = "gen/test-author"
_LLM_ENDPOINT_DIR = "gen/llm-endpoint"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Helpers: dual access, module loading
# ---------------------------------------------------------------------------


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


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


# ---------------------------------------------------------------------------
# Corpus parsing
# ---------------------------------------------------------------------------


def _scalar(value):
    if value.startswith("[") and value.endswith("]"):
        items = [item.strip().strip("'\"") for item in value[1:-1].split(",")]
        return [item for item in items if item]
    if value == "true":
        return True
    if value == "false":
        return False
    return value.strip("'\"")


def _frontmatter(text):
    lines = text.splitlines()
    fm = {}
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            key, sep, val = line.partition(":")
            if sep:
                fm[key.strip()] = _scalar(val.strip())
    return fm


def _components(repo_root):
    comps = []
    for cm in sorted((repo_root / "specs" / "components").glob("*/component.md")):
        fm = _frontmatter(cm.read_text(encoding="utf-8"))
        comp_id = fm["id"]
        slug = comp_id[len("comp-"):] if comp_id.startswith("comp-") else comp_id
        if fm.get("sealed") is True:
            code_dir = repo_root / fm["source_path"]
        else:
            code_dir = repo_root / "gen" / slug
        comps.append(
            {
                "id": comp_id,
                "slug": slug,
                "realizes": fm.get("realizes") or [],
                "code_dir": code_dir,
            }
        )
    return comps


def _capabilities(repo_root):
    caps = {}
    for path in sorted((repo_root / "specs" / "product").glob("*.md")):
        fm = _frontmatter(path.read_text(encoding="utf-8"))
        if "id" in fm:
            caps[fm["id"]] = path
    return caps


def _find_capability(capability_id, repo_root):
    caps = _capabilities(repo_root)
    if capability_id not in caps:
        raise UnknownCapabilityError(capability_id)
    return caps[capability_id]


def _realizing(capability_id, components):
    return sorted(
        (c for c in components if capability_id in c["realizes"]),
        key=lambda c: c["id"],
    )


def _scenarios(text):
    scenarios = []
    current = None
    in_gherkin = False
    for line in text.splitlines():
        stripped = line.strip()
        if current is not None and in_gherkin:
            if stripped.startswith("```"):
                in_gherkin = False
            else:
                current["gherkin_lines"].append(line)
            continue
        if stripped.startswith("### CS-"):
            current = {
                "id": stripped[4:].strip(),
                "covers": "",
                "kind": "",
                "gherkin_lines": [],
            }
            scenarios.append(current)
        elif stripped.startswith("## ") or stripped.startswith("### "):
            current = None
        elif current is not None:
            if stripped.startswith("Covers:"):
                current["covers"] = stripped[len("Covers:"):].strip().strip("`")
            elif stripped.startswith("Kind:"):
                current["kind"] = stripped[len("Kind:"):].strip().strip("`")
            elif stripped.startswith("```gherkin"):
                in_gherkin = True
    return [
        {
            "id": s["id"],
            "covers": s["covers"],
            "kind": s["kind"],
            "gherkin": "\n".join(s["gherkin_lines"]),
        }
        for s in scenarios
    ]


def _code_files(code_dir, skip_provenance):
    if not code_dir.is_dir():
        return []
    files = []
    for path in code_dir.rglob("*"):
        rel = path.relative_to(code_dir)
        if "__pycache__" in rel.parts or not path.is_file():
            continue
        if skip_provenance and path.name == ".provenance.json":
            continue
        files.append((rel.as_posix(), path))
    return sorted(files, key=lambda item: item[0])


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------


def _run_pytest(rel_path, repo_root, realizing):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(str(c["code_dir"]) for c in realizing)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(rel_path)],
            cwd=str(repo_root),
            env=env,
            timeout=_PYTEST_TIMEOUT_SECONDS,
            capture_output=True,
        )
    except (subprocess.TimeoutExpired, OSError):
        return "fail"
    return "pass" if proc.returncode == 0 else "fail"


def _write(repo_root, rel_path, content):
    target = repo_root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _run_compiled(capability_id, scenario, cap_rel_file, repo_root, realizing):
    compiler = _load("criterion_compiler", _COMPILER_DIR, repo_root)
    parsed = compiler.ParsedCriterion(
        criterion_id=scenario["id"],
        covers=scenario["covers"],
        kind=scenario["kind"],
        gherkin=scenario["gherkin"],
        file=cap_rel_file,
    )
    result = compiler.compile_criterion(parsed, surface=None)
    if _get(result, "status") == "error":
        return "fail"
    name = "test_" + scenario["id"].lower().replace("-", "_") + ".py"
    rel = Path("verification") / "capabilities" / capability_id / "compiled" / name
    _write(repo_root, rel, _get(result, "source"))
    return _run_pytest(rel, repo_root, realizing)


def _run_generated(bundle, test_author, repo_root, realizing):
    if test_author is None:
        return "fail"
    outcome = test_author(bundle)
    if _get(outcome, "model_call_error"):
        return "fail"
    file = _get(outcome, "file")
    if not file:
        return "fail"
    rel = Path(_get(file, "path"))
    if rel.is_absolute() or not rel.parts or rel.parts[0] != "verification" or ".." in rel.parts:
        return "fail"
    _write(repo_root, rel, _get(file, "content"))
    return _run_pytest(rel, repo_root, realizing)


def _run_capability(capability_id, cap_path, repo_root, realizing, judge, test_author):
    cap_rel_file = cap_path.relative_to(repo_root).as_posix()
    entries = []
    for scenario in _scenarios(cap_path.read_text(encoding="utf-8")):
        kind = scenario["kind"]
        entry = {"id": scenario["id"], "kind": kind}
        bundle = {
            "capability_id": capability_id,
            "scenario_id": scenario["id"],
            "covers": scenario["covers"],
            "kind": kind,
            "gherkin": scenario["gherkin"],
            "file": cap_rel_file,
        }
        if kind == "compiled":
            entry["result"] = _run_compiled(capability_id, scenario, cap_rel_file, repo_root, realizing)
        elif kind == "generated-test":
            entry["result"] = _run_generated(bundle, test_author, repo_root, realizing)
        elif judge is None:
            entry["result"] = "skipped"
        else:
            outcome = judge(bundle)
            if isinstance(outcome, dict):
                result = outcome.get("result", outcome.get("verdict"))
                rationale = outcome.get("rationale", "")
            else:
                result = outcome
                rationale = ""
            entry["result"] = result
            entry["rationale"] = rationale
        entries.append(entry)
    results = [e["result"] for e in entries]
    if "fail" in results or not results:
        overall = "fail"
    elif all(r == "skipped" for r in results):
        overall = "skipped"
    else:
        overall = "pass"
    return {"overall": overall, "scenarios": entries}


# ---------------------------------------------------------------------------
# Public: run scenarios for a blast radius
# ---------------------------------------------------------------------------


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    repo_root = Path(repo_root)
    components = _components(repo_root)
    radius = set(blast_radius)
    targets = sorted(
        {cap for c in components if c["id"] in radius for cap in c["realizes"]}
    )
    caps = _capabilities(repo_root)
    report = {}
    for capability_id in targets:
        report[capability_id] = _run_capability(
            capability_id,
            caps[capability_id],
            repo_root,
            _realizing(capability_id, components),
            judge,
            test_author,
        )
    return report


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def _content_hash(cap_path, realizing):
    h = hashlib.sha256()
    h.update(cap_path.read_bytes() + b"\0")
    for comp in realizing:
        h.update(comp["id"].encode("utf-8") + b"\0")
        for rel, path in _code_files(comp["code_dir"], skip_provenance=True):
            h.update(rel.encode("utf-8") + b"\0")
            h.update(path.read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()


def _record_path(capability_id, repo_root):
    return repo_root / "verification" / "capabilities" / capability_id / ".provenance.json"


def check_capability_provenance(capability_id, repo_root):
    repo_root = Path(repo_root)
    cap_path = _find_capability(capability_id, repo_root)
    realizing = _realizing(capability_id, _components(repo_root))
    current = _content_hash(cap_path, realizing)
    try:
        record = json.loads(_record_path(capability_id, repo_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"hit": False, "capability_scenario_report": None}
    if (
        isinstance(record, dict)
        and record.get("gate_version") == GATE_VERSION
        and record.get("content_hash") == current
    ):
        return {"hit": True, "capability_scenario_report": record.get("capability_scenario_report")}
    return {"hit": False, "capability_scenario_report": None}


# ---------------------------------------------------------------------------
# Callables built by run_capability_gates
# ---------------------------------------------------------------------------


def _make_test_author(capability_id, cap_path, realizing, repo_root, model, seed, llm_backend):
    def _test_author(bundle):
        module = _load("test_author", _TEST_AUTHOR_DIR, repo_root)
        interface_parts = []
        for comp in realizing:
            interface_parts.append(f"## {comp['id']}")
            iface_dir = repo_root / "specs" / "components" / comp["slug"] / "interface"
            for md in sorted(iface_dir.rglob("*.md")):
                interface_parts.append(md.read_text(encoding="utf-8"))
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
            "module_names": [c["slug"].replace("-", "_") for c in realizing],
        }
        return module.author_test(
            criterion_bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    return _test_author


def _unfence(text):
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines)
    return stripped


def _make_judge(realizing, repo_root, model, llm_backend):
    def _judge(bundle):
        module = _load("llm_endpoint", _LLM_ENDPOINT_DIR, repo_root)
        parts = [
            "You are judging whether a product capability scenario is satisfied "
            "by the code below.",
            f"Covers: {bundle['covers']}",
            "Scenario (Gherkin):",
            bundle["gherkin"],
            "",
            "Code of every realizing component:",
        ]
        for comp in realizing:
            parts.append(f"## {comp['id']}")
            for rel, path in _code_files(comp["code_dir"], skip_provenance=False):
                parts.append(f"### {rel}")
                parts.append(path.read_text(encoding="utf-8", errors="replace"))
        parts.append("")
        parts.append(
            'Reply with JSON only: {"result": "pass" | "fail", "rationale": "..."}'
        )
        response = module.complete("\n".join(parts), model, backend=llm_backend)
        error = _get(response, "model_call_error")
        if error:
            return {"result": "fail", "rationale": f"judge unavailable: {_get(error, 'message')}"}
        try:
            parsed = json.loads(_unfence(_get(response, "text")))
        except (TypeError, ValueError):
            return {"result": "fail", "rationale": "judge unavailable: unparseable reply"}
        result = _get(parsed, "result")
        if result not in ("pass", "fail"):
            return {"result": "fail", "rationale": f"judge unavailable: invalid result {result!r}"}
        return {"result": result, "rationale": _get(parsed, "rationale")}

    return _judge


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    repo_root = Path(repo_root)
    checked = check_capability_provenance(capability_id, repo_root)
    if checked["hit"]:
        return checked
    if model is None:
        raise ModelRequiredError(f"a model is required to run capability {capability_id}")
    cap_path = _find_capability(capability_id, repo_root)
    realizing = _realizing(capability_id, _components(repo_root))
    content_hash = _content_hash(cap_path, realizing)
    report = {
        capability_id: _run_capability(
            capability_id,
            cap_path,
            repo_root,
            realizing,
            _make_judge(realizing, repo_root, model, llm_backend),
            _make_test_author(capability_id, cap_path, realizing, repo_root, model, seed, llm_backend),
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
    path.write_text(json.dumps(record, sort_keys=True, indent=2), encoding="utf-8")
    return {"hit": False, "capability_scenario_report": report}
