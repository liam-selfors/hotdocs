"""Capability Scenario Verifier.

Runs the capability scenarios of every product capability whose
`realizes`-set intersects a blast radius, against the real assembled
`gen/` output, and keeps a per-capability provenance record.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

GATE_VERSION = "capability_scenario_verifier@2.2.0"

_TEST_TIMEOUT_SECONDS = 120


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_file(name, path):
    path = Path(path)
    locations = [str(path.parent)] if path.name == "__init__.py" else None
    spec = importlib.util.spec_from_file_location(
        name, str(path), submodule_search_locations=locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dep(repo_root, rel_dir, name):
    directory = Path(repo_root) / rel_dir
    if not directory.is_dir():
        directory = _tool_root() / rel_dir
    target = directory / (name + ".py")
    if not target.is_file():
        target = directory / name / "__init__.py"
    return _load_file(name, target)


def _load_python_adapter(repo_root):
    rel = Path("gen") / "kind-python" / "kind_python.py"
    path = Path(repo_root) / rel
    if not path.exists():
        path = _tool_root() / rel
    if not path.exists():
        return None
    return _load_file("kind_python", path)


def _provision(repo_root):
    adapter = _load_python_adapter(repo_root)
    if adapter is None:
        return None
    return adapter.provision(repo_root)


def _frontmatter(text):
    lines = text.splitlines()
    fields = {}
    if not lines or lines[0].strip() != "---":
        return fields
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def _list_value(raw):
    inner = raw.strip().lstrip("[").rstrip("]")
    items = []
    for item in inner.split(","):
        item = item.strip().strip("\"'")
        if item:
            items.append(item)
    return items


def _walk_files(directory, skip_provenance):
    files = []
    for path in directory.rglob("*"):
        rel = path.relative_to(directory)
        if "__pycache__" in rel.parts:
            continue
        if skip_provenance and path.name == ".provenance.json":
            continue
        if not path.is_file():
            continue
        files.append((rel.as_posix(), path))
    return sorted(files)


# ---------------------------------------------------------------------------
# Corpus reading
# ---------------------------------------------------------------------------


def _components(repo_root):
    comps = []
    for path in sorted(repo_root.glob("specs/components/*/component.md")):
        fm = _frontmatter(path.read_text(encoding="utf-8"))
        cid = fm.get("id", "")
        slug = cid[len("comp-"):] if cid.startswith("comp-") else cid
        if fm.get("sealed", "").lower() == "true":
            code_dir = repo_root / fm.get("source_path", "")
        else:
            code_dir = repo_root / "gen" / slug
        comps.append(
            {
                "id": cid,
                "slug": slug,
                "realizes": _list_value(fm.get("realizes", "")),
                "code_dir": code_dir,
                "spec_dir": path.parent,
            }
        )
    return comps


def _products(repo_root):
    products = {}
    for path in sorted(repo_root.glob("specs/product/*.md")):
        fm = _frontmatter(path.read_text(encoding="utf-8"))
        products.setdefault(fm.get("id"), path)
    return products


def _realizing(comps, capability_id):
    return sorted(
        (c for c in comps if capability_id in c["realizes"]), key=lambda c: c["id"]
    )


def _scenarios(text):
    scenarios = []
    current = None
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if current is not None and in_fence:
            if stripped.startswith("```"):
                in_fence = False
            else:
                current["gherkin_lines"].append(line)
            continue
        if line.startswith("#"):
            current = None
            if line.startswith("### CS-"):
                current = {
                    "id": line[4:].split()[0],
                    "covers": "",
                    "kind": "",
                    "gherkin_lines": [],
                }
                scenarios.append(current)
            continue
        if current is None:
            continue
        if stripped.startswith("Covers:"):
            current["covers"] = stripped[len("Covers:"):].strip().strip("`")
        elif stripped.startswith("Kind:"):
            current["kind"] = stripped[len("Kind:"):].strip().strip("`")
        elif stripped.startswith("```gherkin"):
            in_fence = True
    return [
        {
            "id": s["id"],
            "covers": s["covers"],
            "kind": s["kind"],
            "gherkin": "\n".join(s["gherkin_lines"]),
        }
        for s in scenarios
    ]


# ---------------------------------------------------------------------------
# Running tests
# ---------------------------------------------------------------------------


def _run_test(repo_root, rel, content, interpreter, pythonpath):
    if not interpreter:
        return "fail"
    target = repo_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = pythonpath
    try:
        proc = subprocess.run(
            [str(interpreter), "-m", "pytest", "-q", "-p", "no:cacheprovider", rel],
            cwd=str(repo_root),
            env=env,
            timeout=_TEST_TIMEOUT_SECONDS,
            capture_output=True,
        )
    except (subprocess.TimeoutExpired, OSError):
        return "fail"
    return "pass" if proc.returncode == 0 else "fail"


def _valid_test_path(path):
    p = PurePosixPath(str(path))
    if p.is_absolute() or p.parts[:1] != ("verification",) or ".." in p.parts:
        return None
    return p.as_posix()


def _overall(results):
    if not results or "fail" in results:
        return "fail"
    if all(r == "skipped" for r in results):
        return "skipped"
    return "pass"


def _run(cap_ids, comps, repo_root, judge, test_author):
    products = _products(repo_root)
    prov = _provision(repo_root)
    interpreter = _get(prov, "interpreter") if prov is not None and _get(prov, "ok") else None
    compiler = {}
    report = {}
    for cap in cap_ids:
        product_path = products.get(cap)
        text = product_path.read_text(encoding="utf-8") if product_path is not None else ""
        realizing = _realizing(comps, cap)
        pythonpath = os.pathsep.join(str(c["code_dir"]) for c in realizing)
        entries = []
        for sc in _scenarios(text):
            rel_file = product_path.relative_to(repo_root).as_posix()
            kind = sc["kind"]
            entry = {"id": sc["id"], "kind": kind}
            bundle = {
                "capability_id": cap,
                "scenario_id": sc["id"],
                "covers": sc["covers"],
                "kind": kind,
                "gherkin": sc["gherkin"],
                "file": rel_file,
            }
            if kind == "compiled":
                if "m" not in compiler:
                    compiler["m"] = _load_dep(
                        repo_root, "pipeline/criterion-compiler", "criterion_compiler"
                    )
                cc = compiler["m"]
                parsed = cc.ParsedCriterion(
                    criterion_id=sc["id"],
                    covers=sc["covers"],
                    kind=kind,
                    gherkin=sc["gherkin"],
                    file=rel_file,
                )
                compiled = cc.compile_criterion(parsed, surface=None)
                if _get(compiled, "status") == "error":
                    entry["result"] = "fail"
                else:
                    rel = "verification/capabilities/{}/compiled/test_{}.py".format(
                        cap, sc["id"].lower().replace("-", "_")
                    )
                    entry["result"] = _run_test(
                        repo_root, rel, _get(compiled, "source"), interpreter, pythonpath
                    )
            elif kind == "generated-test":
                entry["result"] = "fail"
                if test_author is not None:
                    outcome = test_author(bundle)
                    file = _get(outcome, "file")
                    if not _get(outcome, "model_call_error") and file:
                        rel = _valid_test_path(_get(file, "path"))
                        if rel is not None:
                            entry["result"] = _run_test(
                                repo_root, rel, _get(file, "content"), interpreter, pythonpath
                            )
            elif kind == "llm-judge":
                if judge is None:
                    entry["result"] = "skipped"
                else:
                    outcome = judge(bundle)
                    result = _get(outcome, "result")
                    if result is None:
                        result = _get(outcome, "verdict")
                    if result is None:
                        result = outcome
                    rationale = _get(outcome, "rationale")
                    entry["result"] = result
                    entry["rationale"] = rationale if rationale is not None else ""
            else:
                entry["result"] = "fail"
            entries.append(entry)
        report[cap] = {
            "overall": _overall([e["result"] for e in entries]),
            "scenarios": entries,
        }
    return report


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    repo_root = Path(repo_root)
    comps = _components(repo_root)
    blast = set(blast_radius)
    cap_ids = sorted({cap for c in comps if c["id"] in blast for cap in c["realizes"]})
    return _run(cap_ids, comps, repo_root, judge, test_author)


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def _content_hash(repo_root, product_path, realizing):
    h = hashlib.sha256()

    def field(data):
        h.update(data)
        h.update(b"\0")

    field(product_path.read_bytes())
    for comp in realizing:
        field(comp["id"].encode("utf-8"))
        code_dir = comp["code_dir"]
        if code_dir.is_dir():
            for rel, path in _walk_files(code_dir, True):
                field(rel.encode("utf-8"))
                field(path.read_bytes())
    lock = repo_root / "environments" / "python" / "requirements.lock"
    if lock.is_file():
        field(lock.read_bytes())
    prov = _provision(repo_root)
    versions = _get(prov, "versions") if prov is not None and _get(prov, "ok") else {}
    field(json.dumps(versions, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return "sha256:" + h.hexdigest()


def _record_path(repo_root, capability_id):
    return repo_root / "verification" / "capabilities" / capability_id / ".provenance.json"


def _check(capability_id, repo_root):
    products = _products(repo_root)
    if capability_id not in products:
        raise UnknownCapabilityError(capability_id)
    comps = _components(repo_root)
    realizing = _realizing(comps, capability_id)
    current = _content_hash(repo_root, products[capability_id], realizing)
    try:
        record = json.loads(_record_path(repo_root, capability_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record = None
    hit = (
        isinstance(record, dict)
        and record.get("gate_version") == GATE_VERSION
        and record.get("content_hash") == current
    )
    result = {
        "hit": hit,
        "capability_scenario_report": record.get("capability_scenario_report") if hit else None,
    }
    return result, current, comps, realizing, products[capability_id]


def check_capability_provenance(capability_id, repo_root):
    return _check(capability_id, Path(repo_root))[0]


# ---------------------------------------------------------------------------
# Built-in callables
# ---------------------------------------------------------------------------


def _make_test_author(repo_root, model, seed, llm_backend, product_path, realizing):
    loaded = {}

    def author(bundle):
        if "m" not in loaded:
            loaded["m"] = _load_dep(repo_root, "gen/test-author", "test_author")
        parts = []
        for comp in realizing:
            parts.append("## " + comp["id"])
            interface_dir = comp["spec_dir"] / "interface"
            for md in sorted(interface_dir.rglob("*.md")):
                parts.append(md.read_text(encoding="utf-8"))
        glossary_path = repo_root / "specs" / "glossary.md"
        glossary = glossary_path.read_text(encoding="utf-8") if glossary_path.is_file() else ""
        criterion_bundle = {
            "component_id": "capabilities/" + bundle["capability_id"],
            "criterion_id": bundle["scenario_id"],
            "covers": bundle["covers"],
            "criterion_text": bundle["gherkin"],
            "requirement_text": product_path.read_text(encoding="utf-8"),
            "interface": "\n".join(parts),
            "glossary": glossary,
            "dependency_interfaces": {},
            "module_names": [c["slug"].replace("-", "_") for c in realizing],
        }
        return loaded["m"].author_test(
            criterion_bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    return author


def _parse_judge_reply(text):
    lines = text.splitlines()
    fences = [i for i, line in enumerate(lines) if line.lstrip().startswith("```")]
    if fences:
        end = fences[1] if len(fences) > 1 else len(lines)
        body = "\n".join(lines[fences[0] + 1:end])
    else:
        body = text
    return json.loads(body.strip())


def _make_judge(repo_root, model, llm_backend, realizing):
    loaded = {}

    def judge(bundle):
        if "m" not in loaded:
            loaded["m"] = _load_dep(repo_root, "gen/llm-endpoint", "llm_endpoint")
        code_parts = []
        for comp in realizing:
            code_parts.append("## " + comp["id"])
            code_dir = comp["code_dir"]
            if code_dir.is_dir():
                for rel, path in _walk_files(code_dir, False):
                    code_parts.append("### " + rel)
                    code_parts.append(path.read_bytes().decode("utf-8", errors="replace"))
        prompt = "\n".join(
            [
                "You are judging whether a product capability scenario holds for "
                "the code below.",
                "",
                "Capability: " + str(bundle["capability_id"]),
                "Scenario: " + str(bundle["scenario_id"]),
                "Covers: " + str(bundle["covers"]),
                "",
                "Scenario (Gherkin):",
                str(bundle["gherkin"]),
                "",
                "Code of every realizing component:",
                "\n".join(code_parts),
                "",
                'Reply with JSON only: {"result": "pass" | "fail", "rationale": "..."}',
            ]
        )
        response = loaded["m"].complete(prompt, model, backend=llm_backend)
        error = _get(response, "model_call_error")
        if error:
            return {"result": "fail", "rationale": "judge unavailable: {}".format(_get(error, "message"))}
        try:
            parsed = _parse_judge_reply(_get(response, "text"))
        except ValueError:
            return {"result": "fail", "rationale": "judge unavailable: unparseable reply"}
        result = parsed.get("result") if isinstance(parsed, dict) else None
        if result not in ("pass", "fail"):
            return {"result": "fail", "rationale": "judge unavailable: invalid result {!r}".format(result)}
        return {"result": result, "rationale": parsed.get("rationale", "")}

    return judge


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    repo_root = Path(repo_root)
    result, current, comps, realizing, product_path = _check(capability_id, repo_root)
    if result["hit"]:
        return result
    if model is None:
        raise ModelRequiredError("a model is required to run capability scenarios")
    author = _make_test_author(repo_root, model, seed, llm_backend, product_path, realizing)
    judge = _make_judge(repo_root, model, llm_backend, realizing)
    report = _run([capability_id], comps, repo_root, judge, author)
    record = {
        "capability_id": capability_id,
        "gate_version": GATE_VERSION,
        "content_hash": current,
        "realizing_components": sorted(c["id"] for c in realizing),
        "capability_scenario_report": report,
        "model": model,
        "seed": seed,
    }
    path = _record_path(repo_root, capability_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"hit": False, "capability_scenario_report": report}
