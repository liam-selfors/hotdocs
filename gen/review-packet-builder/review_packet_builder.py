"""Review Packet Builder: assembles the human-readable merge review summary.

Formats already-computed results read entirely from provenance-tracker's own
``check_readiness`` (R-PACKET-011) plus the PR's spec diff and exemption
changes read from git (R-PACKET-001, R-PACKET-007).
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
DEFAULT_BRANCH_CANDIDATES = ("origin/HEAD", "main", "master")

USAGE = (
    "usage: hotdocs review-packet build --changed=<spec-id>... "
    "[--repo-root=<dir>] [--format=markdown|json]"
)

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)
_SEALED_TRUE = re.compile(r"^sealed:\s*true\s*$", re.MULTILINE | re.IGNORECASE)
_COMPONENT_MD = re.compile(r"^specs/components/([^/]+)/component\.md$")
_OVERRIDES = re.compile(r"^gen/([^/]+)/\.overrides\.json$")


def _get(obj, key):
    """Dual dict-or-attribute access for any dependency-provided value."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _load_provenance_tracker(repo_root: Path):
    dep_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / "provenance-tracker"
    path = dep_dir / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
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
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _diff_base(repo_root: Path, head: str) -> str:
    merge_base = head
    for candidate in DEFAULT_BRANCH_CANDIDATES:
        out = _git(repo_root, "merge-base", "HEAD", candidate)
        if out:
            merge_base = out.strip()
            break
    return EMPTY_TREE if merge_base == head else merge_base


def _sealed_at(repo_root: Path, rev: str, path: str) -> bool:
    text = _git(repo_root, "show", f"{rev}:{path}") or ""
    match = _FRONTMATTER.match(text)
    return bool(match and _SEALED_TRUE.search(match.group(1)))


def _git_sections(repo_root: Path):
    """Return (spec_diff, exemption_changes) read from git, empty on failure."""
    exemptions = {"sealed": [], "pinned_overrides": []}
    head_out = _git(repo_root, "rev-parse", "HEAD")
    if not head_out:
        return "", exemptions
    head = head_out.strip()
    base = _diff_base(repo_root, head)

    spec_diff = (
        _git(repo_root, "diff", "--no-color", "--no-ext-diff", base, "HEAD", "--", "specs/")
        or ""
    )

    names = (_git(repo_root, "diff", "--name-only", base, "HEAD") or "").splitlines()
    sealed = set()
    overrides = set()
    for name in names:
        comp = _COMPONENT_MD.match(name)
        if comp and _sealed_at(repo_root, "HEAD", name):
            revs = (
                _git(repo_root, "log", "--follow", "--format=%H", "HEAD", "--", name) or ""
            ).split()
            if not _sealed_at(repo_root, (revs or ["HEAD"])[-1], name):
                sealed.add("comp-" + comp.group(1))
        over = _OVERRIDES.match(name)
        if (
            over
            and _git(repo_root, "cat-file", "-e", f"HEAD:{name}") is not None
            and _git(repo_root, "cat-file", "-e", f"{base}:{name}") is None
        ):
            overrides.add("comp-" + over.group(1))
    exemptions["sealed"] = sorted(sealed)
    exemptions["pinned_overrides"] = sorted(overrides)
    return spec_diff, exemptions


def build_review_packet(changed_ids: list[str], repo_root: Path) -> dict:
    repo_root = Path(repo_root)
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids=changed_ids)

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
            residual_risk.append(
                {
                    "component_id": cid,
                    "message": f"mutation_score {score} < 1.0 despite overall=pass",
                }
            )

    capability_scenarios = {
        pid: _get(capabilities[pid], "capability_scenario_report")
        for pid in sorted(capabilities)
    }

    spec_diff, exemption_changes = _git_sections(repo_root)

    return {
        "spec_diff": spec_diff,
        "changed_requirements": [i for i in changed_ids if i.startswith("R-")],
        "regenerated_components": component_ids,
        "verification_results": verification_results,
        "compliance_flags": {"license_scan": license_flags, "secret_scan": secret_flags},
        "provenance_hit_status": provenance_hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": exemption_changes,
        "residual_risk": residual_risk,
    }


def _dump(value) -> str:
    return json.dumps(value, sort_keys=True)


def _lines(items: list[str]) -> list[str]:
    return items or ["_(none)_"]


def render_markdown(packet: dict) -> str:
    out = ["# Review Packet", ""]

    out += ["## Spec Diff", "", "```diff", packet["spec_diff"].rstrip("\n"), "```", ""]

    out += ["## Changed Requirements", ""]
    out += _lines([f"- {rid}" for rid in packet["changed_requirements"]])
    out.append("")

    out += ["## Regenerated Components", ""]
    out += _lines([f"- {cid}" for cid in packet["regenerated_components"]])
    out.append("")

    out += ["## Verification Results", ""]
    out += _lines(
        [f"- {cid}: {_dump(vr)}" for cid, vr in packet["verification_results"].items()]
    )
    out.append("")

    out += ["## Capability Scenarios", ""]
    out += _lines(
        [f"- {pid}: {_dump(rep)}" for pid, rep in packet["capability_scenarios"].items()]
    )
    out.append("")

    flags = packet["compliance_flags"]
    out += ["## Compliance Flags", "", "### License Scan", ""]
    out += _lines(
        [f"- {e['component_id']}: {_dump(e['result'])}" for e in flags["license_scan"]]
    )
    out += ["", "### Secret Scan", ""]
    out += _lines(
        [f"- {e['component_id']}: {_dump(e['result'])}" for e in flags["secret_scan"]]
    )
    out.append("")

    out += ["## Provenance Hit Status", ""]
    out += _lines(
        [f"- {cid}: hit={_dump(hit)}" for cid, hit in packet["provenance_hit_status"].items()]
    )
    out.append("")

    ex = packet["exemption_changes"]
    out += [
        "## Exemption Changes",
        "",
        "**Sealed:** " + (", ".join(ex["sealed"]) or "(none)"),
        "",
        "**Pinned Overrides:** " + (", ".join(ex["pinned_overrides"]) or "(none)"),
        "",
    ]

    out += ["## Residual Risk", ""]
    out += _lines([f"- {r['component_id']}: {r['message']}" for r in packet["residual_risk"]])
    out.append("")

    return "\n".join(out)


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if list(argv[:2]) != ["review-packet", "build"]:
        return _usage_error("expected subcommand 'review-packet build'")

    changed: list[str] = []
    repo_root = "."
    fmt = "markdown"
    tokens = list(argv[2:])
    i = 0
    while i < len(tokens):
        token = tokens[i]
        name, sep, value = token.partition("=")
        if name not in ("--changed", "--repo-root", "--format"):
            return _usage_error(f"unknown argument: {token}")
        if not sep:
            if i + 1 >= len(tokens):
                return _usage_error(f"{name} requires a value")
            i += 1
            value = tokens[i]
        if name == "--changed":
            changed.append(value)
        elif name == "--repo-root":
            repo_root = value
        else:
            fmt = value
        i += 1

    if not changed:
        return _usage_error("--changed is required")
    if fmt not in ("markdown", "json"):
        return _usage_error(f"invalid --format: {fmt}")

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
