"""Capability scenario verifier.

Runs the capability scenarios of every product capability whose
``realizes``-set intersects a blast radius, against the real assembled
``gen/`` output, and checks/writes per-capability provenance records.
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

_PYTEST_TIMEOUT_SECONDS = 120


class UnknownCapabilityError(ValueError):
    """No specs/product/*.md carries the given capability id."""


class ModelRequiredError(ValueError):
    """A fresh run was needed but no model was given."""


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _exec_from_path(name, path, search_locations=None):
    spec = importlib.util.spec_from_file_location(
        name, str(path), submodule_search_locations=search_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dependency(repo_root, rel_dir, module_name):
    base = Path(repo_root) / rel_dir
    if not base.is_dir():
        base = _tool_root() / rel_dir
    flat = base / f"{module_name}.py"
    if flat.is_file():
        return _exec_from_path(module_name, flat)
    package = base / module_name
    return _exec_from_path(
        module_name, package / "__init__.py", search_locations=[str(package)]
    )


def _load_python_adapter(repo_root):
    rel = Path("gen") / "kind-python" / "kind_python.py"
    path = Path(repo_root) / rel
    if not path.is_file():
        path = _tool_root() / rel
    if not path.is_file():
        return None
    return _exec_from_path("kind_python", path)


def _provision(repo_root):
    adapter = _load_python_adapter(repo_root)
    if adapter is None:
        return None
    return adapter.provision(repo_root)


def _frontmatter(text):
    lines = text.splitlines()
    fm = {}
    if not lines or lines[0].strip() != "---":
        return fm
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep:
            fm[key.strip()] = value.strip()
    return fm


def _code_files(code_dir, exclude_provenance):
    files = []
    for path in code_dir.rglob("*"):
        rel = path.relative_to(code_dir)
        if "__pycache__" in rel.parts or not path.is_file():
            continue
        if exclude_provenance and path.name == ".provenance.json":
            continue
        files.append((rel.as_posix(), path))
    return sorted(files, key=lambda item: item[0])


# ---------------------------------------------------------------------------
# Corpus scanning
# ---------------------------------------------------------------------------


def _components(repo_root):
    comps = []
    for md in sorted((repo_root / "specs" / "components").glob("*/component.md")):
        fm = _frontmatter(md.read_text(encoding="utf-8"))
        comp_id = fm.get("id", "")
        slug = comp_id.removeprefix("comp-")
        realizes = [
            item.strip()
            for item in fm.get("realizes", "").strip("[]").split(",")
            if item.strip()
        ]
        if fm.get("sealed") == "true":
            code_dir = repo_root / fm.get("source_path", "")
        else:
            code_dir = repo_root / "gen" / slug
        comps.append(
            {"id": comp_id, "slug": slug, "realizes": realizes, "code_dir": code_dir}
        )
    return comps


def _field(pattern, section):
    m = re.search(pattern, section)
    return m.group(1).strip().strip("`") if m else ""


def _parse_scenarios(text, capability_id, rel):
    scenarios = []
    for section in re.split(r"(?m)^(?=#{1,3} )", text):
        if not section.startswith("### CS-"):
            continue
        gherkin = re.search(r"(?ms)^```gherkin[^\n]*\n(.*?)^```", section)
        scenarios.append(
            {
                "capability_id": capability_id,
                "scenario_id": section.split()[1],
                "covers": _field(r"(?m)^Covers:(.*)$", section),
                "kind": _field(r"(?m)^Kind:(.*)$", section),
                "gherkin": gherkin.group(1) if gherkin else "",
                "file": rel,
            }
        )
    return scenarios


def _products(repo_root):
    products = {}
    for md in sorted((repo_root / "specs" / "product").glob("*.md")):
        text = md.read_text(encoding="utf-8")
        cap_id = _frontmatter(text).get("id")
        rel = md.relative_to(repo_root).as_posix()
        products[cap_id] = {
            "id": cap_id,
            "path": md,
            "text": text,
            "scenarios": _parse_scenarios(text, cap_id, rel),
        }
    return products


def _realizing(capability_id, components):
    return sorted(
        (c for c in components if capability_id in c["realizes"]),
        key=lambda c: c["id"],
    )


# ---------------------------------------------------------------------------
# Scenario dispatch
# ---------------------------------------------------------------------------


def _bundle_for_scenario(scenario):
    return {
        "capability_id": scenario["capability_id"],
        "scenario_id": scenario["scenario_id"],
        "covers": scenario["covers"],
        "kind": scenario["kind"],
        "gherkin": scenario["gherkin"],
        "file": scenario["file"],
    }


def _judge_verdict(outcome):
    value = _get(outcome, "result")
    if value is None:
        value = _get(outcome, "verdict")
    if value is None and not isinstance(outcome, dict):
        value = outcome
    return ("pass" if value == "pass" else "fail"), _get(outcome, "rationale")


def _overall(scenarios):
    results = [s["result"] for s in scenarios]
    if not results or "fail" in results:
        return "fail"
    if all(r == "skipped" for r in results):
        return "skipped"
    return "pass"


class _Runner:
    """One run_capability_scenarios call's worth of shared state."""

    def __init__(self, repo_root):
        self.repo_root = repo_root
        self._provisioned = False
        self._interpreter = None
        self._compiler = None

    def _get_interpreter(self):
        if not self._provisioned:
            self._provisioned = True
            prov = _provision(self.repo_root)
            if prov is not None and _get(prov, "ok"):
                self._interpreter = _get(prov, "interpreter")
        return self._interpreter

    def _get_compiler(self):
        if self._compiler is None:
            self._compiler = _load_dependency(
                self.repo_root, Path("pipeline") / "criterion-compiler", "criterion_compiler"
            )
        return self._compiler

    def _execute(self, rel_path, content, pythonpath):
        interpreter = self._get_interpreter()
        if interpreter is None:
            return "fail"
        target = self.repo_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = pythonpath
        try:
            proc = subprocess.run(
                [str(interpreter), "-m", "pytest", "-q", "-p", "no:cacheprovider", str(rel_path)],
                cwd=str(self.repo_root),
                env=env,
                timeout=_PYTEST_TIMEOUT_SECONDS,
                capture_output=True,
                stdin=subprocess.DEVNULL,
            )
        except (subprocess.TimeoutExpired, OSError):
            return "fail"
        return "pass" if proc.returncode == 0 else "fail"

    def _compiled(self, scenario, pythonpath):
        compiler = self._get_compiler()
        parsed = compiler.ParsedCriterion(
            criterion_id=scenario["scenario_id"],
            covers=scenario["covers"],
            kind=scenario["kind"],
            gherkin=scenario["gherkin"],
            file=scenario["file"],
        )
        outcome = compiler.compile_criterion(parsed, surface=None)
        if _get(outcome, "status") != "compiled":
            return "fail"
        name = "test_" + scenario["scenario_id"].lower().replace("-", "_") + ".py"
        rel = (
            PurePosixPath("verification")
            / "capabilities"
            / scenario["capability_id"]
            / "compiled"
            / name
        ).as_posix()
        return self._execute(rel, _get(outcome, "source"), pythonpath)

    def _generated(self, scenario, test_author, pythonpath):
        if test_author is None:
            return "fail"
        outcome = test_author(_bundle_for_scenario(scenario))
        file_obj = _get(outcome, "file")
        if _get(outcome, "model_call_error") or not file_obj:
            return "fail"
        path = str(_get(file_obj, "path"))
        parts = PurePosixPath(path).parts
        if parts[:1] != ("verification",) or ".." in parts:
            return "fail"
        return self._execute(path, _get(file_obj, "content"), pythonpath)

    def run_capability(self, scenarios, realizing, judge, test_author):
        pythonpath = os.pathsep.join(str(c["code_dir"]) for c in realizing)
        entries = []
        for scenario in scenarios:
            kind = scenario["kind"]
            entry = {"id": scenario["scenario_id"], "kind": kind}
            if kind == "compiled":
                entry["result"] = self._compiled(scenario, pythonpath)
            elif kind == "generated-test":
                entry["result"] = self._generated(scenario, test_author, pythonpath)
            elif kind == "llm-judge":
                if judge is None:
                    entry["result"] = "skipped"
                else:
                    result, rationale = _judge_verdict(judge(_bundle_for_scenario(scenario)))
                    entry["result"] = result
                    entry["rationale"] = rationale
            else:
                entry["result"] = "fail"
            entries.append(entry)
        return {"overall": _overall(entries), "scenarios": entries}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    repo_root = Path(repo_root)
    components = _components(repo_root)
    products = _products(repo_root)
    blast = set(blast_radius)
    # SELECT DISTINCT target_id FROM edges WHERE edge_type = 'realizes'
    #   AND source_id IN (<blast-radius ids>)
    capability_ids = sorted(
        {target for c in components if c["id"] in blast for target in c["realizes"]}
    )
    runner = _Runner(repo_root)
    report = {}
    for capability_id in capability_ids:
        product = products.get(capability_id, {})
        report[capability_id] = runner.run_capability(
            product.get("scenarios", []),
            _realizing(capability_id, components),
            judge,
            test_author,
        )
    return report


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def _content_hash(repo_root, product, realizing):
    digest = hashlib.sha256()

    def field(data):
        digest.update(data)
        digest.update(b"\0")

    field(product["path"].read_bytes())
    for comp in realizing:
        field(comp["id"].encode("utf-8"))
        for rel, path in _code_files(comp["code_dir"], exclude_provenance=True):
            field(rel.encode("utf-8"))
            field(path.read_bytes())
    lock = repo_root / "environments" / "python" / "requirements.lock"
    if lock.is_file():
        field(lock.read_bytes())
    prov = _provision(repo_root)
    versions = _get(prov, "versions") if prov is not None and _get(prov, "ok") else {}
    field(json.dumps(versions, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return "sha256:" + digest.hexdigest()


def _record_path(repo_root, capability_id):
    return repo_root / "verification" / "capabilities" / capability_id / ".provenance.json"


def _check(capability_id, repo_root):
    products = _products(repo_root)
    if capability_id not in products:
        raise UnknownCapabilityError(f"unknown capability: {capability_id}")
    product = products[capability_id]
    components = _components(repo_root)
    realizing = _realizing(capability_id, components)
    content_hash = _content_hash(repo_root, product, realizing)
    result = {"hit": False, "capability_scenario_report": None}
    try:
        record = json.loads(
            _record_path(repo_root, capability_id).read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return result, content_hash, product, realizing
    if (
        isinstance(record, dict)
        and record.get("gate_version") == GATE_VERSION
        and record.get("content_hash") == content_hash
    ):
        result = {
            "hit": True,
            "capability_scenario_report": record.get("capability_scenario_report"),
        }
    return result, content_hash, product, realizing


def check_capability_provenance(capability_id, repo_root):
    return _check(capability_id, Path(repo_root))[0]


# ---------------------------------------------------------------------------
# Built-in callables (R-SCENARIO-007, R-SCENARIO-008)
# ---------------------------------------------------------------------------


def _interface_text(repo_root, realizing):
    blocks = []
    for comp in realizing:
        iface = repo_root / "specs" / "components" / comp["slug"] / "interface"
        texts = [
            p.read_text(encoding="utf-8")
            for p in sorted(iface.rglob("*.md"), key=lambda p: p.relative_to(iface).as_posix())
        ]
        blocks.append("\n".join([f"## {comp['id']}"] + texts))
    return "\n".join(blocks)


def _make_test_author(repo_root, product, realizing, model, seed, llm_backend):
    state = {}

    def test_author(bundle):
        if "module" not in state:
            state["module"] = _load_dependency(
                repo_root, Path("gen") / "test-author", "test_author"
            )
        glossary = repo_root / "specs" / "glossary.md"
        criterion_bundle = {
            "component_id": f"capabilities/{bundle['capability_id']}",
            "criterion_id": bundle["scenario_id"],
            "covers": bundle["covers"],
            "criterion_text": bundle["gherkin"],
            "requirement_text": product["text"],
            "interface": _interface_text(repo_root, realizing),
            "glossary": glossary.read_text(encoding="utf-8") if glossary.is_file() else "",
            "dependency_interfaces": {},
            "module_names": [c["slug"].replace("-", "_") for c in realizing],
        }
        return state["module"].author_test(
            criterion_bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    return test_author


def _judge_prompt(bundle, realizing):
    parts = [
        "You are judging whether a software system satisfies one capability scenario.",
        f"Covers: {bundle['covers']}",
        "Scenario:",
        "```gherkin",
        bundle["gherkin"],
        "```",
        "The full code of every component realizing this capability follows.",
    ]
    for comp in realizing:
        for rel, path in _code_files(comp["code_dir"], exclude_provenance=False):
            parts.append(f"### {comp['id']}: {rel}")
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    parts.append(
        'Reply with JSON only: {"result": "pass" | "fail", "rationale": "..."}'
    )
    return "\n".join(parts)


def _parse_judge_reply(text):
    text = (text or "").strip()
    lines = text.splitlines()
    fences = [i for i, line in enumerate(lines) if line.startswith("```")]
    if fences:
        end = fences[1] if len(fences) > 1 else len(lines)
        text = "\n".join(lines[fences[0] + 1:end])
    return json.loads(text)


def _make_judge(repo_root, realizing, model, llm_backend):
    state = {}

    def unavailable(reason):
        return {"result": "fail", "rationale": f"judge unavailable: {reason}"}

    def judge(bundle):
        if "module" not in state:
            state["module"] = _load_dependency(
                repo_root, Path("gen") / "llm-endpoint", "llm_endpoint"
            )
        response = state["module"].complete(
            _judge_prompt(bundle, realizing), model, backend=llm_backend
        )
        error = _get(response, "model_call_error")
        if error:
            return unavailable(_get(error, "message"))
        try:
            parsed = _parse_judge_reply(_get(response, "text"))
        except ValueError as exc:
            return unavailable(f"unparseable reply: {exc}")
        result = _get(parsed, "result")
        if result not in ("pass", "fail"):
            return unavailable(f"invalid result: {result!r}")
        return {"result": result, "rationale": _get(parsed, "rationale")}

    return judge


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    repo_root = Path(repo_root)
    result, content_hash, product, realizing = _check(capability_id, repo_root)
    if result["hit"]:
        return result
    if model is None:
        raise ModelRequiredError("a model is required to run capability scenarios")
    judge = _make_judge(repo_root, realizing, model, llm_backend)
    test_author = _make_test_author(repo_root, product, realizing, model, seed, llm_backend)
    entry = _Runner(repo_root).run_capability(
        product["scenarios"], realizing, judge, test_author
    )
    report = {capability_id: entry}
    record = {
        "capability_id": capability_id,
        "gate_version": GATE_VERSION,
        "content_hash": content_hash,
        "realizing_components": sorted(c["id"] for c in realizing),
        "capability_scenario_report": report,
        "model": model,
        "seed": seed,
    }
    path = _record_path(repo_root, capability_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"hit": False, "capability_scenario_report": report}
