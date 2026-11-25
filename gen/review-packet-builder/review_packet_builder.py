"""Review Packet Builder: assembles the human-readable review summary for a merge."""

from __future__ import annotations

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

_SEALED_PATH = re.compile(r"specs/components/([^/]+)/component\.md")
_OVERRIDES_PATH = re.compile(r"gen/([^/]+)/\.overrides\.json")


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _load_provenance_tracker(repo_root: Path):
    dep_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not dep_dir.is_dir():
        tool_root = None
        for parent in Path(__file__).resolve().parents:
            if parent.name == "gen":
                tool_root = parent.parent
                break
        dep_dir = tool_root / "gen" / "provenance-tracker"
    path = dep_dir / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


def _git(repo_root: Path, *args):
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _diff_base(repo_root: Path):
    head = _git(repo_root, "rev-parse", "HEAD")
    if head is None:
        return None
    head = head.strip()
    candidates = []
    origin = _git(repo_root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if origin is not None and origin.strip():
        candidates.append(origin.strip())
    candidates.extend(["main", "master"])
    for cand in candidates:
        mb = _git(repo_root, "merge-base", "HEAD", cand)
        if mb is not None and mb.strip():
            mb = mb.strip()
            if mb == head:
                return EMPTY_TREE
            return mb
    return EMPTY_TREE


def _is_sealed(text: str) -> bool:
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    if not m:
        return False
    return re.search(r"^sealed:\s*true\s*$", m.group(1), re.M) is not None


def _exists(repo_root: Path, rev: str, path: str) -> bool:
    return _git(repo_root, "cat-file", "-e", f"{rev}:{path}") is not None


def _exemption_changes(repo_root: Path, base):
    sealed = set()
    pinned = set()
    if base is None:
        return {"sealed": [], "pinned_overrides": []}
    names = _git(repo_root, "diff", "--name-only", base, "HEAD") or ""
    for path in names.splitlines():
        m = _SEALED_PATH.fullmatch(path)
        if m:
            head_text = _git(repo_root, "show", f"HEAD:{path}")
            if head_text is None or not _is_sealed(head_text):
                continue
            log = _git(repo_root, "log", "--follow", "--format=%H", "--", path) or ""
            commits = log.split()
            if not commits:
                continue
            first_text = _git(repo_root, "show", f"{commits[-1]}:{path}") or ""
            if not _is_sealed(first_text):
                sealed.add("comp-" + m.group(1))
            continue
        m = _OVERRIDES_PATH.fullmatch(path)
        if m:
            if _exists(repo_root, "HEAD", path) and not _exists(repo_root, base, path):
                pinned.add("comp-" + m.group(1))
    return {"sealed": sorted(sealed), "pinned_overrides": sorted(pinned)}


def build_review_packet(changed_ids: list[str], repo_root: Path) -> dict:
    repo_root = Path(repo_root)
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids=list(changed_ids))

    components = _get(report, "components") or {}
    capabilities = _get(report, "capabilities") or {}

    regenerated = sorted(components.keys())

    verification_results = {}
    provenance_hit_status = {}
    license_flags = []
    residual_risk = []
    for cid in regenerated:
        entry = components[cid]
        vr = _get(entry, "verification_report")
        verification_results[cid] = vr
        provenance_hit_status[cid] = bool(_get(entry, "hit"))
        ls = _get(entry, "license_scan")
        if ls is not None and _get(ls, "blocked") is True:
            license_flags.append({"component_id": cid, "result": ls})
        if vr is not None:
            score = _get(vr, "mutation_score")
            if (
                _get(vr, "overall") == "pass"
                and isinstance(score, (int, float))
                and score < 1.0
            ):
                residual_risk.append(
                    {
                        "component_id": cid,
                        "message": f"mutation_score {score} < 1.0 despite overall=pass",
                    }
                )

    secret_flags = []
    ss = _get(report, "secret_scan")
    if ss is not None and _get(ss, "flagged") is True:
        secret_flags.append({"component_id": None, "result": ss})

    capability_scenarios = {
        pid: _get(capabilities[pid], "capability_scenario_report")
        for pid in sorted(capabilities.keys())
    }

    base = _diff_base(repo_root)
    spec_diff = ""
    if base is not None:
        spec_diff = _git(repo_root, "diff", base, "HEAD", "--", "specs/") or ""

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


def _dump(value) -> str:
    return json.dumps(value, sort_keys=True)


def _bullets(items) -> list[str]:
    if not items:
        return ["(none)"]
    return [f"- {item}" for item in items]


def _mapping_lines(mapping) -> list[str]:
    if not mapping:
        return ["(none)"]
    return [f"- {key}: {_dump(mapping[key])}" for key in sorted(mapping)]


def render_markdown(packet: dict) -> str:
    lines = ["# Review Packet", ""]

    lines += ["## Spec Diff", ""]
    diff = packet["spec_diff"].rstrip("\n")
    if diff:
        lines += ["```diff", diff, "```"]
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
    lines += _mapping_lines(packet["verification_results"])
    lines.append("")

    flags = packet["compliance_flags"]
    lines += ["## Compliance Flags", "", "License- and secret-scan results.", ""]
    lines += ["### License Scan", ""]
    if flags["license_scan"]:
        for entry in flags["license_scan"]:
            lines.append(f"- {entry['component_id']}: {_dump(entry['result'])}")
    else:
        lines.append("(none)")
    lines.append("")
    lines += ["### Secret Scan", ""]
    if flags["secret_scan"]:
        for entry in flags["secret_scan"]:
            lines.append(f"- repository: {_dump(entry['result'])}")
    else:
        lines.append("(none)")
    lines.append("")

    lines += ["## Provenance Hit Status", ""]
    lines += _mapping_lines(packet["provenance_hit_status"])
    lines.append("")

    ex = packet["exemption_changes"]
    lines += ["## Exemption Changes", ""]
    lines.append("**Sealed:** " + (", ".join(ex["sealed"]) or "(none)"))
    lines.append("")
    lines.append("**Pinned Overrides:** " + (", ".join(ex["pinned_overrides"]) or "(none)"))
    lines.append("")

    lines += ["## Residual Risk", ""]
    if packet["residual_risk"]:
        for entry in packet["residual_risk"]:
            lines.append(f"- {entry['component_id']}: {entry['message']}")
    else:
        lines.append("(none)")
    lines.append("")

    lines += ["## Capability Scenarios", ""]
    lines += _mapping_lines(packet["capability_scenarios"])

    return "\n".join(lines) + "\n"


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv[:2] != ["review-packet", "build"]:
        return _usage_error("expected subcommand 'review-packet build'")

    changed: list[str] = []
    repo_root = None
    fmt = "markdown"
    rest = argv[2:]
    i = 0
    while i < len(rest):
        token = rest[i]
        name, sep, value = token.partition("=")
        if name not in ("--changed", "--repo-root", "--format"):
            return _usage_error(f"unknown argument: {token}")
        if not sep:
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
