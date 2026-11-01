"""Provenance tracker: live readiness checks and per-attempt history."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class UsageError(Exception):
    """Raised when check_readiness cannot proceed without more input."""


@dataclasses.dataclass
class VerifyReport:
    scope: str
    ready: bool
    components: Dict[str, Any] = dataclasses.field(default_factory=dict)
    capabilities: Dict[str, Any] = dataclasses.field(default_factory=dict)
    not_ready_reasons: List[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class AttemptRecord:
    attempt_id: str
    component_id: str
    timestamp: str
    spec_bundle_hash: str
    generation: Any
    verification: Optional[Any] = None


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _load_gen_module(repo_root: Path, slug: str, module_name: str):
    repo_root = Path(repo_root)
    base = repo_root / "gen" / slug
    flat_path = base / f"{module_name}.py"
    pkg_init = base / module_name / "__init__.py"

    if flat_path.is_file():
        file_path = flat_path
        search_locations = None
    elif pkg_init.is_file():
        file_path = pkg_init
        search_locations = [str(base / module_name)]
    else:
        raise ImportError(f"cannot locate module {module_name!r} under {base}")

    unique_name = f"_hotdocs_dep_{module_name}_{abs(hash(str(repo_root)))}"
    if unique_name in sys.modules:
        return sys.modules[unique_name]

    spec = importlib.util.spec_from_file_location(
        unique_name, str(file_path), submodule_search_locations=search_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


def _to_plain(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(v) for v in obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _to_plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if hasattr(obj, "__dict__"):
        return {k: _to_plain(v) for k, v in vars(obj).items()}
    return obj


_FRONTMATTER_KV = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")
_FRONTMATTER_LIST_ITEM = re.compile(r"^\s*-\s*(.*)$")


def _parse_frontmatter(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    lines = text[3:end].splitlines()
    result: Dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        match = _FRONTMATTER_KV.match(line)
        if not match:
            i += 1
            continue
        key, value = match.group(1), match.group(2).strip()
        if value == "":
            items: List[str] = []
            j = i + 1
            while j < len(lines) and _FRONTMATTER_LIST_ITEM.match(lines[j]):
                item = _FRONTMATTER_LIST_ITEM.match(lines[j]).group(1).strip().strip("\"'")
                items.append(item)
                j += 1
            result[key] = items
            i = j
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1]
            result[key] = [v.strip().strip("\"'") for v in inner.split(",") if v.strip()]
            i += 1
        else:
            result[key] = value.strip("\"'")
            i += 1
    return result


def _discover_all_components(repo_root: Path) -> List[str]:
    components_dir = repo_root / "specs" / "components"
    ids: List[str] = []
    if not components_dir.is_dir():
        return ids
    for comp_dir in sorted(components_dir.iterdir()):
        comp_md = comp_dir / "component.md"
        if not comp_md.is_file():
            continue
        frontmatter = _parse_frontmatter(comp_md)
        component_id = frontmatter.get("id")
        if component_id:
            ids.append(component_id)
    return ids


def _collect_realizes_edges(repo_root: Path) -> Dict[str, set]:
    components_dir = repo_root / "specs" / "components"
    edges: Dict[str, set] = {}
    if not components_dir.is_dir():
        return edges
    for comp_dir in sorted(components_dir.iterdir()):
        comp_md = comp_dir / "component.md"
        if not comp_md.is_file():
            continue
        frontmatter = _parse_frontmatter(comp_md)
        component_id = frontmatter.get("id")
        if not component_id:
            continue
        realizes = frontmatter.get("realizes") or []
        if isinstance(realizes, str):
            realizes = [realizes]
        for capability_id in realizes:
            edges.setdefault(capability_id, set()).add(component_id)
    return edges


def _discover_capability_ids(repo_root: Path) -> List[str]:
    product_dir = repo_root / "specs" / "product"
    ids: List[str] = []
    if not product_dir.is_dir():
        return ids
    for md in sorted(product_dir.glob("*.md")):
        frontmatter = _parse_frontmatter(md)
        capability_id = frontmatter.get("id")
        if capability_id:
            ids.append(capability_id)
    return ids


def _make_judge(model: Optional[str], seed: int, llm_backend: Any) -> Optional[Callable]:
    if model is None:
        return None

    def judge(bundle):
        backend_judge = _get(llm_backend, "judge")
        if backend_judge is None:
            return {"result": "skipped"}
        return backend_judge(bundle, model=model, seed=seed)

    return judge


def _make_test_author(model: Optional[str], seed: int, llm_backend: Any) -> Optional[Callable]:
    if model is None:
        return None

    def test_author(bundle):
        backend_test_author = _get(llm_backend, "test_author")
        if backend_test_author is None:
            return {"model_call_error": "no test_author backend configured", "file": None}
        return backend_test_author(bundle, model=model, seed=seed)

    return test_author


def _capability_overall(result: Any, capability_id: str) -> Any:
    report = _get(result, "capability_scenario_report")
    if report is None:
        return None
    nested = _get(report, capability_id)
    if nested is not None:
        return _get(nested, "overall")
    return _get(report, "overall")


def check_readiness(
    repo_root: Path,
    changed_ids: Optional[List[str]] = None,
    model: Optional[str] = None,
    seed: int = 0,
    llm_backend: Any = None,
) -> VerifyReport:
    repo_root = Path(repo_root)
    provenance_checker = _load_gen_module(repo_root, "provenance-checker", "provenance_checker")

    scope = "blast-radius" if changed_ids else "whole-corpus"

    if changed_ids:
        impact_analyzer = _load_gen_module(repo_root, "impact-analyzer", "impact_analyzer")
        blast_report = impact_analyzer.compute_blast_radius(list(changed_ids), repo_root)
        impacted = _get(blast_report, "impacted") or []
        component_ids = list(
            dict.fromkeys(_get(entry, "component_id") for entry in impacted)
        )
    else:
        component_ids = _discover_all_components(repo_root)

    components: Dict[str, Any] = {}
    not_ready_reasons: List[str] = []
    ready = True

    for component_id in component_ids:
        key = provenance_checker.current_provenance_key(component_id, repo_root)
        spec_bundle_hash = _get(key, "spec_bundle_hash")
        gate_versions = _get(key, "gate_versions")
        result = provenance_checker.check_provenance(
            component_id, spec_bundle_hash, gate_versions, repo_root
        )
        components[component_id] = result

        hit = _get(result, "hit")
        if not hit:
            ready = False
            not_ready_reasons.append(
                f"{component_id}: no provenance for current spec state — "
                f"run hotdocs generate {component_id}"
            )
            continue

        verification_report = _get(result, "verification_report")
        overall = _get(verification_report, "overall") if verification_report is not None else None
        if overall != "pass":
            ready = False
            requirement_results = _get(verification_report, "requirement_results") or {}
            failing = sorted(
                rid for rid, status in requirement_results.items() if status == "fail"
            )
            not_ready_reasons.append(
                f"{component_id}: verification failing ({', '.join(failing)})"
            )

        license_scan = _get(result, "license_scan")
        if license_scan is not None and _get(license_scan, "blocked"):
            ready = False
            not_ready_reasons.append(f"{component_id}: license_scan")

        secret_scan = _get(result, "secret_scan")
        if secret_scan is not None and _get(secret_scan, "flagged"):
            ready = False
            not_ready_reasons.append(f"{component_id}: secret_scan")

    capability_ids = _discover_capability_ids(repo_root)
    intersecting_capabilities: List[str] = []
    if capability_ids:
        edges = _collect_realizes_edges(repo_root)
        scope_set = set(component_ids)
        for capability_id in capability_ids:
            realizing = edges.get(capability_id, set())
            if realizing & scope_set:
                intersecting_capabilities.append(capability_id)

    capabilities: Dict[str, Any] = {}
    if intersecting_capabilities:
        capability_scenario_verifier = _load_gen_module(
            repo_root, "capability-scenario-verifier", "capability_scenario_verifier"
        )
        judge = _make_judge(model, seed, llm_backend)
        test_author = _make_test_author(model, seed, llm_backend)

        for capability_id in intersecting_capabilities:
            check_result = capability_scenario_verifier.check_capability_provenance(
                capability_id, repo_root
            )
            if not _get(check_result, "hit") and model is None:
                raise UsageError(
                    f"{capability_id}: no cached capability scenario result and no "
                    "--model supplied for a fresh run"
                )

            result = capability_scenario_verifier.run_capability_gates(
                capability_id, repo_root, judge=judge, test_author=test_author
            )
            capabilities[capability_id] = result

            overall = _capability_overall(result, capability_id)
            if overall != "pass":
                ready = False
                not_ready_reasons.append(f"{capability_id}: capability gate failing")

    return VerifyReport(
        scope=scope,
        ready=ready,
        components=components,
        capabilities=capabilities,
        not_ready_reasons=not_ready_reasons,
    )


def write_attempt_record(
    component_id: str,
    generation_result: Any,
    verification_report: Optional[Any],
    spec_bundle_hash: str,
    repo_root: Path,
) -> AttemptRecord:
    repo_root = Path(repo_root)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = f"{timestamp}-{uuid.uuid4().hex[:6]}"

    generation_plain = _to_plain(generation_result)
    verification_plain = _to_plain(verification_report) if verification_report is not None else None

    record = AttemptRecord(
        attempt_id=attempt_id,
        component_id=component_id,
        timestamp=timestamp,
        spec_bundle_hash=spec_bundle_hash,
        generation=generation_plain,
        verification=verification_plain,
    )

    dest_dir = repo_root / ".hotdocs" / "attempts" / component_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{attempt_id}.json"
    dest_path.write_text(json.dumps(dataclasses.asdict(record), indent=2), encoding="utf-8")

    return record


def last_requirement_failures(component_id: str, repo_root: Path) -> List[str]:
    repo_root = Path(repo_root)
    attempts_dir = repo_root / ".hotdocs" / "attempts" / component_id
    if not attempts_dir.is_dir():
        return []

    for path in sorted(attempts_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        verification = _get(data, "verification")
        if verification is None:
            continue
        requirement_results = _get(verification, "requirement_results") or {}
        return sorted(rid for rid, status in requirement_results.items() if status == "fail")

    return []


def _parse_common_flag(arg: str, args: List[str], index: int, name: str):
    prefix = f"--{name}="
    if arg.startswith(prefix):
        return arg[len(prefix):], index + 1
    if arg == f"--{name}":
        if index + 1 >= len(args):
            raise UsageError(f"--{name} requires a value")
        return args[index + 1], index + 2
    return None, None


def _cli_verify(args: List[str]) -> int:
    changed_ids: List[str] = []
    model: Optional[str] = None
    seed = 0
    repo_root = Path(".")
    fmt = "text"

    i = 0
    try:
        while i < len(args):
            arg = args[i]
            value, next_i = _parse_common_flag(arg, args, i, "changed")
            if next_i is not None:
                changed_ids.append(value)
                i = next_i
                continue
            value, next_i = _parse_common_flag(arg, args, i, "model")
            if next_i is not None:
                model = value
                i = next_i
                continue
            value, next_i = _parse_common_flag(arg, args, i, "seed")
            if next_i is not None:
                seed = int(value)
                i = next_i
                continue
            value, next_i = _parse_common_flag(arg, args, i, "repo-root")
            if next_i is not None:
                repo_root = Path(value)
                i = next_i
                continue
            value, next_i = _parse_common_flag(arg, args, i, "format")
            if next_i is not None:
                fmt = value
                i = next_i
                continue
            print(f"usage error: unknown argument {arg}", file=sys.stderr)
            return 2
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    if fmt not in ("json", "text"):
        print(f"usage error: invalid --format {fmt}", file=sys.stderr)
        return 2

    try:
        report = check_readiness(repo_root, changed_ids or None, model=model, seed=seed)
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    ready = _get(report, "ready")
    if fmt == "json":
        print(json.dumps(_to_plain(report), indent=2))
    else:
        print("ready" if ready else "not ready")
        for reason in _get(report, "not_ready_reasons") or []:
            print(reason)

    return 0 if ready else 1


def _cli_track(args: List[str]) -> int:
    if not args or args[0] != "feedback":
        print("usage error: expected 'feedback' subcommand", file=sys.stderr)
        return 2

    rest = args[1:]
    if not rest or rest[0].startswith("--"):
        print("usage error: missing <component-id>", file=sys.stderr)
        return 2

    component_id = rest[0]
    repo_root = Path(".")

    i = 1
    try:
        while i < len(rest):
            arg = rest[i]
            value, next_i = _parse_common_flag(arg, rest, i, "repo-root")
            if next_i is not None:
                repo_root = Path(value)
                i = next_i
                continue
            print(f"usage error: unknown argument {arg}", file=sys.stderr)
            return 2
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    failures = last_requirement_failures(component_id, repo_root)
    print(",".join(failures))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    if not argv:
        print("usage error: expected a command", file=sys.stderr)
        return 2

    verb, rest = argv[0], argv[1:]
    if verb == "verify":
        return _cli_verify(rest)
    if verb == "track":
        return _cli_track(rest)

    print(f"usage error: unknown command {verb}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())