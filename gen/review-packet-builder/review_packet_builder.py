"""Review Packet Builder.

Assembles the human-readable summary a reviewer reads before merging:
the spec diff, changed requirements, regenerated components,
verification results, compliance flags, provenance-hit status,
capability-scenario results, exemption changes and residual risk.
Every upstream result is read from ``provenance-tracker``'s own
``check_readiness``; this module only formats already-computed data.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
_DEFAULT_BRANCHES = ("main", "master")
_FLAGS = ("--changed", "--repo-root", "--format")
_FORMATS = ("markdown", "json")
_USAGE = (
    "usage: hotdocs review-packet build --changed=<spec-id>... "
    "[--repo-root=<dir>] [--format=markdown|json]"
)


def _get(obj, key):
    """Read ``key`` from a dict, or attribute ``key`` from an object."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _dep_dir(repo_root, rel):
    """Resolve a dependency directory: repo_root first, then the tool root."""
    candidate = Path(repo_root) / rel
    if candidate.is_dir():
        return candidate
    here = Path(__file__).resolve()
    gen_dir = next(p for p in here.parents if p.name == "gen")
    return gen_dir.parent / rel


def _load_provenance_tracker(repo_root):
    path = _dep_dir(repo_root, "gen/provenance-tracker") / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


def _git(repo_root, *args):
    """Run git in repo_root; any failure yields an empty result."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def _diff_base(repo_root):
    """The PR diff-base: merge-base of HEAD and the default branch, or the
    empty tree when that merge-base is HEAD itself."""
    head = _git(repo_root, "rev-parse", "--verify", "--quiet", "HEAD^{commit}").strip()
    for branch in _DEFAULT_BRANCHES:
        merge_base = _git(repo_root, "merge-base", "HEAD", branch).strip()
        if merge_base:
            return EMPTY_TREE if merge_base == head else merge_base
    return EMPTY_TREE


def _is_sealed(text):
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == "sealed":
            return value.strip().strip("'\"").lower() == "true"
    return False


def _sealed_changes(repo_root, base):
    sealed = []
    for path in _git(repo_root, "diff", "--name-only", base, "HEAD").splitlines():
        parts = path.split("/")
        if (
            len(parts) == 4
            and parts[0] == "specs"
            and parts[1] == "components"
            and parts[3] == "component.md"
            and _is_sealed(_git(repo_root, "show", "HEAD:" + path))
        ):
            history = _git(repo_root, "log", "--follow", "--format=%H", "--", path)
            first = "".join(history.split()[-1:])
            if not _is_sealed(_git(repo_root, "show", first + ":" + path)):
                sealed.append("comp-" + parts[2])
    return sorted(set(sealed))


def _override_changes(repo_root, base):
    overrides = []
    added = _git(repo_root, "diff", "--name-only", "--diff-filter=A", base, "HEAD")
    for path in added.splitlines():
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "gen" and parts[2] == ".overrides.json":
            overrides.append("comp-" + parts[1])
    return sorted(set(overrides))


def build_review_packet(changed_ids, repo_root):
    """Build the ReviewPacket for this PR."""
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids=list(changed_ids))
    components = _get(report, "components")
    capabilities = _get(report, "capabilities")

    regenerated = sorted(components)
    verification_results = {}
    provenance_hit_status = {}
    license_flags = []
    secret_flags = []
    residual_risk = []
    for cid in regenerated:
        entry = components[cid]
        report_vr = _get(entry, "verification_report")
        license_scan = _get(entry, "license_scan")
        secret_scan = _get(entry, "secret_scan")
        verification_results[cid] = report_vr
        provenance_hit_status[cid] = _get(entry, "hit")
        if _get(license_scan, "blocked") is True:
            license_flags.append({"component_id": cid, "result": license_scan})
        if _get(secret_scan, "flagged") is True:
            secret_flags.append({"component_id": cid, "result": secret_scan})
        score = _get(report_vr, "mutation_score")
        if _get(report_vr, "overall") == "pass" and score is not None and score < 1.0:
            residual_risk.append(
                {
                    "component_id": cid,
                    "message": "mutation_score %s < 1.0 despite overall=pass" % (score,),
                }
            )

    capability_scenarios = {
        pid: _get(capabilities[pid], "capability_scenario_report")
        for pid in sorted(capabilities)
    }

    base = _diff_base(repo_root)
    spec_diff = _git(repo_root, "diff", "--no-color", base, "HEAD", "--", "specs/")

    return {
        "spec_diff": spec_diff,
        "changed_requirements": [cid for cid in changed_ids if cid.startswith("R-")],
        "regenerated_components": regenerated,
        "verification_results": verification_results,
        "compliance_flags": {
            "license_scan": license_flags,
            "secret_scan": secret_flags,
        },
        "provenance_hit_status": provenance_hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": {
            "sealed": _sealed_changes(repo_root, base),
            "pinned_overrides": _override_changes(repo_root, base),
        },
        "residual_risk": residual_risk,
    }


def _dump(value):
    return json.dumps(value, sort_keys=True)


def _bullets(items):
    lines = ["- " + item for item in items]
    return lines or ["(none)"]


def render_markdown(packet):
    """Render a ReviewPacket as the markdown posted on a PR."""
    lines = ["# Review Packet", ""]

    lines += ["## Spec Diff", "", "```diff"]
    lines += packet["spec_diff"].splitlines()
    lines += ["```", ""]

    lines += ["## Changed Requirements", ""]
    lines += _bullets(packet["changed_requirements"])
    lines.append("")

    lines += ["## Regenerated Components", ""]
    lines += _bullets(packet["regenerated_components"])
    lines.append("")

    lines += ["## Verification Results", ""]
    lines += _bullets(
        "%s: %s" % (cid, _dump(value))
        for cid, value in sorted(packet["verification_results"].items())
    )
    lines.append("")

    lines += ["## Capability Scenarios", ""]
    lines += _bullets(
        "%s: %s" % (pid, _dump(value))
        for pid, value in sorted(packet["capability_scenarios"].items())
    )
    lines.append("")

    flags = packet["compliance_flags"]
    lines += ["## License and Secret Scan", "", "### License Scan", ""]
    lines += _bullets(
        "%s: %s" % (entry["component_id"], _dump(entry["result"]))
        for entry in flags["license_scan"]
    )
    lines += ["", "### Secret Scan", ""]
    lines += _bullets(
        "%s: %s" % (entry["component_id"], _dump(entry["result"]))
        for entry in flags["secret_scan"]
    )
    lines.append("")

    lines += ["## Provenance Hit Status", ""]
    lines += _bullets(
        "%s: %s" % (cid, _dump(hit))
        for cid, hit in sorted(packet["provenance_hit_status"].items())
    )
    lines.append("")

    exemptions = packet["exemption_changes"]
    lines += [
        "## Exemption Changes",
        "",
        "**Sealed:** " + (", ".join(exemptions["sealed"]) or "(none)"),
        "",
        "**Pinned Overrides:** " + (", ".join(exemptions["pinned_overrides"]) or "(none)"),
        "",
    ]

    lines += ["## Residual Risk", ""]
    lines += _bullets(
        "%s: %s" % (entry["component_id"], entry["message"])
        for entry in packet["residual_risk"]
    )

    return "\n".join(lines) + "\n"


def _usage_error():
    print(_USAGE, file=sys.stderr)
    return 2


def main(argv):
    """hotdocs review-packet build --changed=<spec-id>... [--repo-root=<dir>]
    [--format=markdown|json]"""
    argv = list(argv)
    if argv[:2] != ["review-packet", "build"]:
        return _usage_error()
    changed = []
    repo_root = "."
    fmt = "markdown"
    args = argv[2:]
    i = 0
    while i < len(args):
        name, sep, value = args[i].partition("=")
        if name not in _FLAGS:
            return _usage_error()
        if not sep:
            i += 1
            if i >= len(args):
                return _usage_error()
            value = args[i]
        if name == "--changed":
            changed.append(value)
        elif name == "--repo-root":
            repo_root = value
        else:
            fmt = value
        i += 1
    if not changed or fmt not in _FORMATS:
        return _usage_error()

    try:
        packet = build_review_packet(changed, Path(repo_root))
    except Exception as exc:  # a required upstream result was missing
        print("review-packet: upstream result missing: %s" % (exc,), file=sys.stderr)
        return 1

    if fmt == "json":
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render_markdown(packet))
    return 0
