"""Review Packet Builder: formats already-computed results into a reviewable packet."""

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

USAGE = (
    "usage: hotdocs review-packet build --changed=<spec-id>... "
    "[--repo-root=<dir>] [--format=markdown|json]"
)

_R_ID = re.compile(r"^R-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
_COMPONENT_MD = re.compile(r"^specs/components/([^/]+)/component\.md$")
_OVERRIDES = re.compile(r"^gen/([^/]+)/\.overrides\.json$")
_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
_SEALED = re.compile(r"^sealed:\s*(\S+)", re.M)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _load_provenance_tracker(repo_root):
    dep_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not dep_dir.is_dir():
        here = Path(__file__).resolve()
        tool_root = next(p.parent for p in here.parents if p.name == "gen")
        dep_dir = tool_root / "gen" / "provenance-tracker"
    path = dep_dir / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


def _git(repo_root, *args):
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return proc.stdout


def _diff_base(repo_root):
    head = _git(repo_root, "rev-parse", "HEAD")
    if head is None:
        return None
    head = head.strip()
    for ref in ("origin/HEAD", "main", "master"):
        merge_base = _git(repo_root, "merge-base", "HEAD", ref)
        if merge_base is not None:
            merge_base = merge_base.strip()
            return EMPTY_TREE if merge_base == head else merge_base
    return EMPTY_TREE


def _is_sealed(text):
    if text is None:
        return False
    fm = _FRONTMATTER.match(text)
    if fm is None:
        return False
    m = _SEALED.search(fm.group(1))
    return m is not None and m.group(1).lower() == "true"


def _exemption_changes(repo_root, base):
    sealed = set()
    overrides = set()
    if base is None:
        return {"sealed": [], "pinned_overrides": []}
    listing = _git(repo_root, "diff", "--name-status", "--no-renames", base, "HEAD") or ""
    for line in listing.splitlines():
        status, _, path = line.partition("\t")
        m = _COMPONENT_MD.match(path)
        if m and _is_sealed(_git(repo_root, "show", f"HEAD:{path}")):
            log = (_git(repo_root, "log", "--follow", "--format=%H", "--", path) or "").split()
            if log and not _is_sealed(_git(repo_root, "show", f"{log[-1]}:{path}")):
                sealed.add("comp-" + m.group(1))
        m = _OVERRIDES.match(path)
        if m and status.startswith("A"):
            overrides.add("comp-" + m.group(1))
    return {"sealed": sorted(sealed), "pinned_overrides": sorted(overrides)}


def build_review_packet(changed_ids, repo_root):
    repo_root = Path(repo_root)
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids=list(changed_ids))
    components = dict(_get(report, "components") or {})
    capabilities = dict(_get(report, "capabilities") or {})

    base = _diff_base(repo_root)
    spec_diff = ""
    if base is not None:
        spec_diff = _git(repo_root, "diff", base, "HEAD", "--", "specs/") or ""

    regenerated = sorted(components)
    verification_results = {}
    license_flags = []
    secret_flags = []
    hit_status = {}
    residual_risk = []
    for cid in regenerated:
        result = components[cid]
        vr = _get(result, "verification_report")
        verification_results[cid] = vr
        license_scan = _get(result, "license_scan")
        if _get(license_scan, "blocked") is True:
            license_flags.append({"component_id": cid, "result": license_scan})
        secret_scan = _get(result, "secret_scan")
        if _get(secret_scan, "flagged") is True:
            secret_flags.append({"component_id": cid, "result": secret_scan})
        hit_status[cid] = bool(_get(result, "hit"))
        score = _get(vr, "mutation_score")
        if _get(vr, "overall") == "pass" and score is not None and score < 1.0:
            residual_risk.append({
                "component_id": cid,
                "message": f"mutation_score {score} < 1.0 despite overall=pass",
            })

    capability_scenarios = {
        pid: _get(capabilities[pid], "capability_scenario_report")
        for pid in sorted(capabilities)
    }

    return {
        "spec_diff": spec_diff,
        "changed_requirements": sorted({i for i in changed_ids if _R_ID.match(i)}),
        "regenerated_components": regenerated,
        "verification_results": verification_results,
        "compliance_flags": {"license_scan": license_flags, "secret_scan": secret_flags},
        "provenance_hit_status": hit_status,
        "exemption_changes": _exemption_changes(repo_root, base),
        "residual_risk": residual_risk,
        "capability_scenarios": capability_scenarios,
    }


def _dump(value):
    return json.dumps(value, sort_keys=True)


def _lines(items):
    return items if items else ["(none)"]


def render_markdown(packet):
    out = ["# Review Packet", "", "## Spec Diff", "", "```diff"]
    out.append(packet["spec_diff"].rstrip("\n"))
    out += ["```", "", "## Changed Requirements", ""]
    out += _lines([f"- {r}" for r in packet["changed_requirements"]])
    out += ["", "## Regenerated Components", ""]
    out += _lines([f"- {c}" for c in packet["regenerated_components"]])
    out += ["", "## Verification Results", ""]
    out += _lines([f"- {c}: {_dump(v)}" for c, v in packet["verification_results"].items()])
    out += ["", "## Compliance Flags", "", "### License Scan", ""]
    flags = packet["compliance_flags"]
    out += _lines([f"- {e['component_id']}: {_dump(e['result'])}" for e in flags["license_scan"]])
    out += ["", "### Secret Scan", ""]
    out += _lines([f"- {e['component_id']}: {_dump(e['result'])}" for e in flags["secret_scan"]])
    out += ["", "## Provenance Hit Status", ""]
    out += _lines([
        f"- {c}: {_dump(h)} ({'hit' if h else 'miss'})"
        for c, h in packet["provenance_hit_status"].items()
    ])
    ex = packet["exemption_changes"]
    out += ["", "## Exemption Changes", ""]
    out.append("**Sealed:** " + (", ".join(ex["sealed"]) or "(none)"))
    out.append("")
    out.append("**Pinned Overrides:** " + (", ".join(ex["pinned_overrides"]) or "(none)"))
    out += ["", "## Residual Risk", ""]
    out += _lines([f"- {e['component_id']}: {e['message']}" for e in packet["residual_risk"]])
    out += ["", "## Capability Scenarios", ""]
    out += _lines([f"- {p}: {_dump(v)}" for p, v in packet["capability_scenarios"].items()])
    return "\n".join(out) + "\n"


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:2] != ["review-packet", "build"]:
        return _usage_error("expected subcommand 'review-packet build'")
    rest = args[2:]
    changed = []
    repo_root = None
    fmt = "markdown"
    i = 0
    while i < len(rest):
        token = rest[i]
        name, eq, value = token.partition("=")
        if name not in ("--changed", "--repo-root", "--format"):
            return _usage_error(f"unknown argument: {token}")
        if not eq:
            if i + 1 >= len(rest):
                return _usage_error(f"{name} requires a value")
            i += 1
            value = rest[i]
        if name == "--changed":
            changed.append(value)
        elif name == "--repo-root":
            repo_root = value
        else:
            fmt = value
        i += 1
    if fmt not in ("markdown", "json"):
        return _usage_error(f"invalid --format: {fmt}")
    if not changed:
        return _usage_error("--changed is required")
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    try:
        packet = build_review_packet(changed, root)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if fmt == "json":
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render_markdown(packet))
    return 0
