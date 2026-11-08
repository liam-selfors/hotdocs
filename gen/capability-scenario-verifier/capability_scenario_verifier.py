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


def _tool_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _dependency_base_dir(repo_root, rel_dir):
    repo_root = Path(repo_root)
    base = repo_root / rel_dir
    if base.is_dir():
        return base
    tool_root = _tool_root()
    if tool_root is not None:
        alt = tool_root / rel_dir
        if alt.is_dir():
            return alt
    return base


def _load_module(repo_root, rel_dir, module_name):
    base = _dependency_base_dir(repo_root, rel_dir)
    pkg_init = base / module_name / "__init__.py"
    flat = base / f"{module_name}.py"
    if pkg_init.is_file():
        path = pkg_init
        search_locations = [str(base / module_name)]
    elif flat.is_file():
        path = flat
        search_locations = None
    else:
        raise ImportError(f"cannot locate module {module_name!r} under {base}")
    spec = importlib.util.spec_from_file_location(
        module_name, path, submodule_search_locations=search_locations
    )
    module = importlib.util.module_from_spec(spec)
    # Must be registered before exec_module: a dataclass defined inside
    # the loaded module resolves its own __module__ via sys.modules at
    # class-body execution time.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_criterion_compiler(repo_root):
    return _load_module(repo_root, "pipeline/criterion-compiler", "criterion_compiler")


def _load_test_author(repo_root):
    return _load_module(repo_root, "gen/test-author", "test_author")


def _load_llm_endpoint(repo_root):
    return _load_module(repo_root, "gen/llm-endpoint", "llm_endpoint")


def _parse_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i]
        i += 1
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            items = [x.strip().strip('"').strip("'") for x in inner.split(",")] if inner else []
            result[key] = items
        elif value.lower() == "true":
            result[key] = True
        elif value.lower() == "false":
            result[key] = False
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            result[key] = value[1:-1]
        else:
            result[key] = value
    return result


def _iter_components(repo_root):
    comp_dir = Path(repo_root) / "specs" / "components"
    if not comp_dir.is_dir():
        return
    for slug_dir in sorted(comp_dir.iterdir()):
        if not slug_dir.is_dir():
            continue
        comp_md = slug_dir / "component.md"
        if not comp_md.is_file():
            continue
        fm = _parse_frontmatter(comp_md.read_text(encoding="utf-8"))
        yield slug_dir, fm


def _build_realizes_edges(repo_root):
    edges = []
    for slug_dir, fm in _iter_components(repo_root):
        comp_id = fm.get("id")
        if not comp_id:
            continue
        realizes = fm.get("realizes") or []
        if isinstance(realizes, str):
            realizes = [realizes]
        for cap_id in realizes:
            edges.append((comp_id, cap_id))
    return edges


def _capabilities_for_blast_radius(repo_root, blast_radius):
    blast_set = set(blast_radius)
    edges = _build_realizes_edges(repo_root)
    return sorted({cap_id for comp_id, cap_id in edges if comp_id in blast_set})


def _realizing_components(repo_root, capability_id):
    comps = []
    for slug_dir, fm in _iter_components(repo_root):
        comp_id = fm.get("id")
        if not comp_id:
            continue
        realizes = fm.get("realizes") or []
        if isinstance(realizes, str):
            realizes = [realizes]
        if capability_id in realizes:
            comps.append(
                {
                    "id": comp_id,
                    "slug": slug_dir.name,
                    "sealed": bool(fm.get("sealed", False)),
                    "source_path": fm.get("source_path"),
                }
            )
    comps.sort(key=lambda c: c["id"])
    return comps


def _code_dir(repo_root, comp):
    repo_root = Path(repo_root)
    if comp.get("sealed") and comp.get("source_path"):
        return repo_root / comp["source_path"]
    return repo_root / "gen" / comp["slug"]


def _find_capability_file(repo_root, capability_id):
    product_dir = Path(repo_root) / "specs" / "product"
    if not product_dir.is_dir():
        return None
    for md in sorted(product_dir.glob("*.md")):
        fm = _parse_frontmatter(md.read_text(encoding="utf-8"))
        if fm.get("id") == capability_id:
            return md
    return None


def _parse_capability_scenarios(text):
    lines = text.splitlines()
    scenarios = []
    i = 0
    n = len(lines)
    header_re = re.compile(r"^###\s+(CS-[A-Za-z0-9\-]+)")
    section_re = re.compile(r"^#{1,3}\s+")
    covers_re = re.compile(r"^\s*Covers:\s*(.+)$")
    kind_re = re.compile(r"^\s*Kind:\s*(.+)$")
    while i < n:
        m = header_re.match(lines[i])
        if not m:
            i += 1
            continue
        scenario_id = m.group(1)
        i += 1
        covers = None
        kind = None
        gherkin_lines = []
        in_fence = False
        while i < n and not (section_re.match(lines[i]) and not in_fence):
            line = lines[i]
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                i += 1
                continue
            if in_fence:
                gherkin_lines.append(line)
            else:
                cm = covers_re.match(line)
                km = kind_re.match(line)
                if cm:
                    covers = cm.group(1).strip()
                elif km:
                    kind = km.group(1).strip()
            i += 1
        scenarios.append(
            {
                "id": scenario_id,
                "covers": covers,
                "kind": kind,
                "gherkin": "\n".join(gherkin_lines).strip(),
            }
        )
    return scenarios


def _scenario_bundle(capability_id, cap_file, repo_root, scenario):
    try:
        file_rel = str(Path(cap_file).relative_to(Path(repo_root)))
    except ValueError:
        file_rel = str(cap_file)
    return {
        "capability_id": capability_id,
        "scenario_id": scenario["id"],
        "covers": scenario["covers"],
        "kind": scenario["kind"],
        "gherkin": scenario["gherkin"],
        "file": file_rel,
    }


def _is_valid_test_path(path):
    p = Path(path)
    if p.is_absolute():
        return False
    parts = p.parts
    if ".." in parts:
        return False
    if not parts or parts[0] != "verification":
        return False
    return True


def _run_pytest(repo_root, rel_path, realizing):
    repo_root = Path(repo_root)
    code_dirs = [str(_code_dir(repo_root, comp)) for comp in realizing]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(code_dirs)
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(rel_path)]
    try:
        proc = subprocess.run(
            cmd, cwd=str(repo_root), env=env, timeout=120, capture_output=True
        )
    except (subprocess.TimeoutExpired, OSError):
        return "fail"
    return "pass" if proc.returncode == 0 else "fail"


def _run_compiled_scenario(repo_root, capability_id, realizing, bundle):
    module = _load_criterion_compiler(repo_root)
    parsed = module.ParsedCriterion(
        criterion_id=bundle["scenario_id"],
        covers=bundle["covers"],
        kind="compiled",
        gherkin=bundle["gherkin"],
        file=bundle["file"],
    )
    compiled = module.compile_criterion(parsed, surface=None)
    status = _get(compiled, "status")
    if status != "compiled":
        return "fail"
    source = _get(compiled, "source")
    scenario_slug = bundle["scenario_id"].lower().replace("-", "_")
    test_rel = Path("verification") / "capabilities" / capability_id / "compiled" / f"test_{scenario_slug}.py"
    full_path = Path(repo_root) / test_rel
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(source, encoding="utf-8")
    return _run_pytest(repo_root, test_rel, realizing)


def _run_generated_test_scenario(repo_root, realizing, bundle, test_author):
    outcome = test_author(bundle)
    error = _get(outcome, "model_call_error")
    if error:
        return "fail"
    file_obj = _get(outcome, "file")
    if not file_obj:
        return "fail"
    path = _get(file_obj, "path")
    content = _get(file_obj, "content")
    if not path or content is None:
        return "fail"
    if not _is_valid_test_path(path):
        return "fail"
    full_path = Path(repo_root) / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return _run_pytest(repo_root, Path(path), realizing)


def _interpret_judge_outcome(outcome):
    if isinstance(outcome, dict):
        result = outcome.get("result", outcome.get("verdict"))
        rationale = outcome.get("rationale")
    elif hasattr(outcome, "result") or hasattr(outcome, "verdict"):
        result = getattr(outcome, "result", None)
        if result is None:
            result = getattr(outcome, "verdict", None)
        rationale = getattr(outcome, "rationale", None)
    else:
        result = outcome
        rationale = None
    if result not in ("pass", "fail", "skipped"):
        result = "fail"
    return result, rationale


def _dispatch_scenario(repo_root, capability_id, realizing, bundle, judge, test_author):
    kind = bundle["kind"]
    scenario_id = bundle["scenario_id"]
    if kind == "compiled":
        result = _run_compiled_scenario(repo_root, capability_id, realizing, bundle)
        return {"id": scenario_id, "kind": kind, "result": result}
    if kind == "generated-test":
        if test_author is None:
            return {"id": scenario_id, "kind": kind, "result": "fail"}
        result = _run_generated_test_scenario(repo_root, realizing, bundle, test_author)
        return {"id": scenario_id, "kind": kind, "result": result}
    if kind == "llm-judge":
        if judge is None:
            return {"id": scenario_id, "kind": kind, "result": "skipped"}
        outcome = judge(bundle)
        result, rationale = _interpret_judge_outcome(outcome)
        return {"id": scenario_id, "kind": kind, "result": result, "rationale": rationale}
    return {"id": scenario_id, "kind": kind, "result": "fail"}


def _aggregate_overall(scenario_results):
    if not scenario_results:
        return "fail"
    if any(s["result"] == "fail" for s in scenario_results):
        return "fail"
    if all(s["result"] == "skipped" for s in scenario_results):
        return "skipped"
    return "pass"


def _run_one_capability(repo_root, capability_id, judge, test_author):
    cap_file = _find_capability_file(repo_root, capability_id)
    realizing = _realizing_components(repo_root, capability_id)
    scenario_results = []
    if cap_file is not None:
        text = cap_file.read_text(encoding="utf-8")
        scenarios = _parse_capability_scenarios(text)
        for scenario in scenarios:
            bundle = _scenario_bundle(capability_id, cap_file, repo_root, scenario)
            entry = _dispatch_scenario(repo_root, capability_id, realizing, bundle, judge, test_author)
            scenario_results.append(entry)
    return {"overall": _aggregate_overall(scenario_results), "scenarios": scenario_results}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    repo_root = Path(repo_root)
    report = {}
    for cap_id in _capabilities_for_blast_radius(repo_root, blast_radius):
        report[cap_id] = _run_one_capability(repo_root, cap_id, judge, test_author)
    return report


def _sorted_files(code_dir):
    paths = []
    for root, dirs, files in os.walk(code_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f == ".provenance.json":
                continue
            full = Path(root) / f
            paths.append(full.relative_to(code_dir))
    paths.sort(key=lambda p: str(p))
    return paths


def _compute_content_hash(repo_root, cap_file, realizing):
    repo_root = Path(repo_root)
    h = hashlib.sha256()
    h.update(cap_file.read_bytes())
    h.update(b"\0")
    for comp in sorted(realizing, key=lambda c: c["id"]):
        h.update(comp["id"].encode("utf-8"))
        h.update(b"\0")
        code_dir = _code_dir(repo_root, comp)
        if code_dir.is_dir():
            for rel_path in _sorted_files(code_dir):
                full = code_dir / rel_path
                h.update(str(rel_path).encode("utf-8"))
                h.update(b"\0")
                h.update(full.read_bytes())
                h.update(b"\0")
    return "sha256:" + h.hexdigest()


def _write_record(repo_root, capability_id, record):
    record_dir = Path(repo_root) / "verification" / "capabilities" / capability_id
    record_dir.mkdir(parents=True, exist_ok=True)
    (record_dir / ".provenance.json").write_text(
        json.dumps(record, sort_keys=True, indent=2), encoding="utf-8"
    )


def check_capability_provenance(capability_id, repo_root):
    repo_root = Path(repo_root)
    cap_file = _find_capability_file(repo_root, capability_id)
    if cap_file is None:
        raise UnknownCapabilityError(capability_id)
    realizing = _realizing_components(repo_root, capability_id)
    record_path = repo_root / "verification" / "capabilities" / capability_id / ".provenance.json"
    if not record_path.is_file():
        return {"hit": False, "capability_scenario_report": None}
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"hit": False, "capability_scenario_report": None}
    if not isinstance(record, dict):
        return {"hit": False, "capability_scenario_report": None}
    if record.get("gate_version") != GATE_VERSION:
        return {"hit": False, "capability_scenario_report": None}
    current_hash = _compute_content_hash(repo_root, cap_file, realizing)
    if record.get("content_hash") != current_hash:
        return {"hit": False, "capability_scenario_report": None}
    return {"hit": True, "capability_scenario_report": record.get("capability_scenario_report")}


def _build_criterion_bundle(repo_root, capability_id, cap_file, realizing, bundle):
    repo_root = Path(repo_root)
    requirement_text = cap_file.read_text(encoding="utf-8")
    interface_parts = []
    for comp in realizing:
        interface_parts.append(f"## {comp['id']}")
        iface_dir = repo_root / "specs" / "components" / comp["slug"] / "interface"
        if iface_dir.is_dir():
            md_files = sorted(iface_dir.rglob("*.md"), key=lambda p: str(p.relative_to(iface_dir)))
            for md in md_files:
                interface_parts.append(md.read_text(encoding="utf-8"))
    glossary_path = repo_root / "specs" / "glossary.md"
    glossary_text = glossary_path.read_text(encoding="utf-8") if glossary_path.is_file() else ""
    module_names = [comp["slug"].replace("-", "_") for comp in realizing]
    return {
        "component_id": f"capabilities/{capability_id}",
        "criterion_id": bundle["scenario_id"],
        "covers": bundle["covers"],
        "criterion_text": bundle["gherkin"],
        "requirement_text": requirement_text,
        "interface": "\n".join(interface_parts),
        "glossary": glossary_text,
        "dependency_interfaces": {},
        "module_names": module_names,
    }


def _build_test_author_callable(repo_root, capability_id, cap_file, realizing, model, seed, llm_backend):
    def _call(bundle):
        module = _load_test_author(repo_root)
        criterion_bundle = _build_criterion_bundle(repo_root, capability_id, cap_file, realizing, bundle)
        return module.author_test(
            criterion_bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    return _call


def _unwrap_code_fence(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _build_judge_prompt(repo_root, realizing, bundle):
    repo_root = Path(repo_root)
    parts = [
        "Capability scenario under test:",
        f"Covers: {bundle.get('covers')}",
        bundle.get("gherkin", ""),
        "",
        "Realized by the following components' code:",
    ]
    for comp in realizing:
        code_dir = _code_dir(repo_root, comp)
        if not code_dir.is_dir():
            continue
        for rel_path in _sorted_files(code_dir):
            full = code_dir / rel_path
            parts.append(f"## {comp['id']}/{rel_path}")
            try:
                parts.append(full.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, OSError):
                continue
    parts.append('Respond with JSON {"result": "pass" | "fail", "rationale": "..."}')
    return "\n".join(parts)


def _build_judge_callable(repo_root, realizing, model, llm_backend):
    def _call(bundle):
        try:
            module = _load_llm_endpoint(repo_root)
            prompt = _build_judge_prompt(repo_root, realizing, bundle)
            response = module.complete(prompt, model, backend=llm_backend)
        except Exception as exc:
            return {"result": "fail", "rationale": f"judge unavailable: {exc}"}
        error = _get(response, "model_call_error")
        if error:
            message = _get(error, "message", str(error))
            return {"result": "fail", "rationale": f"judge unavailable: {message}"}
        text = _get(response, "text")
        if not text:
            return {"result": "fail", "rationale": "judge unavailable: empty response"}
        unwrapped = _unwrap_code_fence(text)
        try:
            parsed = json.loads(unwrapped)
        except ValueError:
            return {"result": "fail", "rationale": "judge unavailable: unparseable response"}
        result = _get(parsed, "result")
        if result not in ("pass", "fail"):
            return {"result": "fail", "rationale": "judge unavailable: invalid result"}
        rationale = _get(parsed, "rationale")
        return {"result": result, "rationale": rationale}

    return _call


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    repo_root = Path(repo_root)
    check = check_capability_provenance(capability_id, repo_root)
    hit = _get(check, "hit")
    if hit:
        return check
    if model is None:
        raise ModelRequiredError(capability_id)
    cap_file = _find_capability_file(repo_root, capability_id)
    realizing = _realizing_components(repo_root, capability_id)
    test_author_callable = _build_test_author_callable(
        repo_root, capability_id, cap_file, realizing, model, seed, llm_backend
    )
    judge_callable = _build_judge_callable(repo_root, realizing, model, llm_backend)
    capability_report = _run_one_capability(repo_root, capability_id, judge_callable, test_author_callable)
    report = {capability_id: capability_report}
    content_hash = _compute_content_hash(repo_root, cap_file, realizing)
    record = {
        "capability_id": capability_id,
        "gate_version": GATE_VERSION,
        "content_hash": content_hash,
        "realizing_components": sorted(c["id"] for c in realizing),
        "capability_scenario_report": report,
        "model": model,
        "seed": seed,
    }
    _write_record(repo_root, capability_id, record)
    return {"hit": False, "capability_scenario_report": report}