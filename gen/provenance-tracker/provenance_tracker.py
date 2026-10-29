"""hotdocs provenance-tracker: `hotdocs verify` / attempt-record history."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union


class UsageError(Exception):
    """Raised when `check_readiness` cannot proceed without a required input."""


@dataclass
class VerifyReport:
    scope: str
    ready: bool
    components: Dict[str, Any] = field(default_factory=dict)
    capabilities: Dict[str, Any] = field(default_factory=dict)
    not_ready_reasons: List[str] = field(default_factory=list)


@dataclass
class AttemptRecord:
    attempt_id: str
    component_id: str
    timestamp: str
    spec_bundle_hash: str
    generation: Dict[str, Any]
    verification: Optional[Dict[str, Any]]


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_plain(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return {k: _to_plain(v) for k, v in value.items()}
    if is_dataclass(value) and not isinstance(value, type):
        return _to_plain(asdict(value))
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "__dict__"):
        return {k: _to_plain(v) for k, v in vars(value).items()}
    return value


def _load_gen_module(repo_root: Union[str, Path], slug: str, module_name: str):
    repo_root = Path(repo_root)
    base = repo_root / "gen" / slug
    flat_path = base / f"{module_name}.py"
    pkg_path = base / module_name / "__init__.py"

    if flat_path.exists():
        path = flat_path
        submodule_search_locations = None
    elif pkg_path.exists():
        path = pkg_path
        submodule_search_locations = [str(pkg_path.parent)]
    else:
        raise ImportError(
            f"cannot locate module {module_name!r} for dependency {slug!r} under {base}"
        )

    unique_name = (
        f"_hotdocs_dyn__{slug.replace('-', '_')}__"
        f"{abs(hash(str(path.resolve())))}"
    )
    spec = importlib.util.spec_from_file_location(
        unique_name, path, submodule_search_locations=submodule_search_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


def _list_all_component_ids(repo_root: Path) -> List[str]:
    components_dir = repo_root / "specs" / "components"
    ids: List[str] = []
    if not components_dir.exists():
        return ids
    for child in sorted(components_dir.iterdir()):
        if child.is_dir() and (child / "component.md").exists():
            ids.append(f"comp-{child.name}")
    return ids


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _read_frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    return m.group(1) if m else ""


def _parse_realizes(frontmatter: str) -> List[str]:
    lines = frontmatter.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("realizes:"):
            continue
        rest = stripped[len("realizes:"):].strip()
        if rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1]
            return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
        if rest:
            return [rest.strip("'\"")]
        result: List[str] = []
        for sub in lines[i + 1:]:
            sub_stripped = sub.strip()
            if sub_stripped.startswith("- "):
                result.append(sub_stripped[2:].strip().strip("'\""))
            elif sub_stripped == "":
                continue
            else:
                break
        return result
    return []


def _collect_realizes_edges(repo_root: Path) -> Dict[str, set]:
    components_dir = repo_root / "specs" / "components"
    capability_realizers: Dict[str, set] = {}
    if not components_dir.exists():
        return capability_realizers
    for child in sorted(components_dir.iterdir()):
        component_md = child / "component.md"
        if not component_md.exists():
            continue
        component_id = f"comp-{child.name}"
        frontmatter = _read_frontmatter(component_md)
        for cap_id in _parse_realizes(frontmatter):
            capability_realizers.setdefault(cap_id, set()).add(component_id)
    return capability_realizers


_ID_RE = re.compile(r"^id:\s*(\S+)", re.MULTILINE)


def _list_product_capability_ids(repo_root: Path) -> set:
    product_dir = repo_root / "specs" / "product"
    ids: set = set()
    if not product_dir.exists():
        return ids
    for f in sorted(product_dir.glob("*.md")):
        frontmatter = _read_frontmatter(f)
        m = _ID_RE.search(frontmatter)
        if m:
            ids.add(m.group(1).strip("'\""))
    return ids


def _compute_spec_bundle_hash(repo_root: Path, slug: str) -> str:
    component_dir = repo_root / "specs" / "components" / slug
    parts: List[str] = []
    if component_dir.exists():
        for path in sorted(component_dir.rglob("*")):
            if not path.is_file():
                continue
            rel_parts = path.relative_to(component_dir).parts
            if "acceptance" in rel_parts:
                continue
            parts.append("/".join(rel_parts))
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    glossary_path = repo_root / "specs" / "glossary.md"
    if glossary_path.exists():
        parts.append("glossary.md")
        parts.append(glossary_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _build_judge(
    model: Optional[str], seed: int, llm_backend: Any
) -> Optional[Callable[[Any], Any]]:
    if model is None:
        return None

    def judge(bundle: Any) -> Any:
        if llm_backend is not None and hasattr(llm_backend, "judge"):
            return llm_backend.judge(bundle, model=model, seed=seed)
        return None

    return judge


def _build_test_author(
    model: Optional[str], seed: int, llm_backend: Any
) -> Optional[Callable[[Any], Any]]:
    if model is None:
        return None

    def test_author(bundle: Any) -> Any:
        if llm_backend is not None and hasattr(llm_backend, "test_author"):
            return llm_backend.test_author(bundle, model=model, seed=seed)
        return None

    return test_author


def check_readiness(
    repo_root: Path,
    changed_ids: Optional[List[str]] = None,
    model: Optional[str] = None,
    seed: int = 0,
    llm_backend: Any = None,
) -> VerifyReport:
    repo_root = Path(repo_root)
    provenance_checker = _load_gen_module(
        repo_root, "provenance-checker", "provenance_checker"
    )

    if changed_ids:
        impact_analyzer = _load_gen_module(
            repo_root, "impact-analyzer", "impact_analyzer"
        )
        blast_radius_report = impact_analyzer.compute_blast_radius(
            list(changed_ids), repo_root
        )
        impacted = _get(blast_radius_report, "impacted", []) or []
        component_ids = sorted(
            {_get(entry, "component_id") for entry in impacted}
        )
        scope = "blast-radius"
    else:
        component_ids = _list_all_component_ids(repo_root)
        scope = "whole-corpus"

    scope_set = set(component_ids)

    components_result: Dict[str, Any] = {}
    not_ready_reasons: List[str] = []
    all_components_ready = True

    for component_id in sorted(scope_set):
        slug = (
            component_id[len("comp-"):]
            if component_id.startswith("comp-")
            else component_id
        )
        spec_bundle_hash = _compute_spec_bundle_hash(repo_root, slug)
        result = provenance_checker.check_provenance(
            component_id, spec_bundle_hash, {}, repo_root
        )
        components_result[component_id] = result
        hit = _get(result, "hit")
        if not hit:
            all_components_ready = False
            not_ready_reasons.append(
                f"{component_id}: no provenance for current spec state — "
                f"run hotdocs generate {component_id}"
            )
            continue

        verification_report = _get(result, "verification_report")
        overall = _get(verification_report, "overall")
        license_scan = _get(result, "license_scan")
        secret_scan = _get(result, "secret_scan")
        blocked = bool(_get(license_scan, "blocked")) if license_scan is not None else False
        flagged = bool(_get(secret_scan, "flagged")) if secret_scan is not None else False
        if overall != "pass" or blocked or flagged:
            all_components_ready = False
            not_ready_reasons.append(
                f"{component_id}: provenance hit but verification/scan not passing"
            )

    capability_realizers = _collect_realizes_edges(repo_root)
    product_capability_ids = _list_product_capability_ids(repo_root)
    intersecting_capabilities = sorted(
        cap_id
        for cap_id, realizers in capability_realizers.items()
        if cap_id in product_capability_ids and (realizers & scope_set)
    )

    capabilities_result: Dict[str, Any] = {}
    all_capabilities_ready = True

    if intersecting_capabilities:
        capability_scenario_verifier = _load_gen_module(
            repo_root, "capability-scenario-verifier", "capability_scenario_verifier"
        )
        for capability_id in intersecting_capabilities:
            check_result = capability_scenario_verifier.check_capability_provenance(
                capability_id, repo_root
            )
            hit = _get(check_result, "hit")
            if hit:
                result = check_result
            else:
                if model is None:
                    raise UsageError(
                        f"{capability_id}: capability scenario provenance is a "
                        "miss and no --model was supplied to run a fresh check"
                    )
                judge = _build_judge(model, seed, llm_backend)
                test_author = _build_test_author(model, seed, llm_backend)
                result = capability_scenario_verifier.run_capability_gates(
                    capability_id, repo_root, judge=judge, test_author=test_author
                )
            capabilities_result[capability_id] = result

            report = _get(result, "capability_scenario_report")
            entry = _get(report, capability_id) if report is not None else None
            overall = _get(entry, "overall") if entry is not None else None
            if overall != "pass":
                all_capabilities_ready = False
                not_ready_reasons.append(
                    f"{capability_id}: capability scenario check not passing"
                )

    ready = all_components_ready and all_capabilities_ready

    return VerifyReport(
        scope=scope,
        ready=ready,
        components=components_result,
        capabilities=capabilities_result,
        not_ready_reasons=not_ready_reasons,
    )


def write_attempt_record(
    component_id: str,
    generation_result: Any,
    verification_report: Any,
    spec_bundle_hash: str,
    repo_root: Union[str, Path],
) -> AttemptRecord:
    repo_root = Path(repo_root)
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    attempt_id = f"{timestamp}-{uuid.uuid4().hex[:6]}"

    generation_plain = _to_plain(generation_result)
    verification_plain = (
        _to_plain(verification_report) if verification_report is not None else None
    )

    record = AttemptRecord(
        attempt_id=attempt_id,
        component_id=component_id,
        timestamp=timestamp,
        spec_bundle_hash=spec_bundle_hash,
        generation=generation_plain,
        verification=verification_plain,
    )

    attempts_dir = repo_root / ".hotdocs" / "attempts" / component_id
    attempts_dir.mkdir(parents=True, exist_ok=True)
    out_path = attempts_dir / f"{attempt_id}.json"
    out_path.write_text(json.dumps(asdict(record), indent=2), encoding="utf-8")

    return record


def last_requirement_failures(component_id: str, repo_root: Union[str, Path]) -> List[str]:
    repo_root = Path(repo_root)
    attempts_dir = repo_root / ".hotdocs" / "attempts" / component_id
    if not attempts_dir.exists():
        return []

    for attempt_file in sorted(attempts_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(attempt_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        verification = data.get("verification")
        if verification is None:
            continue
        requirement_results = verification.get("requirement_results", {}) or {}
        return [rid for rid, status in requirement_results.items() if status == "fail"]

    return []


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs")
    sub = parser.add_subparsers(dest="command")

    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--changed", action="append", default=[])
    verify_parser.add_argument("--model")
    verify_parser.add_argument("--seed", type=int, default=0)
    verify_parser.add_argument("--repo-root", default=".")
    verify_parser.add_argument("--format", choices=["json", "text"], default="text")

    track_parser = sub.add_parser("track")
    track_sub = track_parser.add_subparsers(dest="track_command")
    feedback_parser = track_sub.add_parser("feedback")
    feedback_parser.add_argument("component_id")
    feedback_parser.add_argument("--repo-root", default=".")

    args = parser.parse_args(argv)

    if args.command == "verify":
        repo_root = Path(args.repo_root).resolve()
        try:
            report = check_readiness(
                repo_root,
                changed_ids=args.changed or None,
                model=args.model,
                seed=args.seed,
            )
        except UsageError as exc:
            print(str(exc), file=sys.stderr)
            return 2

        if args.format == "json":
            print(json.dumps(asdict(report), indent=2, default=_to_plain))
        else:
            print(f"ready: {report.ready}")
            for reason in report.not_ready_reasons:
                print(reason)
        return 0 if report.ready else 1

    if args.command == "track" and args.track_command == "feedback":
        repo_root = Path(args.repo_root).resolve()
        failures = last_requirement_failures(args.component_id, repo_root)
        print(",".join(failures))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())