"""Review Packet Builder.

Assembles the human-readable summary a reviewer reads before merging: the
spec diff, changed requirements, regenerated components, verification
results, compliance flags, provenance-hit status, capability scenarios,
exemption changes and residual risk. Every non-git field is read from
provenance-tracker's own ``check_readiness`` (R-PACKET-011).
"""

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

_R_ID = re.compile(r"^R-[A-Z0-9-]+-\d+$")
_COMPONENT_MD = re.compile(r"^specs/components/([^/]+)/component\.md$")
_OVERRIDES = re.compile(r"^gen/([^/]+)/\.overrides\.json$")
_SEALED_LINE = re.compile(r"^sealed:\s*(\S+)\s*$", re.MULTILINE)

_FLAGS = ("--changed", "--repo-root", "--format")
_FORMATS = ("markdown", "json")


def _get(obj, key):
    """Dual dict-or-attribute access."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    return next(p for p in here.parents if p.name == "gen").parent


def _load_provenance_tracker(repo_root: Path):
    module_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not module_dir.is_dir():
        module_dir = _tool_root() / "gen" / "provenance-tracker"
    path = module_dir / "provenance_tracker.py"
    name = "provenance_tracker"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo_root: Path, *args: str):
    """Run git; return stdout text, or None on any failure (R-PACKET-009)."""
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
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _default_branch(repo_root: Path):
    ref = _git(repo_root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if ref and ref.strip():
        return ref.strip()
    for name in ("main", "master"):
        if _git(repo_root, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}") is not None:
            return name
    return None


def _is_sealed(text) -> bool:
    if text is None or not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    frontmatter = text[3:end] if end != -1 else text[3:]
    match = _SEALED_LINE.search(frontmatter)
    return bool(match) and match.group(1).lower() == "true"


def _git_sections(repo_root: Path):
    """Return (spec_diff, sealed, pinned_overrides) from git history."""
    head = _git(repo_root, "rev-parse", "HEAD")
    if head is None:
        return "", [], []
    head = head.strip()
    branch = _default_branch(repo_root)
    merge_base = _git(repo_root, "merge-base", "HEAD", branch) if branch else None
    if merge_base and merge_base.strip() != head:
        base = merge_base.strip()
    else:
        base = EMPTY_TREE

    spec_diff = _git(
        repo_root, "diff", "--no-color", "--no-ext-diff", base, "HEAD", "--", "specs/"
    ) or ""
    names = _git(repo_root, "diff", "--name-only", "--no-renames", base, "HEAD") or ""

    sealed = set()
    overrides = set()
    for path in names.splitlines():
        comp_match = _COMPONENT_MD.match(path)
        if comp_match:
            if not _is_sealed(_git(repo_root, "show", f"HEAD:{path}")):
                continue
            revs = (_git(repo_root, "log", "--follow", "--format=%H", "--", path) or "").split()
            if revs and not _is_sealed(_git(repo_root, "show", f"{revs[-1]}:{path}")):
                sealed.add("comp-" + comp_match.group(1))
            continue
        ov_match = _OVERRIDES.match(path)
        if ov_match:
            at_head = _git(repo_root, "cat-file", "-e", f"HEAD:{path}") is not None
            at_base = _git(repo_root, "cat-file", "-e", f"{base}:{path}") is not None
            if at_head and not at_base:
                overrides.add("comp-" + ov_match.group(1))
    return spec_diff, sorted(sealed), sorted(overrides)


def build_review_packet(changed_ids: list[str], repo_root: Path) -> dict:
    repo_root = Path(repo_root)
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids=list(changed_ids))
    components = _get(report, "components")
    capabilities = _get(report, "capabilities")

    component_ids = sorted(components)
    verification_results = {}
    provenance_hit_status = {}
    license_flags = []
    secret_flags = []
    residual_risk = []
    for cid in component_ids:
        entry = components[cid]
        vr = _get(entry, "verification_report")
        verification_results[cid] = vr
        provenance_hit_status[cid] = _get(entry, "hit")
        license_scan = _get(entry, "license_scan")
        if _get(license_scan, "blocked") is True:
            license_flags.append({"component_id": cid, "result": license_scan})
        secret_scan = _get(entry, "secret_scan")
        if _get(secret_scan, "flagged") is True:
            secret_flags.append({"component_id": cid, "result": secret_scan})
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

    spec_diff, sealed, pinned = _git_sections(repo_root)

    return {
        "spec_diff": spec_diff,
        "changed_requirements": [i for i in changed_ids if _R_ID.match(i)],
        "regenerated_components": component_ids,
        "verification_results": verification_results,
        "compliance_flags": {"license_scan": license_flags, "secret_scan": secret_flags},
        "provenance_hit_status": provenance_hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": {"sealed": sealed, "pinned_overrides": pinned},
        "residual_risk": residual_risk,
    }


def _dump(value) -> str:
    return json.dumps(value, sort_keys=True)


def _bullets(items: list[str]) -> list[str]:
    if not items:
        return ["(none)"]
    return [f"- {item}" for item in items]


def render_markdown(packet: dict) -> str:
    lines = ["# Review Packet", "", "## Spec Diff", ""]
    diff = packet["spec_diff"]
    if diff:
        lines += ["```diff", diff.rstrip("\n"), "```"]
    else:
        lines.append("(no spec changes)")

    lines += ["", "## Changed Requirements", ""]
    lines += _bullets(list(packet["changed_requirements"]))

    lines += ["", "## Regenerated Components", ""]
    lines += _bullets(list(packet["regenerated_components"]))

    lines += ["", "## Verification Results", ""]
    lines += _bullets([f"{k}: {_dump(v)}" for k, v in packet["verification_results"].items()])

    lines += ["", "## Capability Scenarios", ""]
    lines += _bullets([f"{k}: {_dump(v)}" for k, v in packet["capability_scenarios"].items()])

    flags = packet["compliance_flags"]
    lines += ["", "## License and Secret Scan", "", "### License Scan", ""]
    lines += _bullets([f"{e['component_id']}: {_dump(e['result'])}" for e in flags["license_scan"]])
    lines += ["", "### Secret Scan", ""]
    lines += _bullets([f"{e['component_id']}: {_dump(e['result'])}" for e in flags["secret_scan"]])

    lines += ["", "## Provenance Hit Status", ""]
    lines += _bullets([f"{k}: {_dump(v)}" for k, v in packet["provenance_hit_status"].items()])

    exemptions = packet["exemption_changes"]
    lines += [
        "",
        "## Exemption Changes",
        "",
        f"**Sealed:** {', '.join(exemptions['sealed']) or '(none)'}",
        "",
        f"**Pinned Overrides:** {', '.join(exemptions['pinned_overrides']) or '(none)'}",
    ]

    lines += ["", "## Residual Risk", ""]
    lines += _bullets([f"{e['component_id']}: {e['message']}" for e in packet["residual_risk"]])
    return "\n".join(lines)


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
    repo_root = "."
    fmt = "markdown"
    rest = argv[2:]
    i = 0
    while i < len(rest):
        token = rest[i]
        name, eq, value = token.partition("=")
        if name not in _FLAGS:
            return _usage_error(f"unknown argument: {token}")
        if not eq:
            i += 1
            if i >= len(rest):
                return _usage_error(f"{name} requires a value")
            value = rest[i]
        i += 1
        if name == "--changed":
            changed.append(value)
        elif name == "--repo-root":
            repo_root = value
        else:
            fmt = value
    if fmt not in _FORMATS:
        return _usage_error(f"invalid --format: {fmt}")
    if not changed:
        return _usage_error("--changed is required")
    try:
        packet = build_review_packet(changed, Path(repo_root))
    except Exception as exc:  # a required upstream result was missing
        print(str(exc), file=sys.stderr)
        return 1
    if fmt == "json":
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(render_markdown(packet))
    return 0
