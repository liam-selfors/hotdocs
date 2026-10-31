import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

EMPTY_TREE_HASH = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

_R_ID_RE = re.compile(r"^R-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*-\d+$")
_COMPONENT_MD_RE = re.compile(r"^specs/components/([^/]+)/component\.md$")
_OVERRIDES_RE = re.compile(r"^gen/([^/]+)/\.overrides\.json$")
_SEALED_RE = re.compile(r"^sealed\s*:\s*[\"']?(true|false)[\"']?\s*$", re.IGNORECASE)


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _run_git(args, repo_root):
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _head(repo_root):
    out = _run_git(["rev-parse", "HEAD"], repo_root)
    if out is None:
        return None
    out = out.strip()
    return out or None


def _default_branch(repo_root):
    out = _run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], repo_root)
    if out:
        ref = out.strip()
        parts = ref.split("/")
        if len(parts) >= 3:
            candidate = "/".join(parts[2:])
            if _run_git(["rev-parse", "--verify", candidate], repo_root) is not None:
                return candidate
    for candidate in ("main", "master", "origin/main", "origin/master"):
        if _run_git(["rev-parse", "--verify", candidate], repo_root) is not None:
            return candidate
    return None


def _pr_base(repo_root, head):
    default_branch = _default_branch(repo_root)
    if default_branch is not None:
        merge_base_out = _run_git(["merge-base", head, default_branch], repo_root)
        if merge_base_out:
            merge_base = merge_base_out.strip()
            if merge_base and merge_base != head:
                return merge_base
    return EMPTY_TREE_HASH


def _spec_diff(repo_root):
    head = _head(repo_root)
    if head is None:
        return ""
    base = _pr_base(repo_root, head)
    diff = _run_git(["diff", base, head, "--", "specs/"], repo_root)
    return diff if diff is not None else ""


def _file_first_commit(repo_root, path):
    out = _run_git(["log", "--follow", "--format=%H", "--", path], repo_root)
    if not out:
        return None
    hashes = [h for h in out.strip().splitlines() if h]
    if not hashes:
        return None
    return hashes[-1]


def _git_show(repo_root, rev, path):
    return _run_git(["show", "{}:{}".format(rev, path)], repo_root)


def _is_sealed(content):
    if not content:
        return False
    in_frontmatter = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            break
        if in_frontmatter:
            m = _SEALED_RE.match(stripped)
            if m:
                return m.group(1).lower() == "true"
    return False


def _exemption_changes(repo_root):
    head = _head(repo_root)
    if head is None:
        return {"sealed": [], "pinned_overrides": []}
    base = _pr_base(repo_root, head)
    diff_out = _run_git(["diff", "--name-only", base, head], repo_root)
    diff_paths = [p for p in diff_out.strip().splitlines() if p] if diff_out else []

    sealed = []
    pinned_overrides = []
    for path in diff_paths:
        m = _COMPONENT_MD_RE.match(path)
        if m:
            slug = m.group(1)
            first_commit = _file_first_commit(repo_root, path)
            if first_commit is None:
                continue
            sealed_first = _is_sealed(_git_show(repo_root, first_commit, path))
            sealed_head = _is_sealed(_git_show(repo_root, head, path))
            if not sealed_first and sealed_head:
                sealed.append("comp-{}".format(slug))
            continue
        m2 = _OVERRIDES_RE.match(path)
        if m2:
            slug = m2.group(1)
            exists_head = _git_show(repo_root, head, path) is not None
            exists_base = _git_show(repo_root, base, path) is not None
            if exists_head and not exists_base:
                pinned_overrides.append("comp-{}".format(slug))

    return {"sealed": sealed, "pinned_overrides": pinned_overrides}


def _load_provenance_tracker(repo_root):
    base = Path(repo_root) / "gen" / "provenance-tracker"
    flat_path = base / "provenance_tracker.py"
    pkg_path = base / "provenance_tracker" / "__init__.py"

    if flat_path.is_file():
        module_path = flat_path
        search_locations = None
    elif pkg_path.is_file():
        module_path = pkg_path
        search_locations = [str(pkg_path.parent)]
    else:
        raise ImportError(
            "provenance_tracker module not found under {}".format(base)
        )

    module_name = "provenance_tracker"
    spec = importlib.util.spec_from_file_location(
        module_name, module_path, submodule_search_locations=search_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def build_review_packet(changed_ids, repo_root):
    repo_root = Path(repo_root)

    spec_diff = _spec_diff(repo_root)
    changed_requirements = [i for i in changed_ids if _R_ID_RE.match(i)]
    exemption_changes = _exemption_changes(repo_root)

    pt_module = _load_provenance_tracker(repo_root)
    report = pt_module.check_readiness(repo_root=repo_root, changed_ids=list(changed_ids))

    components = _get(report, "components", {}) or {}
    capabilities = _get(report, "capabilities", {}) or {}

    regenerated_components = list(components.keys())

    verification_results = {}
    license_flags = []
    secret_flags = []
    provenance_hit_status = {}
    residual_risk = []

    for comp_id, comp_entry in components.items():
        verification_report = _get(comp_entry, "verification_report")
        verification_results[comp_id] = verification_report

        license_scan = _get(comp_entry, "license_scan")
        if license_scan is not None and _get(license_scan, "blocked") is True:
            license_flags.append({"component_id": comp_id, "result": license_scan})

        secret_scan = _get(comp_entry, "secret_scan")
        if secret_scan is not None and _get(secret_scan, "flagged") is True:
            secret_flags.append({"component_id": comp_id, "result": secret_scan})

        provenance_hit_status[comp_id] = bool(_get(comp_entry, "hit"))

        if verification_report is not None:
            overall = _get(verification_report, "overall")
            mutation_score = _get(verification_report, "mutation_score")
            if (
                overall == "pass"
                and isinstance(mutation_score, (int, float))
                and mutation_score < 1.0
            ):
                residual_risk.append(
                    {
                        "component_id": comp_id,
                        "message": "mutation_score {} < 1.0 despite overall=pass".format(
                            mutation_score
                        ),
                    }
                )

    capability_scenarios = {}
    for cap_id, cap_entry in capabilities.items():
        capability_scenarios[cap_id] = _get(cap_entry, "capability_scenario_report")

    return {
        "spec_diff": spec_diff,
        "changed_requirements": changed_requirements,
        "regenerated_components": regenerated_components,
        "verification_results": verification_results,
        "compliance_flags": {
            "license_scan": license_flags,
            "secret_scan": secret_flags,
        },
        "provenance_hit_status": provenance_hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": exemption_changes,
        "residual_risk": residual_risk,
    }


def _json_inline(value):
    return json.dumps(value, sort_keys=True)


def render_markdown(packet):
    lines = []
    lines.append("# Review Packet")
    lines.append("")

    lines.append("## Spec Diff")
    spec_diff = packet["spec_diff"]
    if spec_diff:
        lines.append("```diff")
        lines.append(spec_diff.rstrip("\n"))
        lines.append("```")
    else:
        lines.append("(no diff)")
    lines.append("")

    lines.append("## Changed Requirements")
    changed_requirements = packet["changed_requirements"]
    if changed_requirements:
        for r in changed_requirements:
            lines.append("- {}".format(r))
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("## Regenerated Components")
    regenerated_components = packet["regenerated_components"]
    if regenerated_components:
        for c in regenerated_components:
            lines.append("- {}".format(c))
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("## Verification Results")
    verification_results = packet["verification_results"]
    if verification_results:
        for comp_id, report in verification_results.items():
            lines.append("- {}: {}".format(comp_id, _json_inline(report)))
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("## Capability Scenarios")
    capability_scenarios = packet["capability_scenarios"]
    if capability_scenarios:
        for cap_id, report in capability_scenarios.items():
            lines.append("- {}: {}".format(cap_id, _json_inline(report)))
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("## Compliance Flags")
    compliance_flags = packet["compliance_flags"]
    lines.append("### License Scan")
    license_scan = compliance_flags["license_scan"]
    if license_scan:
        for entry in license_scan:
            lines.append(
                "- {}: {}".format(entry["component_id"], _json_inline(entry["result"]))
            )
    else:
        lines.append("(none)")
    lines.append("### Secret Scan")
    secret_scan = compliance_flags["secret_scan"]
    if secret_scan:
        for entry in secret_scan:
            lines.append(
                "- {}: {}".format(entry["component_id"], _json_inline(entry["result"]))
            )
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("## Provenance Hit Status")
    provenance_hit_status = packet["provenance_hit_status"]
    if provenance_hit_status:
        for comp_id, hit in provenance_hit_status.items():
            lines.append("- {}: {}".format(comp_id, "hit" if hit else "miss"))
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("## Exemption Changes")
    exemption_changes = packet["exemption_changes"]
    sealed = exemption_changes["sealed"]
    pinned_overrides = exemption_changes["pinned_overrides"]
    lines.append("**Sealed:** {}".format(", ".join(sealed) if sealed else "(none)"))
    lines.append(
        "**Pinned Overrides:** {}".format(
            ", ".join(pinned_overrides) if pinned_overrides else "(none)"
        )
    )
    lines.append("")

    lines.append("## Residual Risk")
    residual_risk = packet["residual_risk"]
    if residual_risk:
        for entry in residual_risk:
            lines.append("- {}: {}".format(entry["component_id"], entry["message"]))
    else:
        lines.append("(none)")

    return "\n".join(lines) + "\n"


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) < 2 or argv[0] != "review-packet" or argv[1] != "build":
        sys.stderr.write(
            "usage: hotdocs review-packet build --changed=<spec-id>... "
            "[--repo-root=<dir>] [--format=markdown|json]\n"
        )
        return 2

    changed_ids = []
    repo_root = "."
    fmt = "markdown"

    for arg in argv[2:]:
        if arg.startswith("--changed="):
            value = arg[len("--changed="):]
            changed_ids.extend([v for v in value.split(",") if v])
        elif arg.startswith("--repo-root="):
            repo_root = arg[len("--repo-root="):]
        elif arg.startswith("--format="):
            fmt = arg[len("--format="):]
        else:
            sys.stderr.write("usage error: unrecognized argument '{}'\n".format(arg))
            return 2

    if not changed_ids:
        sys.stderr.write("usage error: --changed is required\n")
        return 2

    if fmt not in ("markdown", "json"):
        sys.stderr.write("usage error: invalid --format '{}'\n".format(fmt))
        return 2

    try:
        packet = build_review_packet(changed_ids, Path(repo_root))
    except Exception as exc:
        sys.stderr.write("error: a required upstream result was missing: {}\n".format(exc))
        return 1

    if fmt == "json":
        print(json.dumps(packet, indent=2))
    else:
        print(render_markdown(packet), end="")

    return 0


if __name__ == "__main__":
    sys.exit(main())