"""Review Packet Builder: assembles the human-readable review summary."""

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

_FORMATS = ("markdown", "json")


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_provenance_tracker(repo_root):
    rel = Path("gen") / "provenance-tracker"
    base = Path(repo_root) / rel
    if not base.is_dir():
        base = _tool_root() / rel
    path = base / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


def _git(repo_root, *args):
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _default_branch(repo_root):
    out = _git(repo_root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if out is not None and out.strip():
        return out.strip()
    for name in ("main", "master"):
        if _git(repo_root, "rev-parse", "--verify", "--quiet", "refs/heads/" + name) is not None:
            return name
    return None


def _diff_base(repo_root):
    """Return (head_sha, base_rev) or None when HEAD cannot be resolved."""
    head = _git(repo_root, "rev-parse", "HEAD")
    if head is None:
        return None
    head = head.strip()
    base = None
    branch = _default_branch(repo_root)
    if branch is not None:
        mb = _git(repo_root, "merge-base", "HEAD", branch)
        if mb is not None and mb.strip():
            base = mb.strip()
    if base is None or base == head:
        base = EMPTY_TREE
    return head, base


def _show(repo_root, rev, path):
    return _git(repo_root, "show", "%s:%s" % (rev, path))


def _is_sealed(text):
    if not text:
        return False
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^sealed:\s*(.*?)\s*$", line)
        if m:
            return m.group(1).strip("\"'").lower() == "true"
    return False


def _first_commit(repo_root, path):
    out = _git(repo_root, "log", "--follow", "--format=%H", "--", path)
    if out is None:
        return None
    shas = [s for s in out.split() if s]
    if not shas:
        return None
    return shas[-1]


def _spec_diff_and_exemptions(repo_root):
    empty = ("", {"sealed": [], "pinned_overrides": []})
    resolved = _diff_base(repo_root)
    if resolved is None:
        return empty
    head, base = resolved
    diff = _git(repo_root, "diff", "--no-color", "--no-ext-diff", base, "HEAD", "--", "specs/")
    if diff is None:
        diff = ""
    names = _git(repo_root, "diff", "--name-only", "--no-renames", base, "HEAD")
    sealed = set()
    overrides = set()
    for path in (names or "").splitlines():
        parts = path.split("/")
        if len(parts) == 4 and parts[0] == "specs" and parts[1] == "components" \
                and parts[3] == "component.md":
            head_text = _show(repo_root, "HEAD", path)
            if not _is_sealed(head_text):
                continue
            first = _first_commit(repo_root, path)
            if first is None:
                continue
            if not _is_sealed(_show(repo_root, first, path)):
                sealed.add("comp-" + parts[2])
        elif len(parts) == 3 and parts[0] == "gen" and parts[2] == ".overrides.json":
            if _show(repo_root, "HEAD", path) is None:
                continue
            if _show(repo_root, base, path) is None:
                overrides.add("comp-" + parts[1])
    return diff, {"sealed": sorted(sealed), "pinned_overrides": sorted(overrides)}


def build_review_packet(changed_ids, repo_root):
    repo_root = Path(repo_root)
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids=list(changed_ids))

    components = _get(report, "components") or {}
    capabilities = _get(report, "capabilities") or {}

    regenerated = sorted(components.keys())
    verification_results = {}
    license_flags = []
    secret_flags = []
    hit_status = {}
    residual = []
    for cid in regenerated:
        entry = components[cid]
        vr = _get(entry, "verification_report")
        verification_results[cid] = vr
        lic = _get(entry, "license_scan")
        if _get(lic, "blocked") is True:
            license_flags.append({"component_id": cid, "result": lic})
        sec = _get(entry, "secret_scan")
        if _get(sec, "flagged") is True:
            secret_flags.append({"component_id": cid, "result": sec})
        hit_status[cid] = _get(entry, "hit")
        score = _get(vr, "mutation_score")
        if _get(vr, "overall") == "pass" and score is not None and score < 1.0:
            residual.append({
                "component_id": cid,
                "message": "mutation_score %s < 1.0 despite overall=pass" % score,
            })

    capability_scenarios = {}
    for pid in sorted(capabilities.keys()):
        capability_scenarios[pid] = _get(capabilities[pid], "capability_scenario_report")

    spec_diff, exemptions = _spec_diff_and_exemptions(repo_root)

    return {
        "spec_diff": spec_diff,
        "changed_requirements": [i for i in changed_ids if i.startswith("R-")],
        "regenerated_components": regenerated,
        "verification_results": verification_results,
        "compliance_flags": {"license_scan": license_flags, "secret_scan": secret_flags},
        "provenance_hit_status": hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": exemptions,
        "residual_risk": residual,
    }


def _dump(value):
    return json.dumps(value, sort_keys=True)


def render_markdown(packet):
    lines = ["# Review Packet", ""]

    lines.append("## Spec Diff")
    lines.append("")
    if packet["spec_diff"]:
        lines.append("```diff")
        lines.append(packet["spec_diff"].rstrip("\n"))
        lines.append("```")
    else:
        lines.append("(no spec changes)")
    lines.append("")

    lines.append("## Changed Requirements")
    lines.append("")
    lines.extend(["- " + r for r in packet["changed_requirements"]] or ["- (none)"])
    lines.append("")

    lines.append("## Regenerated Components")
    lines.append("")
    lines.extend(["- " + c for c in packet["regenerated_components"]] or ["- (none)"])
    lines.append("")

    lines.append("## Verification Results")
    lines.append("")
    vr = packet["verification_results"]
    lines.extend(["- %s: %s" % (c, _dump(vr[c])) for c in sorted(vr)] or ["- (none)"])
    lines.append("")

    lines.append("## Compliance Flags")
    lines.append("")
    for title, key in (("License Scan", "license_scan"), ("Secret Scan", "secret_scan")):
        lines.append("### " + title)
        lines.append("")
        entries = packet["compliance_flags"][key]
        lines.extend(
            ["- %s: %s" % (e["component_id"], _dump(e["result"])) for e in entries]
            or ["- (none)"]
        )
        lines.append("")

    lines.append("## Provenance Hit Status")
    lines.append("")
    hs = packet["provenance_hit_status"]
    lines.extend(["- %s: %s" % (c, _dump(hs[c])) for c in sorted(hs)] or ["- (none)"])
    lines.append("")

    lines.append("## Exemption Changes")
    lines.append("")
    ex = packet["exemption_changes"]
    lines.append("**Sealed:** " + (", ".join(ex["sealed"]) or "(none)"))
    lines.append("")
    lines.append("**Pinned Overrides:** " + (", ".join(ex["pinned_overrides"]) or "(none)"))
    lines.append("")

    lines.append("## Residual Risk")
    lines.append("")
    lines.extend(
        ["- %s: %s" % (r["component_id"], r["message"]) for r in packet["residual_risk"]]
        or ["- (none)"]
    )
    lines.append("")

    lines.append("## Capability Scenarios")
    lines.append("")
    cs = packet["capability_scenarios"]
    lines.extend(["- %s: %s" % (p, _dump(cs[p])) for p in sorted(cs)] or ["- (none)"])

    return "\n".join(lines) + "\n"


def _usage_error(cause):
    print("usage error: " + cause, file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv[:2] != ["review-packet", "build"]:
        return _usage_error("no subcommand")
    changed = []
    repo_root = None
    fmt = "markdown"
    flags = ("--changed", "--repo-root", "--format")
    i = 2
    while i < len(argv):
        tok = argv[i]
        name, sep, value = tok.partition("=")
        if name not in flags:
            return _usage_error("unknown argument: " + tok)
        if not sep:
            if i + 1 >= len(argv):
                return _usage_error(name + " requires a value")
            i += 1
            value = argv[i]
        if name == "--changed":
            changed.append(value)
        elif name == "--repo-root":
            repo_root = value
        else:
            fmt = value
        i += 1
    if not changed:
        return _usage_error("--changed is required")
    if fmt not in _FORMATS:
        return _usage_error("invalid --format: " + fmt)
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
