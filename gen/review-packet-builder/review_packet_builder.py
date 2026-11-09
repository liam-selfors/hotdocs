"""Review packet builder: formats already-computed provenance-tracker
results into the human-reviewable document posted on a PR."""

import dataclasses
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

EMPTY_TREE_HASH = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _to_jsonable(value):
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if dataclasses.is_dataclass(value):
        return _to_jsonable(dataclasses.asdict(value))
    if hasattr(value, "__dict__"):
        return _to_jsonable(vars(value))
    return str(value)


def _tool_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    raise RuntimeError("no 'gen' ancestor directory found above review_packet_builder module")


def _load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_provenance_tracker(repo_root):
    candidate_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not candidate_dir.is_dir():
        candidate_dir = _tool_root() / "gen" / "provenance-tracker"
    module_path = candidate_dir / "provenance_tracker.py"
    if not module_path.is_file():
        raise FileNotFoundError(f"provenance_tracker module not found at {module_path}")
    return _load_module_from_path("provenance_tracker", module_path)


def _git_run(repo_root, args):
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root)] + args,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _pr_diff_base(repo_root):
    head_out = _git_run(repo_root, ["rev-parse", "HEAD"])
    if head_out is None:
        return None, None
    head = head_out.strip()
    default_ref_out = _git_run(repo_root, ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"])
    default_ref = default_ref_out.strip() if default_ref_out else head
    merge_base_out = _git_run(repo_root, ["merge-base", head, default_ref])
    merge_base = merge_base_out.strip() if merge_base_out else None
    if merge_base is None or merge_base == head:
        base = EMPTY_TREE_HASH
    else:
        base = merge_base
    return head, base


def _compute_spec_diff(repo_root):
    head, base = _pr_diff_base(repo_root)
    if head is None:
        return ""
    diff = _git_run(repo_root, ["diff", base, head, "--", "specs/"])
    return diff if diff is not None else ""


def _parse_sealed(content):
    if not content:
        return False
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^sealed\s*:\s*(true|false)\s*$", line.strip(), re.IGNORECASE)
        if m:
            return m.group(1).lower() == "true"
    return False


def _is_sealed_transition(repo_root, head, path):
    log_out = _git_run(repo_root, ["log", "--follow", "--format=%H", head, "--", path])
    if not log_out:
        return False
    commits = [c for c in log_out.splitlines() if c]
    if not commits:
        return False
    first_commit = commits[-1]
    first_content = _git_run(repo_root, ["show", f"{first_commit}:{path}"])
    head_content = _git_run(repo_root, ["show", f"{head}:{path}"])
    return (not _parse_sealed(first_content)) and _parse_sealed(head_content)


def _file_exists_at_rev(repo_root, rev, path):
    return _git_run(repo_root, ["cat-file", "-e", f"{rev}:{path}"]) is not None


def _compute_exemption_changes(repo_root):
    sealed = []
    pinned_overrides = []
    head, base = _pr_diff_base(repo_root)
    if head is None:
        return {"sealed": sealed, "pinned_overrides": pinned_overrides}
    diff_names_out = _git_run(repo_root, ["diff", "--name-only", base, head])
    if diff_names_out is None:
        return {"sealed": sealed, "pinned_overrides": pinned_overrides}
    for path in diff_names_out.splitlines():
        path = path.strip()
        if not path:
            continue
        m = re.match(r"^specs/components/([^/]+)/component\.md$", path)
        if m:
            slug = m.group(1)
            if _is_sealed_transition(repo_root, head, path):
                sealed.append(f"comp-{slug}")
            continue
        m = re.match(r"^gen/([^/]+)/\.overrides\.json$", path)
        if m:
            slug = m.group(1)
            if _file_exists_at_rev(repo_root, head, path) and not _file_exists_at_rev(repo_root, base, path):
                pinned_overrides.append(f"comp-{slug}")
    return {"sealed": sorted(sealed), "pinned_overrides": sorted(pinned_overrides)}


def build_review_packet(changed_ids, repo_root):
    repo_root = Path(repo_root)
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids=list(changed_ids))

    components = _get(report, "components", {}) or {}
    capabilities = _get(report, "capabilities", {}) or {}

    changed_requirements = [cid for cid in changed_ids if isinstance(cid, str) and cid.startswith("R-")]

    verification_results = {}
    license_scan_flags = []
    secret_scan_flags = []
    provenance_hit_status = {}
    residual_risk = []

    for component_id, comp_result in components.items():
        verification_report_raw = _get(comp_result, "verification_report")
        verification_results[component_id] = _to_jsonable(verification_report_raw)

        license_scan_raw = _get(comp_result, "license_scan")
        if license_scan_raw is not None and _get(license_scan_raw, "blocked") is True:
            license_scan_flags.append({
                "component_id": component_id,
                "result": _to_jsonable(license_scan_raw),
            })

        secret_scan_raw = _get(comp_result, "secret_scan")
        if secret_scan_raw is not None and _get(secret_scan_raw, "flagged") is True:
            secret_scan_flags.append({
                "component_id": component_id,
                "result": _to_jsonable(secret_scan_raw),
            })

        provenance_hit_status[component_id] = _get(comp_result, "hit")

        if verification_report_raw is not None:
            overall = _get(verification_report_raw, "overall")
            mutation_score = _get(verification_report_raw, "mutation_score")
            if overall == "pass" and mutation_score is not None and mutation_score < 1.0:
                residual_risk.append({
                    "component_id": component_id,
                    "message": f"mutation_score {mutation_score} < 1.0 despite overall=pass",
                })

    capability_scenarios = {}
    for capability_id, cap_result in capabilities.items():
        capability_scenarios[capability_id] = _to_jsonable(_get(cap_result, "capability_scenario_report"))

    license_scan_flags.sort(key=lambda e: e["component_id"])
    secret_scan_flags.sort(key=lambda e: e["component_id"])
    residual_risk.sort(key=lambda e: e["component_id"])

    return {
        "spec_diff": _compute_spec_diff(repo_root),
        "changed_requirements": changed_requirements,
        "regenerated_components": sorted(components.keys()),
        "verification_results": verification_results,
        "compliance_flags": {
            "license_scan": license_scan_flags,
            "secret_scan": secret_scan_flags,
        },
        "provenance_hit_status": provenance_hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": _compute_exemption_changes(repo_root),
        "residual_risk": residual_risk,
    }


def _render_list_section(lines, items, formatter):
    if items:
        for item in items:
            lines.append(f"- {formatter(item)}")
    else:
        lines.append("(none)")


def _render_markdown(packet):
    lines = []

    lines.append("## Spec Diff")
    lines.append("")
    spec_diff = packet.get("spec_diff", "")
    if spec_diff.strip():
        lines.append("```diff")
        lines.append(spec_diff.rstrip("\n"))
        lines.append("```")
    else:
        lines.append("(no changes)")
    lines.append("")

    lines.append("## Changed Requirements")
    lines.append("")
    _render_list_section(lines, packet.get("changed_requirements", []), lambda r: r)
    lines.append("")

    lines.append("## Regenerated Components")
    lines.append("")
    _render_list_section(lines, packet.get("regenerated_components", []), lambda c: c)
    lines.append("")

    lines.append("## Verification Results")
    lines.append("")
    verification_results = packet.get("verification_results", {})
    _render_list_section(
        lines,
        sorted(verification_results.keys()),
        lambda cid: f"{cid}: {json.dumps(verification_results[cid], sort_keys=True)}",
    )
    lines.append("")

    lines.append("## Compliance Flags")
    lines.append("")
    lines.append("### License Scan")
    lines.append("")
    license_scan = packet.get("compliance_flags", {}).get("license_scan", [])
    _render_list_section(
        lines, license_scan,
        lambda e: f"{e['component_id']}: {json.dumps(e['result'], sort_keys=True)}",
    )
    lines.append("")
    lines.append("### Secret Scan")
    lines.append("")
    secret_scan = packet.get("compliance_flags", {}).get("secret_scan", [])
    _render_list_section(
        lines, secret_scan,
        lambda e: f"{e['component_id']}: {json.dumps(e['result'], sort_keys=True)}",
    )
    lines.append("")

    lines.append("## Provenance Hit Status")
    lines.append("")
    provenance_hit_status = packet.get("provenance_hit_status", {})
    _render_list_section(
        lines,
        sorted(provenance_hit_status.keys()),
        lambda cid: f"{cid}: {json.dumps(provenance_hit_status[cid], sort_keys=True)}",
    )
    lines.append("")

    lines.append("## Capability Scenarios")
    lines.append("")
    capability_scenarios = packet.get("capability_scenarios", {})
    _render_list_section(
        lines,
        sorted(capability_scenarios.keys()),
        lambda pid: f"{pid}: {json.dumps(capability_scenarios[pid], sort_keys=True)}",
    )
    lines.append("")

    lines.append("## Exemption Changes")
    lines.append("")
    exemption_changes = packet.get("exemption_changes", {})
    sealed = exemption_changes.get("sealed", [])
    pinned_overrides = exemption_changes.get("pinned_overrides", [])
    lines.append(f"**Sealed:** {json.dumps(sealed, sort_keys=True)}")
    lines.append(f"**Pinned Overrides:** {json.dumps(pinned_overrides, sort_keys=True)}")
    lines.append("")

    lines.append("## Residual Risk")
    lines.append("")
    residual_risk = packet.get("residual_risk", [])
    _render_list_section(
        lines, residual_risk,
        lambda e: f"{e['component_id']}: {e['message']}",
    )

    return "\n".join(lines) + "\n"


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) < 2 or argv[0] != "review-packet" or argv[1] != "build":
        return 2

    rest = argv[2:]
    changed_ids = []
    repo_root = Path(".")
    fmt = "markdown"

    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg.startswith("--changed="):
            changed_ids.append(arg[len("--changed="):])
            i += 1
        elif arg == "--changed":
            if i + 1 >= len(rest):
                return 2
            changed_ids.append(rest[i + 1])
            i += 2
        elif arg.startswith("--repo-root="):
            repo_root = Path(arg[len("--repo-root="):])
            i += 1
        elif arg == "--repo-root":
            if i + 1 >= len(rest):
                return 2
            repo_root = Path(rest[i + 1])
            i += 2
        elif arg.startswith("--format="):
            fmt = arg[len("--format="):]
            i += 1
        elif arg == "--format":
            if i + 1 >= len(rest):
                return 2
            fmt = rest[i + 1]
            i += 2
        else:
            return 2

    if not changed_ids:
        return 2
    if fmt not in ("markdown", "json"):
        return 2

    try:
        packet = build_review_packet(changed_ids, repo_root)
    except Exception:
        return 1

    if fmt == "json":
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(_render_markdown(packet))

    return 0


if __name__ == "__main__":
    sys.exit(main())