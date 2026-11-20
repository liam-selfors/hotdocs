"""Review Packet Builder: assembles the human-readable review summary.

Formats already-computed results read from provenance-tracker's own
``check_readiness`` together with the PR's spec diff and exemption changes.
"""

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

_COMPONENT_MD_RE = re.compile(r"^specs/components/([^/]+)/component\.md$")
_OVERRIDES_RE = re.compile(r"^gen/([^/]+)/\.overrides\.json$")


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_provenance_tracker(repo_root):
    module_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not module_dir.is_dir():
        module_dir = _tool_root() / "gen" / "provenance-tracker"
    path = module_dir / "provenance_tracker.py"
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
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _diff_base(repo_root):
    head = (_git(repo_root, "rev-parse", "HEAD") or "").strip()
    candidates = []
    origin_head = _git(
        repo_root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"
    )
    if origin_head:
        candidates.append(origin_head.strip())
    candidates.extend(["main", "master"])
    base = None
    for branch in candidates:
        out = _git(repo_root, "merge-base", "HEAD", branch)
        if out is not None:
            base = out.strip()
            break
    if base is None or base == head:
        base = EMPTY_TREE
    return base


def _is_sealed(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            return False
        key, sep, value = line.partition(":")
        if sep and key.strip() == "sealed":
            return value.strip().lower() == "true"
    return False


def _sealed_at(repo_root, rev, path):
    text = _git(repo_root, "show", f"{rev}:{path}")
    return text is not None and _is_sealed(text)


def _exemption_changes(repo_root, base):
    names = (
        _git(repo_root, "diff", "--name-only", "--no-renames", base, "HEAD") or ""
    ).splitlines()
    sealed = set()
    overrides = set()
    for path in names:
        m = _COMPONENT_MD_RE.match(path)
        if m:
            if _sealed_at(repo_root, "HEAD", path):
                history = (
                    _git(repo_root, "log", "--follow", "--format=%H", "HEAD", "--", path)
                    or ""
                ).split()
                if history and not _sealed_at(repo_root, history[-1], path):
                    sealed.add("comp-" + m.group(1))
            continue
        m = _OVERRIDES_RE.match(path)
        if m:
            at_head = _git(repo_root, "cat-file", "-e", f"HEAD:{path}") is not None
            at_base = _git(repo_root, "cat-file", "-e", f"{base}:{path}") is not None
            if at_head and not at_base:
                overrides.add("comp-" + m.group(1))
    return {"sealed": sorted(sealed), "pinned_overrides": sorted(overrides)}


def build_review_packet(changed_ids, repo_root):
    repo_root = Path(repo_root)
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids=list(changed_ids))
    components = _get(report, "components") or {}
    capabilities = _get(report, "capabilities") or {}

    regenerated = sorted(components.keys())

    verification_results = {}
    provenance_hit_status = {}
    license_flags = []
    secret_flags = []
    residual_risk = []
    for cid in regenerated:
        entry = components[cid]
        vr = _get(entry, "verification_report")
        verification_results[cid] = vr
        provenance_hit_status[cid] = _get(entry, "hit")
        ls = _get(entry, "license_scan")
        if ls is not None and _get(ls, "blocked") is True:
            license_flags.append({"component_id": cid, "result": ls})
        ss = _get(entry, "secret_scan")
        if ss is not None and _get(ss, "flagged") is True:
            secret_flags.append({"component_id": cid, "result": ss})
        if vr is not None:
            score = _get(vr, "mutation_score")
            if _get(vr, "overall") == "pass" and score is not None and score < 1.0:
                residual_risk.append(
                    {
                        "component_id": cid,
                        "message": f"mutation_score {score} < 1.0 despite overall=pass",
                    }
                )

    capability_scenarios = {
        pid: _get(capabilities[pid], "capability_scenario_report")
        for pid in sorted(capabilities.keys())
    }

    base = _diff_base(repo_root)
    spec_diff = (
        _git(repo_root, "diff", "--no-color", "--no-ext-diff", base, "HEAD", "--", "specs/")
        or ""
    )

    return {
        "spec_diff": spec_diff,
        "changed_requirements": [i for i in changed_ids if i.startswith("R-")],
        "regenerated_components": regenerated,
        "verification_results": verification_results,
        "compliance_flags": {"license_scan": license_flags, "secret_scan": secret_flags},
        "provenance_hit_status": provenance_hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": _exemption_changes(repo_root, base),
        "residual_risk": residual_risk,
    }


def _dump(value):
    return json.dumps(value, sort_keys=True)


def _bullets(items):
    return [f"- {item}" for item in items] or ["(none)"]


def render_markdown(packet):
    lines = ["# Review Packet", ""]

    lines += ["## Spec Diff", ""]
    if packet["spec_diff"]:
        lines += ["```diff", packet["spec_diff"].rstrip("\n"), "```"]
    else:
        lines.append("(no spec changes)")
    lines.append("")

    lines += ["## Changed Requirements", ""]
    lines += _bullets(packet["changed_requirements"])
    lines.append("")

    lines += ["## Regenerated Components", ""]
    lines += _bullets(packet["regenerated_components"])
    lines.append("")

    lines += ["## Verification Results", ""]
    lines += _bullets(
        f"{cid}: {_dump(vr)}" for cid, vr in packet["verification_results"].items()
    )
    lines.append("")

    lines += ["## Compliance Flags", ""]
    lines += ["### License Scan", ""]
    lines += _bullets(
        f"{e['component_id']}: {_dump(e['result'])}"
        for e in packet["compliance_flags"]["license_scan"]
    )
    lines.append("")
    lines += ["### Secret Scan", ""]
    lines += _bullets(
        f"{e['component_id']}: {_dump(e['result'])}"
        for e in packet["compliance_flags"]["secret_scan"]
    )
    lines.append("")

    lines += ["## Provenance Hit Status", ""]
    lines += _bullets(
        f"{cid}: {_dump(hit)}" for cid, hit in packet["provenance_hit_status"].items()
    )
    lines.append("")

    exemptions = packet["exemption_changes"]
    lines += ["## Exemption Changes", ""]
    lines.append(f"**Sealed:** {', '.join(exemptions['sealed']) or '(none)'}")
    lines.append("")
    lines.append(
        f"**Pinned Overrides:** {', '.join(exemptions['pinned_overrides']) or '(none)'}"
    )
    lines.append("")

    lines += ["## Residual Risk", ""]
    lines += _bullets(
        f"{e['component_id']}: {e['message']}" for e in packet["residual_risk"]
    )
    lines.append("")

    lines += ["## Capability Scenarios", ""]
    lines += _bullets(
        f"{pid}: {_dump(rep)}" for pid, rep in packet["capability_scenarios"].items()
    )
    lines.append("")

    return "\n".join(lines)


def _usage_error(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv[:2] != ["review-packet", "build"]:
        return _usage_error("expected subcommand 'review-packet build'")
    changed = []
    repo_root = None
    fmt = "markdown"
    flags = ("--changed", "--repo-root", "--format")
    args = argv[2:]
    i = 0
    while i < len(args):
        token = args[i]
        name, eq, value = token.partition("=")
        if name not in flags:
            return _usage_error(f"unknown argument: {token}")
        if not eq:
            if i + 1 >= len(args):
                return _usage_error(f"{name} requires a value")
            i += 1
            value = args[i]
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
        print(render_markdown(packet))
    return 0
