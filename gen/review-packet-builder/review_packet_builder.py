"""Review Packet Builder.

Assembles the human-readable summary a reviewer reads before merging:
the spec diff, changed requirements, regenerated components, verification
results, compliance flags, provenance-hit status, capability scenarios,
exemption changes, and residual risk -- never the generated code itself.

Every upstream result is read from provenance-tracker's own
``check_readiness`` (R-PACKET-011, D90).
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

_DEFAULT_BRANCH_CANDIDATES = ("main", "master")
_SEALED_RE = re.compile(r"^sealed:\s*true\s*$", re.MULTILINE)
_COMPONENT_MD_RE = re.compile(r"^specs/components/([^/]+)/component\.md$")
_OVERRIDES_RE = re.compile(r"^gen/([^/]+)/\.overrides\.json$")


# --------------------------------------------------------------------------
# dependency loading (R-PACKET-013)
# --------------------------------------------------------------------------

def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_provenance_tracker(repo_root):
    dep_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / "provenance-tracker"
    path = dep_dir / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# --------------------------------------------------------------------------
# git helpers (R-PACKET-001, R-PACKET-007, R-PACKET-009)
# --------------------------------------------------------------------------

def _git(repo_root, *args):
    """Run git in repo_root; return stdout text, or None on any failure."""
    root = Path(repo_root)
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = str(root.resolve().parent)
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            env=env,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _default_branch(repo_root):
    out = _git(repo_root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if out and out.strip():
        return out.strip()
    for name in _DEFAULT_BRANCH_CANDIDATES:
        if _git(repo_root, "rev-parse", "--verify", "--quiet", name) is not None:
            return name
    return None


def _diff_base(repo_root):
    head = _git(repo_root, "rev-parse", "HEAD")
    branch = _default_branch(repo_root)
    merge_base = None
    if head is not None and branch is not None:
        merge_base = _git(repo_root, "merge-base", "HEAD", branch)
    if merge_base is None or merge_base.strip() == head.strip():
        return EMPTY_TREE
    return merge_base.strip()


def _spec_diff(repo_root, base):
    out = _git(repo_root, "diff", "--no-color", base, "HEAD", "--", "specs/")
    return out or ""


def _changed_paths(repo_root, base):
    out = _git(repo_root, "diff", "--name-only", base, "HEAD")
    return [line for line in (out or "").splitlines() if line]


def _is_sealed_at(repo_root, rev, path):
    text = _git(repo_root, "show", f"{rev}:{path}")
    return bool(text) and _SEALED_RE.search(text) is not None


def _first_commit(repo_root, path):
    out = _git(repo_root, "log", "--follow", "--format=%H", "--", path)
    lines = [line for line in (out or "").splitlines() if line.strip()]
    return lines[-1].strip() if lines else None


def _exists_at(repo_root, rev, path):
    return _git(repo_root, "cat-file", "-e", f"{rev}:{path}") is not None


def _exemption_changes(repo_root, base):
    sealed = set()
    pinned = set()
    for path in _changed_paths(repo_root, base):
        m = _COMPONENT_MD_RE.match(path)
        if m:
            first = _first_commit(repo_root, path)
            if (
                first is not None
                and _is_sealed_at(repo_root, "HEAD", path)
                and not _is_sealed_at(repo_root, first, path)
            ):
                sealed.add("comp-" + m.group(1))
            continue
        m = _OVERRIDES_RE.match(path)
        if m:
            if _exists_at(repo_root, "HEAD", path) and not _exists_at(repo_root, base, path):
                pinned.add("comp-" + m.group(1))
    return {"sealed": sorted(sealed), "pinned_overrides": sorted(pinned)}


# --------------------------------------------------------------------------
# library
# --------------------------------------------------------------------------

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
        if _get(ls, "blocked") is True:
            license_flags.append({"component_id": cid, "result": ls})
        ss = _get(entry, "secret_scan")
        if _get(ss, "flagged") is True:
            secret_flags.append({"component_id": cid, "result": ss})

        score = _get(vr, "mutation_score")
        if _get(vr, "overall") == "pass" and score is not None and score < 1.0:
            residual_risk.append({
                "component_id": cid,
                "message": f"mutation_score {score} < 1.0 despite overall=pass",
            })

    capability_scenarios = {
        pid: _get(capabilities[pid], "capability_scenario_report")
        for pid in sorted(capabilities.keys())
    }

    base = _diff_base(repo_root)

    return {
        "spec_diff": _spec_diff(repo_root, base),
        "changed_requirements": [i for i in changed_ids if i.startswith("R-")],
        "regenerated_components": regenerated,
        "verification_results": verification_results,
        "compliance_flags": {
            "license_scan": license_flags,
            "secret_scan": secret_flags,
        },
        "provenance_hit_status": provenance_hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": _exemption_changes(repo_root, base),
        "residual_risk": residual_risk,
    }


# --------------------------------------------------------------------------
# markdown rendering
# --------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, sort_keys=True)


def _bullets(items):
    return [f"- {item}" for item in items] or ["(none)"]


def render_markdown(packet):
    lines = ["# Review Packet", ""]

    lines += ["## Spec Diff", "", "```diff"]
    diff = packet["spec_diff"]
    if diff:
        lines.append(diff.rstrip("\n"))
    lines += ["```", ""]

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

    lines += ["## Capability Scenarios", ""]
    lines += _bullets(
        f"{pid}: {_dump(rep)}" for pid, rep in packet["capability_scenarios"].items()
    )
    lines.append("")

    flags = packet["compliance_flags"]
    lines += ["## License and Secret Scan", ""]
    lines += ["### License Scan", ""]
    lines += _bullets(
        f"{e['component_id']}: {_dump(e['result'])}" for e in flags["license_scan"]
    )
    lines.append("")
    lines += ["### Secret Scan", ""]
    lines += _bullets(
        f"{e['component_id']}: {_dump(e['result'])}" for e in flags["secret_scan"]
    )
    lines.append("")

    lines += ["## Provenance Hit Status", ""]
    lines += _bullets(
        f"{cid}: {_dump(hit)}" for cid, hit in packet["provenance_hit_status"].items()
    )
    lines.append("")

    ex = packet["exemption_changes"]
    lines += ["## Exemption Changes", "", "**Sealed:**"]
    lines += _bullets(ex["sealed"])
    lines += ["", "**Pinned Overrides:**"]
    lines += _bullets(ex["pinned_overrides"])
    lines.append("")

    lines += ["## Residual Risk", ""]
    lines += _bullets(
        f"{r['component_id']}: {r['message']}" for r in packet["residual_risk"]
    )
    lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI (R-PACKET-012)
# --------------------------------------------------------------------------

class _UsageError(Exception):
    pass


def _parse(argv):
    if list(argv[:2]) != ["review-packet", "build"]:
        raise _UsageError("usage: hotdocs review-packet build --changed=<spec-id>... "
                          "[--repo-root=<dir>] [--format=markdown|json]")
    changed = []
    repo_root = None
    fmt = "markdown"
    args = list(argv[2:])
    i = 0
    while i < len(args):
        arg = args[i]
        name, sep, value = arg.partition("=")
        if name not in ("--changed", "--repo-root", "--format"):
            raise _UsageError(f"unknown argument: {arg}")
        if not sep:
            if i + 1 >= len(args):
                raise _UsageError(f"{name} requires a value")
            i += 1
            value = args[i]
        if name == "--changed":
            changed.append(value)
        elif name == "--repo-root":
            repo_root = value
        else:
            fmt = value
        i += 1
    if not changed:
        raise _UsageError("--changed is required")
    if fmt not in ("markdown", "json"):
        raise _UsageError(f"invalid --format: {fmt}")
    return changed, Path(repo_root) if repo_root is not None else Path.cwd(), fmt


def main(argv):
    try:
        changed, repo_root, fmt = _parse(argv)
    except _UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        packet = build_review_packet(changed, repo_root)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if fmt == "json":
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(render_markdown(packet))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
