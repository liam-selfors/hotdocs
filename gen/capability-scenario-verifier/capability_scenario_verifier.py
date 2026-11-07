"""capability-scenario-verifier: runs product-capability scenarios against
real, assembled gen/ output for every capability whose realizes-set
intersects a merge's blast radius."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

GATE_VERSION = "capability_scenario_verifier@2.0.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


_DEPENDENCY_CACHE = {}


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _load_dependency(repo_root, base_dir, module_name):
    repo_root = Path(repo_root)
    cache_key = (str(repo_root.resolve()), base_dir, module_name)
    cached = _DEPENDENCY_CACHE.get(cache_key)
    if cached is not None:
        return cached
    base = repo_root / base_dir
    flat_path = base / f"{module_name}.py"
    pkg_path = base / module_name / "__init__.py"
    if flat_path.is_file():
        load_path = flat_path
        search_locations = None
    elif pkg_path.is_file():
        load_path = pkg_path
        search_locations = [str(pkg_path.parent)]
    else:
        raise ImportError(f"cannot locate module '{module_name}' under {base}")
    unique_name = f"_csv_dep__{module_name}__{abs(hash(cache_key))}"
    spec = importlib.util.spec_from_file_location(
        unique_name, load_path, submodule_search_locations=search_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    _DEPENDENCY_CACHE[cache_key] = module
    return module


def _load_criterion_compiler(repo_root):
    return _load_dependency(repo_root, "pipeline/criterion-compiler", "criterion_compiler")


def _load_test_author(repo_root):
    return _load_dependency(repo_root, "gen/test-author", "test_author")


def _load_llm_endpoint(repo_root):
    return _load_dependency(repo_root, "gen/llm-endpoint", "llm_endpoint")


def _parse_frontmatter(text):
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    data = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            items = []
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith("-"):
                items.append(lines[j].strip()[1:].strip())
                j += 1
            if items:
                data[key] = items
                i = j
                continue
            data[key] = None
            i += 1
            continue
        if rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1]
            data[key] = [x.strip() for x in inner.split(",") if x.strip()]
            i += 1
            continue
        val = rest
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        if val == "true":
            val = True
        elif val == "false":
            val = False
        data[key] = val
        i += 1
    return data


def _load_components(repo_root):
    repo_root = Path(repo_root)
    components_dir = repo_root / "specs" / "components"
    components = []
    if not components_dir.is_dir():
        return components
    for comp_md in sorted(components_dir.glob("*/component.md")):
        text = comp_md.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        comp_id = fm.get("id")
        if not comp_id:
            continue
        realizes = fm.get("realizes") or []
        if isinstance(realizes, str):
            realizes = [realizes]
        sealed = bool(fm.get("sealed")) if fm.get("sealed") is not None else False
        source_path = fm.get("source_path")
        components.append(
            {
                "id": comp_id,
                "realizes": realizes,
                "sealed": sealed,
                "source_path": source_path,
            }
        )
    return components


def _slug(component_id):
    return component_id[len("comp-") :] if component_id.startswith("comp-") else component_id


def _code_dir(repo_root, comp):
    repo_root = Path(repo_root)
    if comp.get("sealed"):
        return repo_root / (comp.get("source_path") or "")
    return repo_root / "gen" / _slug(comp["id"])


def _find_capability_file(repo_root, capability_id):
    repo_root = Path(repo_root)
    product_dir = repo_root / "specs" / "product"
    if not product_dir.is_dir():
        return None
    for p in sorted(product_dir.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        if fm.get("id") == capability_id:
            return p
    return None


def _parse_capability_scenarios(text):
    import re

    body = text
    if body.startswith("---"):
        end = body.find("\n---", 3)
        if end != -1:
            body = body[end + 4 :]
    pattern = re.compile(r"^### (CS-\S+)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(body))
    scenarios = []
    for idx, m in enumerate(matches):
        scenario_id = m.group(1)
        start = m.end()
        stop = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        section = body[start:stop]
        covers_m = re.search(r"^Covers:\s*(.+)$", section, re.MULTILINE)
        kind_m = re.search(r"^Kind:\s*(.+)$", section, re.MULTILINE)
        gherkin_m = re.search(r"```[a-zA-Z]*\n(.*?)```", section, re.DOTALL)
        scenarios.append(
            {
                "id": scenario_id,
                "covers": covers_m.group(1).strip() if covers_m else "",
                "kind": kind_m.group(1).strip() if kind_m else "",
                "gherkin": gherkin_m.group(1).strip() if gherkin_m else "",
            }
        )
    return scenarios


def _iter_regular_files(code_dir):
    results = []
    for p in code_dir.rglob("*"):
        if p.is_dir():
            continue
        if "__pycache__" in p.parts:
            continue
        if p.name == ".provenance.json":
            continue
        rel = p.relative_to(code_dir).as_posix()
        results.append((rel, p))
    results.sort(key=lambda x: x[0])
    return results


def _content_hash(repo_root, cap_file, realizing_components):
    h = hashlib.sha256()
    h.update(cap_file.read_bytes())
    h.update(b"\0")
    for comp in sorted(realizing_components, key=lambda c: c["id"]):
        h.update(comp["id"].encode("utf-8"))
        h.update(b"\0")
        code_dir = _code_dir(repo_root, comp)
        if code_dir.is_dir():
            for rel_path, abs_path in _iter_regular_files(code_dir):
                h.update(rel_path.encode("utf-8"))
                h.update(b"\0")
                h.update(abs_path.read_bytes())
                h.update(b"\0")
    return "sha256:" + h.hexdigest()


def _read_record(path):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _record_path(repo_root, capability_id):
    return Path(repo_root) / "verification" / "capabilities" / capability_id / ".provenance.json"


def check_capability_provenance(capability_id, repo_root):
    repo_root = Path(repo_root)
    cap_file = _find_capability_file(repo_root, capability_id)
    if cap_file is None:
        raise UnknownCapabilityError(capability_id)
    components = _load_components(repo_root)
    realizing = [c for c in components if capability_id in c.get("realizes", [])]
    content_hash = _content_hash(repo_root, cap_file, realizing)
    record = _read_record(_record_path(repo_root, capability_id))
    if record is None:
        return {"hit": False, "capability_scenario_report": None}
    gate_version = _get(record, "gate_version")
    recorded_hash = _get(record, "content_hash")
    if gate_version == GATE_VERSION and recorded_hash == content_hash:
        return {"hit": True, "capability_scenario_report": _get(record, "capability_scenario_report")}
    return {"hit": False, "capability_scenario_report": None}


def _test_filename(scenario_id):
    return f"test_{scenario_id.lower().replace('-', '_')}.py"


def _build_pythonpath(repo_root, realizing):
    return os.pathsep.join(str(_code_dir(repo_root, comp)) for comp in realizing)


def _run_pytest(repo_root, test_path, pythonpath):
    env = dict(os.environ)
    env["PYTHONPATH"] = pythonpath
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(test_path)],
            cwd=str(repo_root),
            env=env,
            timeout=120,
            capture_output=True,
        )
    except (subprocess.TimeoutExpired, OSError):
        return "fail"
    return "pass" if proc.returncode == 0 else "fail"


def _valid_verification_path(path):
    if not path or not isinstance(path, str):
        return False
    if path.startswith("/"):
        return False
    posix = PurePosixPath(path)
    if posix.is_absolute():
        return False
    if ".." in posix.parts:
        return False
    if not posix.parts or posix.parts[0] != "verification":
        return False
    return True


def _run_compiled_scenario(cap_id, scenario, rel_cap_file, realizing, repo_root):
    try:
        criterion_compiler = _load_criterion_compiler(repo_root)
    except ImportError:
        return {"result": "fail"}
    parsed = criterion_compiler.ParsedCriterion(
        criterion_id=scenario["id"],
        covers=scenario["covers"],
        kind="compiled",
        gherkin=scenario["gherkin"],
        file=rel_cap_file,
    )
    outcome = criterion_compiler.compile_criterion(parsed, surface=None)
    status = _get(outcome, "status")
    if status != "compiled":
        return {"result": "fail"}
    source = _get(outcome, "source")
    test_path = (
        Path(repo_root)
        / "verification"
        / "capabilities"
        / cap_id
        / "compiled"
        / _test_filename(scenario["id"])
    )
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(source or "", encoding="utf-8")
    pythonpath = _build_pythonpath(repo_root, realizing)
    return {"result": _run_pytest(repo_root, test_path, pythonpath)}


def _run_generated_test_scenario(cap_id, scenario, rel_cap_file, realizing, repo_root, test_author):
    if test_author is None:
        return {"result": "fail"}
    bundle = {
        "capability_id": cap_id,
        "scenario_id": scenario["id"],
        "covers": scenario["covers"],
        "kind": "generated-test",
        "gherkin": scenario["gherkin"],
        "file": rel_cap_file,
    }
    outcome = test_author(bundle)
    model_call_error = _get(outcome, "model_call_error")
    file_obj = _get(outcome, "file")
    if model_call_error or file_obj is None:
        return {"result": "fail"}
    path = _get(file_obj, "path")
    content = _get(file_obj, "content")
    if not _valid_verification_path(path):
        return {"result": "fail"}
    test_path = Path(repo_root) / path
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(content or "", encoding="utf-8")
    pythonpath = _build_pythonpath(repo_root, realizing)
    return {"result": _run_pytest(repo_root, test_path, pythonpath)}


def _run_judge_scenario(cap_id, scenario, rel_cap_file, realizing, repo_root, judge):
    if judge is None:
        return {"result": "skipped"}
    bundle = {
        "capability_id": cap_id,
        "scenario_id": scenario["id"],
        "covers": scenario["covers"],
        "kind": "llm-judge",
        "gherkin": scenario["gherkin"],
        "file": rel_cap_file,
    }
    outcome = judge(bundle)
    if isinstance(outcome, dict):
        result_value = outcome.get("result", outcome.get("verdict"))
        rationale = outcome.get("rationale")
    elif hasattr(outcome, "result") or hasattr(outcome, "verdict"):
        result_value = getattr(outcome, "result", None)
        if result_value is None:
            result_value = getattr(outcome, "verdict", None)
        rationale = getattr(outcome, "rationale", None)
    else:
        result_value = outcome
        rationale = None
    result = "pass" if result_value == "pass" else "fail"
    return {"result": result, "rationale": rationale}


def _run_scenario(cap_id, scenario, rel_cap_file, realizing, repo_root, judge, test_author):
    kind = scenario["kind"]
    if kind == "compiled":
        outcome = _run_compiled_scenario(cap_id, scenario, rel_cap_file, realizing, repo_root)
    elif kind == "generated-test":
        outcome = _run_generated_test_scenario(cap_id, scenario, rel_cap_file, realizing, repo_root, test_author)
    elif kind == "llm-judge":
        outcome = _run_judge_scenario(cap_id, scenario, rel_cap_file, realizing, repo_root, judge)
    else:
        outcome = {"result": "fail"}
    entry = {"id": scenario["id"], "kind": kind, "result": outcome["result"]}
    if "rationale" in outcome:
        entry["rationale"] = outcome["rationale"]
    return entry


def _aggregate_overall(scenario_results):
    if not scenario_results:
        return "fail"
    if any(s["result"] == "fail" for s in scenario_results):
        return "fail"
    if all(s["result"] == "skipped" for s in scenario_results):
        return "skipped"
    return "pass"


def _compute_capability_report(cap_id, repo_root, components, judge, test_author):
    cap_file = _find_capability_file(repo_root, cap_id)
    if cap_file is None:
        raise UnknownCapabilityError(cap_id)
    text = cap_file.read_text(encoding="utf-8")
    scenarios = _parse_capability_scenarios(text)
    realizing = sorted(
        (c for c in components if cap_id in c.get("realizes", [])), key=lambda c: c["id"]
    )
    rel_cap_file = str(cap_file.relative_to(Path(repo_root)))
    scenario_results = [
        _run_scenario(cap_id, sc, rel_cap_file, realizing, repo_root, judge, test_author)
        for sc in scenarios
    ]
    return {"overall": _aggregate_overall(scenario_results), "scenarios": scenario_results}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    repo_root = Path(repo_root)
    components = _load_components(repo_root)
    blast_set = set(blast_radius)
    capability_ids = sorted(
        {
            cap
            for comp in components
            if comp["id"] in blast_set
            for cap in comp.get("realizes", [])
        }
    )
    report = {}
    for cap_id in capability_ids:
        report[cap_id] = _compute_capability_report(cap_id, repo_root, components, judge, test_author)
    return report


def _build_criterion_bundle(repo_root, scenario_bundle):
    repo_root = Path(repo_root)
    capability_id = scenario_bundle["capability_id"]
    components = _load_components(repo_root)
    cap_file = _find_capability_file(repo_root, capability_id)
    requirement_text = cap_file.read_text(encoding="utf-8") if cap_file else ""
    realizing = sorted(
        (c for c in components if capability_id in c.get("realizes", [])), key=lambda c: c["id"]
    )
    interface_parts = []
    for comp in realizing:
        slug = _slug(comp["id"])
        interface_dir = repo_root / "specs" / "components" / slug / "interface"
        interface_parts.append(f"## {comp['id']}")
        if interface_dir.is_dir():
            for md in sorted(interface_dir.rglob("*.md")):
                interface_parts.append(md.read_text(encoding="utf-8"))
    glossary_path = repo_root / "specs" / "glossary.md"
    glossary_text = glossary_path.read_text(encoding="utf-8") if glossary_path.is_file() else ""
    module_names = [_slug(c["id"]).replace("-", "_") for c in realizing]
    return {
        "component_id": f"capabilities/{capability_id}",
        "criterion_id": scenario_bundle["scenario_id"],
        "covers": scenario_bundle["covers"],
        "criterion_text": scenario_bundle["gherkin"],
        "requirement_text": requirement_text,
        "interface": "\n\n".join(interface_parts),
        "glossary": glossary_text,
        "dependency_interfaces": {},
        "module_names": module_names,
    }


def _build_test_author_callable(repo_root, model, seed, llm_backend):
    def _call(bundle):
        test_author_module = _load_test_author(repo_root)
        criterion_bundle = _build_criterion_bundle(repo_root, bundle)
        return test_author_module.author_test(
            criterion_bundle, model, seed=seed, repo_root=Path(repo_root), llm_backend=llm_backend
        )

    return _call


def _parse_judge_reply(text):
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _build_judge_callable(repo_root, model, llm_backend):
    def _call(bundle):
        try:
            repo_root_path = Path(repo_root)
            llm_endpoint_module = _load_llm_endpoint(repo_root_path)
            capability_id = bundle["capability_id"]
            components = _load_components(repo_root_path)
            realizing = sorted(
                (c for c in components if capability_id in c.get("realizes", [])),
                key=lambda c: c["id"],
            )
            code_sections = []
            for comp in realizing:
                code_dir = _code_dir(repo_root_path, comp)
                if not code_dir.is_dir():
                    continue
                for rel_path, abs_path in _iter_regular_files(code_dir):
                    try:
                        content = abs_path.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        continue
                    code_sections.append(f"## {comp['id']}/{rel_path}\n{content}")
            prompt = (
                f"Scenario: {bundle['scenario_id']}\n"
                f"Covers: {bundle['covers']}\n\n"
                f"{bundle['gherkin']}\n\n"
                "Code under test:\n" + "\n\n".join(code_sections) + "\n\n"
                'Respond with JSON {"result": "pass" | "fail", "rationale": "..."}'
            )
            outcome = llm_endpoint_module.complete(prompt, model, backend=llm_backend)
            model_call_error = _get(outcome, "model_call_error")
            if model_call_error:
                message = _get(model_call_error, "message", str(model_call_error))
                return {"result": "fail", "rationale": f"judge unavailable: {message}"}
            text = _get(outcome, "text")
            parsed = _parse_judge_reply(text)
            if parsed is None:
                return {"result": "fail", "rationale": "judge unavailable: unparseable reply"}
            result = parsed.get("result")
            if result not in ("pass", "fail"):
                return {"result": "fail", "rationale": f"judge unavailable: invalid result {result!r}"}
            return {"result": result, "rationale": parsed.get("rationale")}
        except Exception as exc:  # noqa: BLE001 - never raised outward (R-SCENARIO-008)
            return {"result": "fail", "rationale": f"judge unavailable: {exc}"}

    return _call


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    repo_root = Path(repo_root)
    check = check_capability_provenance(capability_id, repo_root)
    if check["hit"]:
        return check
    if model is None:
        raise ModelRequiredError(capability_id)
    judge = _build_judge_callable(repo_root, model, llm_backend)
    test_author_callable = _build_test_author_callable(repo_root, model, seed, llm_backend)
    components = _load_components(repo_root)
    cap_report = _compute_capability_report(capability_id, repo_root, components, judge, test_author_callable)
    full_report = {capability_id: cap_report}
    cap_file = _find_capability_file(repo_root, capability_id)
    realizing = [c for c in components if capability_id in c.get("realizes", [])]
    content_hash = _content_hash(repo_root, cap_file, realizing)
    record = {
        "capability_id": capability_id,
        "gate_version": GATE_VERSION,
        "content_hash": content_hash,
        "realizing_components": sorted(c["id"] for c in realizing),
        "capability_scenario_report": full_report,
        "model": model,
        "seed": seed,
    }
    record_path = _record_path(repo_root, capability_id)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, sort_keys=True, indent=2), encoding="utf-8")
    return {"hit": False, "capability_scenario_report": full_report}