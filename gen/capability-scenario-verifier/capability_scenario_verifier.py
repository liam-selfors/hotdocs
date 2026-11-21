"""Capability scenario verifier.

Runs the capability scenarios of every product capability whose
`realizes`-set intersects a blast radius, against the real assembled
code, and records per-capability provenance keyed on actual content.
"""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import os
import re
import subprocess
import sys
from pathlib import Path

GATE_VERSION = "capability_scenario_verifier@2.2.0"

_SCENARIO_HEADING = re.compile(r"^###\s+(CS-[A-Za-z0-9-]+)")
_TEST_TIMEOUT_SECONDS = 120


class UnknownCapabilityError(ValueError):
    """No `specs/product/*.md` has the given capability id."""


class ModelRequiredError(ValueError):
    """A provenance miss needs a model to re-run scenarios."""


# --------------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------------

def _get(obj, key, default=None):
    """Dual dict-or-attribute access."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    return next(parent.parent for parent in here.parents if parent.name == "gen")


def _load_path(name: str, path: Path, package: bool = False):
    kwargs = {"submodule_search_locations": [str(path.parent)]} if package else {}
    spec = importlib.util.spec_from_file_location(name, str(path), **kwargs)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dep(repo_root: Path, rel_dir: str, name: str):
    directory = Path(repo_root) / rel_dir
    if not directory.is_dir():
        directory = _tool_root() / rel_dir
    flat = directory / f"{name}.py"
    if flat.is_file():
        return _load_path(name, flat)
    return _load_path(name, directory / name / "__init__.py", package=True)


def _provision(repo_root: Path):
    """The `python` adapter's provision(repo_root), or None with no adapter."""
    rel = Path("gen") / "kind-python" / "kind_python.py"
    path = Path(repo_root) / rel
    if not path.is_file():
        path = _tool_root() / rel
    if not path.is_file():
        return None
    adapter = _load_path("kind_python", path)
    return adapter.provision(Path(repo_root))


# --------------------------------------------------------------------------
# Corpus reading
# --------------------------------------------------------------------------

def _clean(value: str) -> str:
    return value.strip().strip("`").strip().strip("'\"")


def _frontmatter(text: str) -> dict:
    lines = text.splitlines()
    fields = {}
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip("'\"")
    return fields


def _list(value: str) -> list:
    return [_clean(item) for item in value.strip().strip("[]").split(",") if item.strip()]


def _components(repo_root: Path) -> dict:
    comps = {}
    for md in sorted((repo_root / "specs" / "components").glob("*/component.md")):
        fm = _frontmatter(md.read_text(encoding="utf-8"))
        slug = md.parent.name
        if fm.get("sealed") == "true":
            code_dir = repo_root / fm["source_path"]
        else:
            code_dir = repo_root / "gen" / slug
        comps[fm["id"]] = {
            "slug": slug,
            "realizes": _list(fm.get("realizes", "")),
            "code_dir": code_dir,
        }
    return comps


def _edges(comps: dict) -> list:
    """The `realizes` edges: (source_id, target_id)."""
    return [(cid, target) for cid, comp in comps.items() for target in comp["realizes"]]


def _capabilities(repo_root: Path) -> dict:
    caps = {}
    for md in sorted((repo_root / "specs" / "product").glob("*.md")):
        fm = _frontmatter(md.read_text(encoding="utf-8"))
        caps[fm.get("id")] = md
    return caps


def _realizing(capability_id: str, comps: dict) -> list:
    return sorted({source for source, target in _edges(comps) if target == capability_id})


def _scenarios(text: str) -> list:
    scenarios = []
    current = None
    in_gherkin = False
    for line in text.splitlines():
        if in_gherkin:
            if line.strip().startswith("```"):
                in_gherkin = False
            else:
                current["gherkin"].append(line)
            continue
        match = _SCENARIO_HEADING.match(line)
        if match:
            current = {"id": match.group(1), "covers": "", "kind": "", "gherkin": []}
            scenarios.append(current)
        elif line.startswith("#"):
            current = None
        elif current is not None:
            stripped = line.strip()
            if stripped.startswith("```gherkin"):
                in_gherkin = True
            elif stripped.startswith("Covers:"):
                current["covers"] = _clean(stripped[len("Covers:"):])
            elif stripped.startswith("Kind:"):
                current["kind"] = _clean(stripped[len("Kind:"):])
    for scenario in scenarios:
        scenario["gherkin"] = "\n".join(scenario["gherkin"])
    return scenarios


def _code_files(code_dir: Path, skip_provenance: bool) -> list:
    files = []
    for dirpath, dirnames, filenames in os.walk(code_dir):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_file() and not (skip_provenance and name == ".provenance.json"):
                files.append((path.relative_to(code_dir).as_posix(), path))
    return sorted(files)


# --------------------------------------------------------------------------
# Scenario execution
# --------------------------------------------------------------------------

class _Runner:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._provisioned = False
        self._interpreter = None

    def interpreter(self):
        if not self._provisioned:
            self._provisioned = True
            prov = _provision(self.repo_root)
            self._interpreter = _get(prov, "interpreter") if _get(prov, "ok") else None
        return self._interpreter

    def _write(self, rel: str, content) -> None:
        target = self.repo_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")

    def _run(self, rel: str, pythonpath: str) -> str:
        interpreter = self.interpreter()
        if interpreter is None:
            return "fail"
        env = dict(os.environ, PYTHONPATH=pythonpath)
        try:
            proc = subprocess.run(
                [str(interpreter), "-m", "pytest", "-q", "-p", "no:cacheprovider", rel],
                cwd=str(self.repo_root),
                env=env,
                timeout=_TEST_TIMEOUT_SECONDS,
                capture_output=True,
            )
        except (subprocess.TimeoutExpired, OSError):
            return "fail"
        return "pass" if proc.returncode == 0 else "fail"

    def compiled(self, bundle: dict, pythonpath: str) -> str:
        compiler = _load_dep(self.repo_root, "pipeline/criterion-compiler", "criterion_compiler")
        parsed = compiler.ParsedCriterion(
            criterion_id=bundle["scenario_id"],
            covers=bundle["covers"],
            kind=bundle["kind"],
            gherkin=bundle["gherkin"],
            file=bundle["file"],
        )
        outcome = compiler.compile_criterion(parsed, surface=None)
        if _get(outcome, "status") == "error":
            return "fail"
        name = bundle["scenario_id"].lower().replace("-", "_")
        rel = f"verification/capabilities/{bundle['capability_id']}/compiled/test_{name}.py"
        self._write(rel, _get(outcome, "source"))
        return self._run(rel, pythonpath)

    def generated(self, bundle: dict, test_author, pythonpath: str) -> str:
        if test_author is None:
            return "fail"
        outcome = test_author(bundle)
        test_file = _get(outcome, "file")
        if _get(outcome, "model_call_error") or not test_file:
            return "fail"
        rel = str(_get(test_file, "path"))
        parts = Path(rel).parts
        if len(parts) < 2 or parts[0] != "verification" or ".." in parts:
            return "fail"
        self._write(rel, _get(test_file, "content"))
        return self._run(rel, pythonpath)


def _judge_outcome(outcome):
    verdict = _get(outcome, "result", _get(outcome, "verdict", outcome))
    rationale = _get(outcome, "rationale", "")
    return ("pass" if verdict == "pass" else "fail"), rationale


def _overall(entries: list) -> str:
    results = [entry["result"] for entry in entries]
    if not results or "fail" in results:
        return "fail"
    if all(result == "skipped" for result in results):
        return "skipped"
    return "pass"


def _verify_capability(capability_id, comps, md, repo_root, judge, test_author, runner) -> dict:
    realizing = _realizing(capability_id, comps)
    pythonpath = os.pathsep.join(
        os.path.abspath(comps[cid]["code_dir"]) for cid in realizing
    )
    scenarios = _scenarios(md.read_text(encoding="utf-8")) if md is not None else []
    entries = []
    for scenario in scenarios:
        kind = scenario["kind"]
        bundle = {
            "capability_id": capability_id,
            "scenario_id": scenario["id"],
            "covers": scenario["covers"],
            "kind": kind,
            "gherkin": scenario["gherkin"],
            "file": md.relative_to(repo_root).as_posix(),
        }
        entry = {"id": scenario["id"], "kind": kind}
        if kind == "compiled":
            entry["result"] = runner.compiled(bundle, pythonpath)
        elif kind == "generated-test":
            entry["result"] = runner.generated(bundle, test_author, pythonpath)
        elif kind == "llm-judge":
            if judge is None:
                entry["result"] = "skipped"
            else:
                entry["result"], entry["rationale"] = _judge_outcome(judge(bundle))
        else:
            entry["result"] = "fail"
        entries.append(entry)
    return {"overall": _overall(entries), "scenarios": entries}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None) -> dict:
    repo_root = Path(repo_root)
    comps = _components(repo_root)
    caps = _capabilities(repo_root)
    radius = set(blast_radius)
    targets = sorted({target for source, target in _edges(comps) if source in radius})
    runner = _Runner(repo_root)
    return {
        cap: _verify_capability(cap, comps, caps.get(cap), repo_root, judge, test_author, runner)
        for cap in targets
    }


# --------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------

def _content_hash(repo_root: Path, md: Path, realizing: list, comps: dict) -> str:
    digest = hashlib.sha256()

    def field(data: bytes) -> None:
        digest.update(data)
        digest.update(b"\0")

    field(md.read_bytes())
    for cid in realizing:
        field(cid.encode("utf-8"))
        for rel, path in _code_files(comps[cid]["code_dir"], True):
            field(rel.encode("utf-8"))
            field(path.read_bytes())
    lock = repo_root / "environments" / "python" / "requirements.lock"
    if lock.is_file():
        field(lock.read_bytes())
    prov = _provision(repo_root)
    versions = _get(prov, "versions", {}) if _get(prov, "ok") else {}
    field(json.dumps(versions, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return "sha256:" + digest.hexdigest()


def _record_path(repo_root: Path, capability_id: str) -> Path:
    return repo_root / "verification" / "capabilities" / capability_id / ".provenance.json"


def _check(capability_id: str, repo_root: Path):
    comps = _components(repo_root)
    caps = _capabilities(repo_root)
    if capability_id not in caps:
        raise UnknownCapabilityError(f"unknown capability: {capability_id}")
    md = caps[capability_id]
    realizing = _realizing(capability_id, comps)
    key = _content_hash(repo_root, md, realizing, comps)
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
    return result, {"comps": comps, "md": md, "realizing": realizing, "key": key}


def check_capability_provenance(capability_id: str, repo_root) -> dict:
    result, _ = _check(capability_id, Path(repo_root))
    return result


# --------------------------------------------------------------------------
# Built callables
# --------------------------------------------------------------------------

def _make_test_author(capability_id, ctx, repo_root, model, seed, llm_backend):
    comps = ctx["comps"]
    realizing = ctx["realizing"]

    def call(bundle):
        module = _load_dep(repo_root, "gen/test-author", "test_author")
        interface_parts = []
        for cid in realizing:
            interface_parts.append(f"## {cid}")
            idir = repo_root / "specs" / "components" / comps[cid]["slug"] / "interface"
            for path in sorted(idir.rglob("*.md")):
                interface_parts.append(path.read_text(encoding="utf-8"))
        glossary = repo_root / "specs" / "glossary.md"
        criterion_bundle = {
            "component_id": f"capabilities/{capability_id}",
            "criterion_id": bundle["scenario_id"],
            "covers": bundle["covers"],
            "criterion_text": bundle["gherkin"],
            "requirement_text": ctx["md"].read_text(encoding="utf-8"),
            "interface": "\n".join(interface_parts),
            "glossary": glossary.read_text(encoding="utf-8") if glossary.is_file() else "",
            "dependency_interfaces": {},
            "module_names": [comps[cid]["slug"].replace("-", "_") for cid in realizing],
        }
        return module.author_test(
            criterion_bundle, model, seed=seed, repo_root=repo_root, llm_backend=llm_backend
        )

    return call


def _unavailable(reason) -> dict:
    return {"result": "fail", "rationale": f"judge unavailable: {reason}"}


def _parse_judge(response) -> dict:
    error = _get(response, "model_call_error")
    if error:
        return _unavailable(_get(error, "message"))
    text = str(_get(response, "text"))
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("```")), None)
    if start is None:
        body = text
    else:
        body = "\n".join(
            itertools.takewhile(lambda line: not line.startswith("```"), lines[start + 1:])
        )
    try:
        parsed = json.loads(body.strip())
    except ValueError:
        return _unavailable("unparseable reply")
    verdict = _get(parsed, "result")
    if verdict not in ("pass", "fail"):
        return _unavailable(f"invalid result: {verdict!r}")
    return {"result": verdict, "rationale": _get(parsed, "rationale", "")}


def _make_judge(ctx, repo_root, model, llm_backend):
    comps = ctx["comps"]
    realizing = ctx["realizing"]

    def call(bundle):
        endpoint = _load_dep(repo_root, "gen/llm-endpoint", "llm_endpoint")
        lines = [
            "You are judging whether a product capability scenario holds for the code below.",
            f"Covers: {bundle['covers']}",
            "Scenario (Gherkin):",
            bundle["gherkin"],
            "",
            "Code of every realizing component:",
        ]
        for cid in realizing:
            for rel, path in _code_files(comps[cid]["code_dir"], False):
                lines.append(f"--- {cid}: {rel} ---")
                lines.append(path.read_text(encoding="utf-8", errors="replace"))
        lines.append("")
        lines.append(
            'Reply with JSON only: {"result": "pass" | "fail", "rationale": "..."}'
        )
        response = endpoint.complete("\n".join(lines), model, backend=llm_backend)
        return _parse_judge(response)

    return call


# --------------------------------------------------------------------------
# Gate entry point
# --------------------------------------------------------------------------

def run_capability_gates(capability_id: str, repo_root, model=None, seed=0, llm_backend=None) -> dict:
    repo_root = Path(repo_root)
    result, ctx = _check(capability_id, repo_root)
    if result["hit"]:
        return result
    if model is None:
        raise ModelRequiredError(
            f"capability {capability_id} needs re-verification and no model was given"
        )
    test_author = _make_test_author(capability_id, ctx, repo_root, model, seed, llm_backend)
    judge = _make_judge(ctx, repo_root, model, llm_backend)
    entry = _verify_capability(
        capability_id, ctx["comps"], ctx["md"], repo_root, judge, test_author, _Runner(repo_root)
    )
    report = {capability_id: entry}
    record = {
        "capability_id": capability_id,
        "gate_version": GATE_VERSION,
        "content_hash": ctx["key"],
        "realizing_components": sorted(ctx["realizing"]),
        "capability_scenario_report": report,
        "model": model,
        "seed": seed,
    }
    path = _record_path(repo_root, capability_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"hit": False, "capability_scenario_report": report}
