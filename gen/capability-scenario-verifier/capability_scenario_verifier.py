import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

GATE_VERSION = "capability_scenario_verifier@2.0.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _strip_quotes(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def _parse_frontmatter_block(fm_text):
    data = {}
    lines = fm_text.split("\n")
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == "":
            items = []
            j = i + 1
            while j < n:
                item_m = re.match(r"^\s*-\s*(.+)$", lines[j])
                if not item_m:
                    break
                items.append(_strip_quotes(item_m.group(1)))
                j += 1
            if items:
                data[key] = items
                i = j
                continue
            data[key] = None
            i += 1
            continue
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            data[key] = [_strip_quotes(x) for x in inner.split(",") if x.strip()] if inner else []
        elif val.lower() in ("true", "false"):
            data[key] = val.lower() == "true"
        else:
            data[key] = _strip_quotes(val)
        i += 1
    return data


def _parse_frontmatter(text):
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    return _parse_frontmatter_block(m.group(1)), text[m.end():]


def _scan_components(repo_root):
    components = []
    comp_dir = repo_root / "specs" / "components"
    if not comp_dir.is_dir():
        return components
    for sub in sorted(comp_dir.iterdir()):
        comp_md = sub / "component.md"
        if not comp_md.is_file():
            continue
        text = comp_md.read_text(encoding="utf-8")
        fm, _ = _parse_frontmatter(text)
        comp_id = fm.get("id")
        if not comp_id:
            continue
        realizes = fm.get("realizes") or []
        if isinstance(realizes, str):
            realizes = [realizes]
        slug = comp_id[len("comp-"):] if comp_id.startswith("comp-") else sub.name
        components.append({
            "id": comp_id,
            "slug": slug,
            "realizes": realizes,
            "sealed": bool(fm.get("sealed")),
            "source_path": fm.get("source_path"),
        })
    return components


def _find_capability_spec(repo_root, capability_id):
    product_dir = repo_root / "specs" / "product"
    if not product_dir.is_dir():
        return None
    for f in sorted(product_dir.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        fm, body = _parse_frontmatter(text)
        if fm.get("id") == capability_id:
            return {"path": f, "text": text, "frontmatter": fm, "body": body}
    return None


def _code_dir(component, repo_root):
    if component.get("sealed"):
        source_path = component.get("source_path")
        if not source_path:
            return None
        return repo_root / source_path
    return repo_root / "gen" / component["slug"]


def _capabilities_in_blast_radius(components, blast_radius):
    blast_set = set(blast_radius)
    found = set()
    for c in components:
        if c["id"] in blast_set:
            for cap_id in c["realizes"]:
                found.add(cap_id)
    return sorted(found)


def _realizing_set(components, capability_id):
    return sorted(
        (c for c in components if capability_id in c["realizes"]),
        key=lambda c: c["id"],
    )


_CS_HEADER_RE = re.compile(r"^###\s+(CS-\S+)\s*$", re.MULTILINE)
_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def _extract_field(block, field_name):
    m = re.search(r"^" + field_name + r":\s*(.+)$", block, re.MULTILINE)
    return m.group(1).strip() if m else None


def _extract_fenced_block(block):
    m = _FENCE_RE.search(block)
    return m.group(1).strip() if m else ""


def _parse_capability_scenarios(body_text):
    scenarios = []
    headers = list(_CS_HEADER_RE.finditer(body_text))
    for i, m in enumerate(headers):
        scenario_id = m.group(1)
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body_text)
        block = body_text[start:end]
        scenarios.append({
            "id": scenario_id,
            "covers": _extract_field(block, "Covers"),
            "kind": _extract_field(block, "Kind"),
            "gherkin": _extract_fenced_block(block),
        })
    return scenarios


def _scenario_bundle(capability_id, scenario, file_rel_path):
    return {
        "capability_id": capability_id,
        "scenario_id": scenario["id"],
        "covers": scenario["covers"],
        "kind": scenario["kind"],
        "gherkin": scenario["gherkin"],
        "file": file_rel_path,
    }


def _load_module(repo_root, dir_rel_path, module_name):
    base = Path(repo_root) / dir_rel_path
    flat = base / (module_name + ".py")
    pkg_init = base / module_name / "__init__.py"
    if flat.is_file():
        file_path = flat
        submodule_locations = None
    elif pkg_init.is_file():
        file_path = pkg_init
        submodule_locations = [str(base / module_name)]
    else:
        raise ModuleNotFoundError("cannot find module {} under {}".format(module_name, base))
    spec = importlib.util.spec_from_file_location(
        module_name, file_path, submodule_search_locations=submodule_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_criterion_compiler(repo_root):
    return _load_module(repo_root, "pipeline/criterion-compiler", "criterion_compiler")


def _load_test_author(repo_root):
    return _load_module(repo_root, "gen/test-author", "test_author")


def _load_llm_endpoint(repo_root):
    return _load_module(repo_root, "gen/llm-endpoint", "llm_endpoint")


def _pythonpath_for(realizing_components, repo_root):
    paths = []
    for c in realizing_components:
        code_dir = _code_dir(c, repo_root)
        if code_dir is not None:
            paths.append(str(code_dir))
    return os.pathsep.join(paths)


def _write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_pytest(repo_root, test_path, realizing_components):
    env = dict(os.environ)
    env["PYTHONPATH"] = _pythonpath_for(realizing_components, repo_root)
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(test_path)]
    try:
        proc = subprocess.run(
            cmd, cwd=str(repo_root), env=env, timeout=120,
            capture_output=True,
        )
    except Exception:
        return "fail"
    return "pass" if proc.returncode == 0 else "fail"


def _compiled_test_path(repo_root, capability_id, scenario_id):
    name = "test_" + scenario_id.lower().replace("-", "_") + ".py"
    return repo_root / "verification" / "capabilities" / capability_id / "compiled" / name


def _validate_generated_path(path_str):
    if not path_str:
        return False
    norm = path_str.replace("\\", "/")
    if norm.startswith("/"):
        return False
    parts = norm.split("/")
    if ".." in parts:
        return False
    if parts[0] != "verification":
        return False
    return True


def _dispatch_compiled(repo_root, capability_id, scenario, file_rel_path, realizing_components):
    compiler = _load_criterion_compiler(repo_root)
    parsed = compiler.ParsedCriterion(
        criterion_id=scenario["id"],
        covers=scenario["covers"],
        kind=scenario["kind"],
        gherkin=scenario["gherkin"],
        file=file_rel_path or "",
    )
    result = compiler.compile_criterion(parsed, surface=None)
    status = _get(result, "status")
    if status != "compiled":
        return {"id": scenario["id"], "kind": scenario["kind"], "result": "fail"}
    source = _get(result, "source")
    test_path = _compiled_test_path(repo_root, capability_id, scenario["id"])
    _write_file(test_path, source)
    outcome = _run_pytest(repo_root, test_path, realizing_components)
    return {"id": scenario["id"], "kind": scenario["kind"], "result": outcome}


def _dispatch_generated_test(repo_root, scenario, bundle, test_author_callable, realizing_components):
    if test_author_callable is None:
        return {"id": scenario["id"], "kind": scenario["kind"], "result": "fail"}
    outcome = test_author_callable(bundle)
    model_call_error = _get(outcome, "model_call_error")
    file_obj = _get(outcome, "file")
    if model_call_error or not file_obj:
        return {"id": scenario["id"], "kind": scenario["kind"], "result": "fail"}
    path_str = _get(file_obj, "path")
    content = _get(file_obj, "content")
    if not _validate_generated_path(path_str):
        return {"id": scenario["id"], "kind": scenario["kind"], "result": "fail"}
    test_path = repo_root / path_str
    _write_file(test_path, content)
    result = _run_pytest(repo_root, test_path, realizing_components)
    return {"id": scenario["id"], "kind": scenario["kind"], "result": result}


def _parse_judge_outcome(outcome):
    if isinstance(outcome, dict):
        result = outcome.get("result", outcome.get("verdict"))
        rationale = outcome.get("rationale", "")
    elif hasattr(outcome, "result") or hasattr(outcome, "verdict"):
        result = getattr(outcome, "result", None)
        if result is None:
            result = getattr(outcome, "verdict", None)
        rationale = getattr(outcome, "rationale", "")
    else:
        result = outcome
        rationale = ""
    if result not in ("pass", "fail"):
        result = "fail"
    return result, rationale


def _dispatch_llm_judge(scenario, bundle, judge_callable):
    if judge_callable is None:
        return {"id": scenario["id"], "kind": scenario["kind"], "result": "skipped"}
    outcome = judge_callable(bundle)
    result, rationale = _parse_judge_outcome(outcome)
    return {"id": scenario["id"], "kind": scenario["kind"], "result": result, "rationale": rationale}


def _aggregate_overall(scenario_results):
    if not scenario_results:
        return "fail"
    if any(s["result"] == "fail" for s in scenario_results):
        return "fail"
    if all(s["result"] == "skipped" for s in scenario_results):
        return "skipped"
    return "pass"


def _run_one_capability(capability_id, components, repo_root, judge, test_author):
    realizing = _realizing_set(components, capability_id)
    spec = _find_capability_spec(repo_root, capability_id)
    scenarios = []
    file_rel_path = None
    if spec is not None:
        file_rel_path = str(spec["path"].relative_to(repo_root))
        scenarios = _parse_capability_scenarios(spec["body"])
    results = []
    for scenario in scenarios:
        bundle = _scenario_bundle(capability_id, scenario, file_rel_path)
        kind = scenario["kind"]
        if kind == "compiled":
            entry = _dispatch_compiled(repo_root, capability_id, scenario, file_rel_path, realizing)
        elif kind == "generated-test":
            entry = _dispatch_generated_test(repo_root, scenario, bundle, test_author, realizing)
        elif kind == "llm-judge":
            entry = _dispatch_llm_judge(scenario, bundle, judge)
        else:
            entry = {"id": scenario["id"], "kind": kind, "result": "fail"}
        results.append(entry)
    return {"overall": _aggregate_overall(results), "scenarios": results}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    repo_root = Path(repo_root)
    components = _scan_components(repo_root)
    capability_ids = _capabilities_in_blast_radius(components, blast_radius)
    report = {}
    for capability_id in capability_ids:
        report[capability_id] = _run_one_capability(capability_id, components, repo_root, judge, test_author)
    return report


def _sorted_code_files(code_dir):
    paths = []
    for p in code_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.name == ".provenance.json":
            continue
        if "__pycache__" in p.parts:
            continue
        paths.append(str(p.relative_to(code_dir).as_posix()))
    return sorted(paths)


def _code_files_skip_pycache(code_dir):
    paths = []
    for p in code_dir.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts:
            paths.append(str(p.relative_to(code_dir).as_posix()))
    return sorted(paths)


def _compute_content_hash(repo_root, capability_file_path, realizing_components):
    h = hashlib.sha256()
    h.update(capability_file_path.read_bytes())
    h.update(b"\0")
    for component in sorted(realizing_components, key=lambda c: c["id"]):
        h.update(component["id"].encode("utf-8"))
        h.update(b"\0")
        code_dir = _code_dir(component, repo_root)
        if code_dir is not None and code_dir.is_dir():
            for rel_path in _sorted_code_files(code_dir):
                h.update(rel_path.encode("utf-8"))
                h.update(b"\0")
                h.update((code_dir / rel_path).read_bytes())
                h.update(b"\0")
    return "sha256:" + h.hexdigest()


def _provenance_record_path(repo_root, capability_id):
    return Path(repo_root) / "verification" / "capabilities" / capability_id / ".provenance.json"


def _read_provenance_record(path):
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _write_provenance_record(repo_root, capability_id, record):
    path = _provenance_record_path(repo_root, capability_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(record, f, sort_keys=True, indent=2)


def check_capability_provenance(capability_id, repo_root):
    repo_root = Path(repo_root)
    components = _scan_components(repo_root)
    spec = _find_capability_spec(repo_root, capability_id)
    if spec is None:
        raise UnknownCapabilityError(capability_id)
    realizing = _realizing_set(components, capability_id)
    content_hash = _compute_content_hash(repo_root, spec["path"], realizing)
    record = _read_provenance_record(_provenance_record_path(repo_root, capability_id))
    if record is None:
        return {"hit": False, "capability_scenario_report": None}
    if record.get("gate_version") != GATE_VERSION:
        return {"hit": False, "capability_scenario_report": None}
    if record.get("content_hash") != content_hash:
        return {"hit": False, "capability_scenario_report": None}
    return {"hit": True, "capability_scenario_report": record.get("capability_scenario_report")}


def _build_author_criterion_bundle(repo_root, bundle):
    capability_id = bundle["capability_id"]
    components = _scan_components(repo_root)
    realizing = _realizing_set(components, capability_id)
    spec = _find_capability_spec(repo_root, capability_id)
    requirement_text = spec["text"] if spec else ""
    interface_parts = []
    for c in realizing:
        interface_parts.append("## " + c["id"])
        interface_dir = repo_root / "specs" / "components" / c["slug"] / "interface"
        if interface_dir.is_dir():
            md_files = sorted(
                interface_dir.rglob("*.md"),
                key=lambda p: str(p.relative_to(interface_dir).as_posix()),
            )
            for md_path in md_files:
                interface_parts.append(md_path.read_text(encoding="utf-8"))
    glossary_path = repo_root / "specs" / "glossary.md"
    glossary_text = glossary_path.read_text(encoding="utf-8") if glossary_path.is_file() else ""
    return {
        "component_id": "capabilities/" + capability_id,
        "criterion_id": bundle["scenario_id"],
        "covers": bundle["covers"],
        "criterion_text": bundle["gherkin"],
        "requirement_text": requirement_text,
        "interface": "\n".join(interface_parts),
        "glossary": glossary_text,
        "dependency_interfaces": {},
    }


def _build_test_author(repo_root, model, seed, llm_backend):
    def _callable(bundle):
        module = _load_test_author(repo_root)
        criterion_bundle = _build_author_criterion_bundle(repo_root, bundle)
        return module.author_test(
            criterion_bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )
    return _callable


def _build_judge_prompt(repo_root, bundle, realizing):
    parts = [
        "Covers: " + str(bundle.get("covers")),
        "",
        bundle.get("gherkin", ""),
        "",
    ]
    for c in realizing:
        code_dir = _code_dir(c, repo_root)
        if code_dir is None or not code_dir.is_dir():
            continue
        for rel_path in _code_files_skip_pycache(code_dir):
            parts.append("## " + c["id"] + ": " + rel_path)
            parts.append((code_dir / rel_path).read_text(encoding="utf-8", errors="replace"))
    parts.append("")
    parts.append('Respond with JSON: {"result": "pass" | "fail", "rationale": "..."}')
    return "\n".join(parts)


def _parse_judge_json(text):
    if text is None:
        return None
    stripped = text.strip()
    fence_match = re.match(r"^```(?:\w+)?\n(.*?)\n?```$", stripped, re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1).strip()
    try:
        data = json.loads(stripped)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _build_judge(repo_root, model, llm_backend, realizing):
    def _callable(bundle):
        try:
            endpoint = _load_llm_endpoint(repo_root)
            prompt = _build_judge_prompt(repo_root, bundle, realizing)
            response = endpoint.complete(prompt, model, backend=llm_backend)
        except Exception as exc:
            return {"result": "fail", "rationale": "judge unavailable: " + str(exc)}
        model_call_error = _get(response, "model_call_error")
        if model_call_error:
            message = _get(model_call_error, "message", str(model_call_error))
            return {"result": "fail", "rationale": "judge unavailable: " + str(message)}
        text = _get(response, "text")
        parsed = _parse_judge_json(text)
        if parsed is None:
            return {"result": "fail", "rationale": "judge unavailable: unparseable response"}
        result = parsed.get("result")
        rationale = parsed.get("rationale", "")
        if result not in ("pass", "fail"):
            return {"result": "fail", "rationale": "judge unavailable: invalid result"}
        return {"result": result, "rationale": rationale}
    return _callable


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    repo_root = Path(repo_root)
    check = check_capability_provenance(capability_id, repo_root)
    if _get(check, "hit"):
        return check
    if model is None:
        raise ModelRequiredError(capability_id)
    components = _scan_components(repo_root)
    spec = _find_capability_spec(repo_root, capability_id)
    if spec is None:
        raise UnknownCapabilityError(capability_id)
    realizing = _realizing_set(components, capability_id)
    judge_callable = _build_judge(repo_root, model, llm_backend, realizing)
    test_author_callable = _build_test_author(repo_root, model, seed, llm_backend)
    report = {
        capability_id: _run_one_capability(
            capability_id, components, repo_root, judge_callable, test_author_callable
        )
    }
    content_hash = _compute_content_hash(repo_root, spec["path"], realizing)
    record = {
        "capability_id": capability_id,
        "gate_version": GATE_VERSION,
        "content_hash": content_hash,
        "realizing_components": sorted(c["id"] for c in realizing),
        "capability_scenario_report": report,
        "model": model,
        "seed": seed,
    }
    _write_provenance_record(repo_root, capability_id, record)
    return {"hit": False, "capability_scenario_report": report}