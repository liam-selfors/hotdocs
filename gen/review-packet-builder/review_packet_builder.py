"""Review Packet Builder.

Assembles the human-readable review packet a reviewer reads before merging:
the spec diff, changed requirements, regenerated components, verification
results, compliance flags, provenance-hit status, exemption changes, residual
risk, and capability-scenario results.  Every upstream result is read from
``provenance-tracker``'s own ``check_readiness`` (R-PACKET-011); the generated
code diff is deliberately never included (R-PACKET-010).
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
FORMATS = ("markdown", "json")

_COMPONENT_MD_RE = re.compile(r"specs/components/([^/]+)/component\.md")
_OVERRIDES_RE = re.compile(r"gen/([^/]+)/\.overrides\.json")
_FRONTMATTER_RE = re.compile(r"---[ \t]*\r?\n(.*?)\r?\n---", re.S)
_SEALED_TRUE_RE = re.compile(r"^sealed[ \t]*:[ \t]*true\b", re.M)


def _get(obj, key, default=None):
    """Dual dict-or-attribute access for any value read from a dependency."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# --------------------------------------------------------------------------
# provenance-tracker loading (R-PACKET-013)
# --------------------------------------------------------------------------

def _tool_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_provenance_tracker(repo_root: Path):
    dep_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / "provenance-tracker"
    path = dep_dir / "provenance_tracker.py"
    name = "provenance_tracker"
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# git helpers (R-PACKET-001, R-PACKET-007, R-PACKET-009)
# --------------------------------------------------------------------------

def _git(repo_root: Path, *args: str):
    """Run git in ``repo_root``; return stdout, or ``None`` on any failure."""
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


def _diff_base(repo_root: Path) -> str:
    head = (_git(repo_root, "rev-parse", "HEAD") or "").strip()
    for ref in DEFAULT_BRANCH_CANDIDATES:
        merge_base = _git(repo_root, "merge-base", "HEAD", ref)
        if merge_base is not None:
            merge_base = merge_base.strip()
            return EMPTY_TREE if merge_base == head else merge_base
    return EMPTY_TREE


def _spec_diff(repo_root: Path, base: str) -> str:
    return _git(repo_root, "diff", "--no-color", "--no-ext-diff", base, "HEAD", "--", "specs/") or ""


def _is_sealed(text) -> bool:
    if text is None:
        return False
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return False
    return _SEALED_TRUE_RE.search(match.group(1)) is not None


def _exemption_changes(repo_root: Path, base: str) -> dict:
    names = _git(repo_root, "diff", "--name-only", "--no-renames", base, "HEAD") or ""
    sealed = set()
    overrides = set()
    for path in names.splitlines():
        comp_match = _COMPONENT_MD_RE.fullmatch(path)
        if comp_match:
            history = (_git(repo_root, "log", "--follow", "--format=%H", "--", path) or "").split()
            if history:
                first = history[-1]
                was_sealed = _is_sealed(_git(repo_root, "show", f"{first}:{path}"))
                now_sealed = _is_sealed(_git(repo_root, "show", f"HEAD:{path}"))
                if now_sealed and not was_sealed:
                    sealed.add("comp-" + comp_match.group(1))
            continue
        ov_match = _OVERRIDES_RE.fullmatch(path)
        if ov_match:
            at_head = _git(repo_root, "cat-file", "-e", f"HEAD:{path}") is not None
            at_base = _git(repo_root, "cat-file", "-e", f"{base}:{path}") is not None
            if at_head and not at_base:
                overrides.add("comp-" + ov_match.group(1))
    return {"sealed": sorted(sealed), "pinned_overrides": sorted(overrides)}


# --------------------------------------------------------------------------
# Library
# --------------------------------------------------------------------------

def build_review_packet(changed_ids, repo_root):
    repo_root = Path(repo_root)
    changed_ids = list(changed_ids)

    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids=changed_ids)

    components = _get(report, "components", {})
    capabilities = _get(report, "capabilities", {})

    regenerated = sorted(components.keys())

    verification_results = {}
    license_flags = []
    secret_flags = []
    provenance_hit_status = {}
    residual_risk = []
    for cid in regenerated:
        comp = components[cid]
        vreport = _get(comp, "verification_report")
        verification_results[cid] = vreport

        license_scan = _get(comp, "license_scan")
        if _get(license_scan, "blocked") is True:
            license_flags.append({"component_id": cid, "result": license_scan})
        secret_scan = _get(comp, "secret_scan")
        if _get(secret_scan, "flagged") is True:
            secret_flags.append({"component_id": cid, "result": secret_scan})

        provenance_hit_status[cid] = _get(comp, "hit")

        score = _get(vreport, "mutation_score")
        if _get(vreport, "overall") == "pass" and score is not None and score < 1.0:
            residual_risk.append({
                "component_id": cid,
                "message": f"mutation_score {score} < 1.0 despite overall=pass",
            })

    capability_scenarios = {
        pid: _get(capabilities[pid], "capability_scenario_report")
        for pid in sorted(capabilities.keys())
    }

    changed_requirements = sorted({cid for cid in changed_ids if cid.startswith("R-")})

    base = _diff_base(repo_root)

    return {
        "spec_diff": _spec_diff(repo_root, base),
        "changed_requirements": changed_requirements,
        "regenerated_components": regenerated,
        "verification_results": verification_results,
        "compliance_flags": {"license_scan": license_flags, "secret_scan": secret_flags},
        "provenance_hit_status": provenance_hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": _exemption_changes(repo_root, base),
        "residual_risk": residual_risk,
    }


# --------------------------------------------------------------------------
# Markdown rendering
# --------------------------------------------------------------------------

def _dump(value) -> str:
    return json.dumps(value, sort_keys=True)


def _bullets(lines):
    return lines or ["(none)"]


def render_markdown(packet) -> str:
    out = ["# Review Packet", ""]

    out += ["## Spec Diff", "", "```diff", packet["spec_diff"].rstrip("\n"), "```", ""]

    out += ["## Changed Requirements", ""]
    out += _bullets([f"- {rid}" for rid in packet["changed_requirements"]])
    out.append("")

    out += ["## Regenerated Components", ""]
    out += _bullets([f"- {cid}" for cid in packet["regenerated_components"]])
    out.append("")

    out += ["## Verification Results", ""]
    out += _bullets([
        f"- {cid}: {_dump(rep)}" for cid, rep in packet["verification_results"].items()
    ])
    out.append("")

    flags = packet["compliance_flags"]
    out += ["## License and Secret Scan", "",
            "License- and secret-scan results, shown even when clean.", ""]
    out += ["### License Scan", ""]
    out += _bullets([
        f"- {e['component_id']}: {_dump(e['result'])}" for e in flags["license_scan"]
    ])
    out.append("")
    out += ["### Secret Scan", ""]
    out += _bullets([
        f"- {e['component_id']}: {_dump(e['result'])}" for e in flags["secret_scan"]
    ])
    out.append("")

    out += ["## Provenance Hit Status", ""]
    out += _bullets([
        f"- {cid}: {_dump(hit)}" for cid, hit in packet["provenance_hit_status"].items()
    ])
    out.append("")

    exemptions = packet["exemption_changes"]
    out += ["## Exemption Changes", ""]
    out.append("**Sealed:** " + (", ".join(exemptions["sealed"]) or "(none)"))
    out.append("")
    out.append("**Pinned Overrides:** " + (", ".join(exemptions["pinned_overrides"]) or "(none)"))
    out.append("")

    out += ["## Residual Risk", ""]
    out += _bullets([
        f"- {e['component_id']}: {e['message']}" for e in packet["residual_risk"]
    ])
    out.append("")

    out += ["## Capability Scenarios", ""]
    out += _bullets([
        f"- {pid}: {_dump(rep)}" for pid, rep in packet["capability_scenarios"].items()
    ])
    out.append("")

    return "\n".join(out)


# --------------------------------------------------------------------------
# CLI (R-PACKET-012)
# --------------------------------------------------------------------------

class _UsageError(Exception):
    pass


def _parse(argv):
    if argv[:2] != ["review-packet", "build"]:
        raise _UsageError("expected subcommand 'review-packet build'")
    changed = []
    repo_root = "."
    fmt = "markdown"
    tokens = argv[2:]
    i = 0
    while i < len(tokens):
        token = tokens[i]
        name, sep, value = token.partition("=")
        if name not in ("--changed", "--repo-root", "--format"):
            raise _UsageError(f"unknown argument: {token}")
        if not sep:
            i += 1
            if i >= len(tokens):
                raise _UsageError(f"{name} requires a value")
            value = tokens[i]
        if name == "--changed":
            changed.append(value)
        elif name == "--repo-root":
            repo_root = value
        else:
            fmt = value
        i += 1
    if not changed:
        raise _UsageError("--changed is required")
    if fmt not in FORMATS:
        raise _UsageError(f"invalid --format: {fmt}")
    return changed, repo_root, fmt


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        changed, repo_root, fmt = _parse(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    try:
        packet = build_review_packet(changed, Path(repo_root))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if fmt == "json":
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(render_markdown(packet))
    return 0
