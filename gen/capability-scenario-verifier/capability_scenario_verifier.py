"""Capability Scenario Verifier.

Runs the capability scenarios of every product capability whose
`realizes`-set intersects a blast radius, against the real assembled
`gen/` output, and keeps per-capability provenance records.
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


def _unquote(value):
    return value.strip().strip("'\"")


def _scalar(value):
    if value.startswith("[") and value.endswith("]"):
        return [_unquote(x) for x in value[1:-1].split(",") if x.strip()]
    return _unquote(value)


def _frontmatter(text):
    lines = text.splitlines()
    data = {}
    if not lines or lines[0].strip() != "---":
        return data
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep:
            data[key.strip()] = _scalar(value.strip())
    return data


def _load(module_name, rel_dir, repo_root):
    base = Path(repo_root) / rel_dir
    if not base.is_dir():
        gen = next(p for p in Path(__file__).resolve().parents if p.name == "gen")
        base = gen.parent / rel_dir
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


def _components(repo_root):
    comps = []
    for path in sorted((repo_root / "specs" / "components").glob("*/component.md")):
        fm = _frontmatter(path.read_text(encoding="utf-8"))
        cid = fm.get("id")
        realizes = fm.get("realizes", [])
        if not isinstance(realizes, list):
            realizes = [realizes]
        comps.append(
            {
                "id": cid,
                "slug": cid.removeprefix("comp-"),
                "spec_dir": path.parent,
                "sealed": str(fm.get("sealed", "")).lower() == "true",
                "source_path": fm.get("source_path"),
                "realizes": realizes,
            }
        )
    return comps


def _capabilities(repo_root):
    caps = {}
    for path in sorted((repo_root / "specs" / "product").glob("*.md")):
        cid = _frontmatter(path.read_text(encoding="utf-8")).get("id")
        caps.setdefault(cid, path)
    return caps


def _realizing(capability_id, comps):
    return sorted((c for c in comps if capability_id in c["realizes"]), key=lambda c: c["id"])


def _code_dir(comp, repo_root):
    root = Path(os.path.abspath(repo_root))
    if comp["sealed"]:
        return root / comp["source_path"]
    return root / "gen" / comp["slug"]


def _files(root, skip_provenance):
    if not root.is_dir():
        return []
    out = []
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if "__pycache__" in rel.parts or not p.is_file():
            continue
        if skip_provenance and p.name == ".provenance.json":
            continue
        out.append((rel.as_posix(), p))
    return sorted(out)


def _content_hash(product, realizing, repo_root):
    h = hashlib.sha256()
    h.update(product.read_bytes() + b"\0")
    for comp in realizing:
        h.update(comp["id"].encode("utf-8") + b"\0")
        for rel, p in _files(_code_dir(comp, repo_root), True):
            h.update(rel.encode("utf-8") + b"\0")
            h.update(p.read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()


def _parse_scenarios(text):
    scenarios = []
    cur = None
    in_fence = False
    capture = False
    buf = []
    for line in text.splitlines():
        s = line.strip()
        if in_fence:
            if s.startswith("```"):
                in_fence = False
                if capture:
                    cur["gherkin"] = "\n".join(buf)
                    capture = False
            elif capture:
                buf.append(line)
            continue
        if s.startswith("```"):
            in_fence = True
            capture = cur is not None and s[3:].strip() == "gherkin"
            buf = []
            continue
        if s.startswith("#"):
            m = re.match(r"###\s+(CS-\S+)", s)
            cur = None
            if m:
                cur = {"id": m.group(1), "covers": "", "kind": "", "gherkin": ""}
                scenarios.append(cur)
            continue
        if cur is not None and s.startswith("Covers:"):
            cur["covers"] = s[len("Covers:"):].strip().strip("`")
        elif cur is not None and s.startswith("Kind:"):
            cur["kind"] = s[len("Kind:"):].strip().strip("`")
    return scenarios


# ---------------------------------------------------------------------------
# dispatch


def _run_test(rel_path, realizing, repo_root):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(str(_code_dir(c, repo_root)) for c in realizing)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(rel_path)],
            cwd=str(repo_root),
            env=env,
            timeout=120,
            capture_output=True,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return proc.returncode == 0


def _write(repo_root, rel_path, content):
    target = Path(repo_root) / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _compiled_test(capability_id, scenario, product_rel, repo_root):
    cc = _load("criterion_compiler", "pipeline/criterion-compiler", repo_root)
    parsed = cc.ParsedCriterion(
        criterion_id=scenario["id"],
        covers=scenario["covers"],
        kind=scenario["kind"],
        gherkin=scenario["gherkin"],
        file=product_rel,
    )
    res = cc.compile_criterion(parsed, surface=None)
    if _get(res, "status") == "error":
        return None
    name = "test_" + scenario["id"].lower().replace("-", "_") + ".py"
    rel = f"verification/capabilities/{capability_id}/compiled/{name}"
    _write(repo_root, rel, _get(res, "source"))
    return rel


def _generated_test(bundle, test_author, repo_root):
    if test_author is None:
        return None
    out = test_author(bundle)
    file = _get(out, "file")
    if _get(out, "model_call_error") or not file:
        return None
    path = str(_get(file, "path"))
    pp = PurePosixPath(path)
    if pp.is_absolute() or pp.parts[:1] != ("verification",) or ".." in pp.parts:
        return None
    _write(repo_root, path, _get(file, "content"))
    return path


def _dispatch(capability_id, scenario, product_rel, realizing, repo_root, judge, test_author):
    kind = scenario["kind"]
    entry = {"id": scenario["id"], "kind": kind}
    bundle = {
        "capability_id": capability_id,
        "scenario_id": scenario["id"],
        "covers": scenario["covers"],
        "kind": kind,
        "gherkin": scenario["gherkin"],
        "file": product_rel,
    }
    if kind == "llm-judge":
        if judge is None:
            entry["result"] = "skipped"
            return entry
        out = judge(bundle)
        if isinstance(out, dict):
            result = out.get("result", out.get("verdict"))
            rationale = out.get("rationale", "")
        else:
            result = out
            rationale = ""
        entry["result"] = "pass" if result == "pass" else "fail"
        entry["rationale"] = rationale
        return entry
    if kind == "compiled":
        rel = _compiled_test(capability_id, scenario, product_rel, repo_root)
    elif kind == "generated-test":
        rel = _generated_test(bundle, test_author, repo_root)
    else:
        rel = None
    passed = rel is not None and _run_test(rel, realizing, repo_root)
    entry["result"] = "pass" if passed else "fail"
    return entry


def _overall(entries):
    results = [e["result"] for e in entries]
    if not results or "fail" in results:
        return "fail"
    if all(r == "skipped" for r in results):
        return "skipped"
    return "pass"


def _run_capability(capability_id, product, realizing, repo_root, judge, test_author):
    entries = []
    if product is not None:
        product_rel = product.relative_to(repo_root).as_posix()
        for scenario in _parse_scenarios(product.read_text(encoding="utf-8")):
            entries.append(
                _dispatch(capability_id, scenario, product_rel, realizing, repo_root, judge, test_author)
            )
    return {"overall": _overall(entries), "scenarios": entries}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    repo_root = Path(repo_root)
    comps = _components(repo_root)
    radius = set(blast_radius)
    cap_ids = sorted({t for c in comps if c["id"] in radius for t in c["realizes"]})
    caps = _capabilities(repo_root)
    return {
        cid: _run_capability(cid, caps.get(cid), _realizing(cid, comps), repo_root, judge, test_author)
        for cid in cap_ids
    }


# ---------------------------------------------------------------------------
# provenance


def _record_path(repo_root, capability_id):
    return Path(repo_root) / "verification" / "capabilities" / capability_id / ".provenance.json"


def _check(capability_id, repo_root):
    repo_root = Path(repo_root)
    product = _capabilities(repo_root).get(capability_id)
    if product is None:
        raise UnknownCapabilityError(f"unknown capability: {capability_id}")
    comps = _components(repo_root)
    realizing = _realizing(capability_id, comps)
    content_hash = _content_hash(product, realizing, repo_root)
    result = {"hit": False, "capability_scenario_report": None}
    try:
        record = json.loads(_record_path(repo_root, capability_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record = None
    if (
        isinstance(record, dict)
        and record.get("gate_version") == GATE_VERSION
        and record.get("content_hash") == content_hash
    ):
        result = {"hit": True, "capability_scenario_report": record.get("capability_scenario_report")}
    return result, product, realizing, content_hash


def check_capability_provenance(capability_id, repo_root):
    return _check(capability_id, repo_root)[0]


def _make_test_author(capability_id, product, realizing, repo_root, model, seed, llm_backend):
    def test_author(bundle):
        mod = _load("test_author", "gen/test-author", repo_root)
        interface_parts = []
        for comp in realizing:
            interface_parts.append(f"## {comp['id']}")
            iface = comp["spec_dir"] / "interface"
            for _rel, p in _files(iface, False):
                if p.suffix == ".md":
                    interface_parts.append(p.read_text(encoding="utf-8"))
        glossary = Path(repo_root) / "specs" / "glossary.md"
        criterion_bundle = {
            "component_id": f"capabilities/{capability_id}",
            "criterion_id": bundle["scenario_id"],
            "covers": bundle["covers"],
            "criterion_text": bundle["gherkin"],
            "requirement_text": product.read_text(encoding="utf-8"),
            "interface": "\n".join(interface_parts),
            "glossary": glossary.read_text(encoding="utf-8") if glossary.is_file() else "",
            "dependency_interfaces": {},
            "module_names": [c["slug"].replace("-", "_") for c in realizing],
        }
        return mod.author_test(
            criterion_bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    return test_author


def _extract_json_text(text):
    lines = text.splitlines()
    fences = [i for i, line in enumerate(lines) if line.startswith("```")]
    if fences:
        end = fences[1] if len(fences) > 1 else len(lines)
        return "\n".join(lines[fences[0] + 1:end])
    return text.strip()


def _make_judge(realizing, repo_root, model, llm_backend):
    def judge(bundle):
        parts = [
            "You are judging whether a product capability scenario holds against "
            "the real, fully assembled code below.",
            f"Scenario: {bundle['scenario_id']}",
            f"Covers: {bundle['covers']}",
            "Gherkin:",
            bundle["gherkin"],
            "",
            "Code:",
        ]
        for comp in realizing:
            for rel, p in _files(_code_dir(comp, repo_root), False):
                parts.append(f"=== {comp['id']}: {rel} ===")
                parts.append(p.read_bytes().decode("utf-8", "replace"))
        parts.append(
            'Reply with JSON only: {"result": "pass" | "fail", "rationale": "..."}'
        )
        prompt = "\n".join(parts)
        le = _load("llm_endpoint", "gen/llm-endpoint", repo_root)
        resp = le.complete(prompt, model, backend=llm_backend)
        err = _get(resp, "model_call_error")
        if err:
            return {"result": "fail", "rationale": f"judge unavailable: {_get(err, 'message')}"}
        try:
            parsed = json.loads(_extract_json_text(_get(resp, "text") or ""))
        except ValueError as exc:
            return {"result": "fail", "rationale": f"judge unavailable: unparseable reply: {exc}"}
        result = parsed.get("result") if isinstance(parsed, dict) else None
        if result not in ("pass", "fail"):
            return {"result": "fail", "rationale": f"judge unavailable: invalid result {result!r}"}
        return {"result": result, "rationale": parsed.get("rationale", "")}

    return judge


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    check, product, realizing, content_hash = _check(capability_id, repo_root)
    if check["hit"]:
        return check
    if model is None:
        raise ModelRequiredError("a model is required to run capability gates on a miss")
    root = Path(repo_root)
    ta = _make_test_author(capability_id, product, realizing, repo_root, model, seed, llm_backend)
    jg = _make_judge(realizing, repo_root, model, llm_backend)
    report = {capability_id: _run_capability(capability_id, product, realizing, root, jg, ta)}
    record = {
        "capability_id": capability_id,
        "gate_version": GATE_VERSION,
        "content_hash": content_hash,
        "realizing_components": sorted(c["id"] for c in realizing),
        "capability_scenario_report": report,
        "model": model,
        "seed": seed,
    }
    path = _record_path(root, capability_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"hit": False, "capability_scenario_report": report}
