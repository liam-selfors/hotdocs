"""Review Packet Builder: assembles the human-readable review packet.

Formats already-computed results read entirely from provenance-tracker's
own ``check_readiness`` into one reviewable document. Never gates, never
includes generated code.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

USAGE = (
    "usage: hotdocs review-packet build --changed=<spec-id>... "
    "[--repo-root=<dir>] [--format=markdown|json]"
)

_R_ID = re.compile(r"R-[A-Z0-9]+(?:-[A-Z0-9]+)*")
_SEALED_PATH = re.compile(r"specs/components/([^/]+)/component\.md")
_OVERRIDE_PATH = re.compile(r"gen/([^/]+)/\.overrides\.json")

_SCREENSHOT_NOTE = (
    "Screenshots are local files under .hotdocs/ (not committed); "
    "attach them to the PR to show them there."
)


# ---------------------------------------------------------------------------
# Dependency loading (R-PACKET-013)
# ---------------------------------------------------------------------------

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


def _get(obj, key):
    """Dual dict-or-attribute access."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _plain(value):
    """Convert a dependency value into its plain JSON-equivalent form."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "__dict__"):
        return {k: _plain(v) for k, v in vars(value).items()}
    return value


# ---------------------------------------------------------------------------
# Git helpers (R-PACKET-001, R-PACKET-007, R-PACKET-009)
# ---------------------------------------------------------------------------

def _git(repo_root: Path, *args: str) -> str | None:
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = str(Path(repo_root).resolve().parent)
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            check=False,
            env=env,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace")


def _diff_base(repo_root: Path) -> str | None:
    head = _git(repo_root, "rev-parse", "HEAD")
    if head is None:
        return None
    head = head.strip()
    candidates = []
    origin = _git(
        repo_root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"
    )
    if origin:
        candidates.append(origin.strip())
    candidates.extend(["main", "master"])
    for candidate in candidates:
        merge_base = _git(repo_root, "merge-base", "HEAD", candidate)
        if merge_base is not None:
            merge_base = merge_base.strip()
            return EMPTY_TREE if merge_base == head else merge_base
    return EMPTY_TREE


def _frontmatter_sealed(text: str | None) -> bool:
    if text is None:
        return False
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        if key.strip() == "sealed":
            return value.strip().lower() == "true"
    return False


def _sealed_transition(repo_root: Path, path: str) -> bool:
    log = _git(repo_root, "log", "--follow", "--format=%H", "--", path)
    if log is None:
        return False
    revs = [line.strip() for line in log.splitlines() if line.strip()]
    if not revs:
        return False
    first = revs[-1]
    at_first = _frontmatter_sealed(_git(repo_root, "show", f"{first}:{path}"))
    at_head = _frontmatter_sealed(_git(repo_root, "show", f"HEAD:{path}"))
    return at_head and not at_first


def _exists_at(repo_root: Path, rev: str, path: str) -> bool:
    return _git(repo_root, "cat-file", "-e", f"{rev}:{path}") is not None


def _exemption_changes(repo_root: Path, base: str | None) -> dict:
    sealed: set[str] = set()
    overrides: set[str] = set()
    if base is not None:
        names = _git(repo_root, "diff", "--name-only", base, "HEAD") or ""
        for name in names.splitlines():
            name = name.strip()
            m = _SEALED_PATH.fullmatch(name)
            if m and _sealed_transition(repo_root, name):
                sealed.add(f"comp-{m.group(1)}")
            m = _OVERRIDE_PATH.fullmatch(name)
            if (
                m
                and _exists_at(repo_root, "HEAD", name)
                and not _exists_at(repo_root, base, name)
            ):
                overrides.add(f"comp-{m.group(1)}")
    return {"sealed": sorted(sealed), "pinned_overrides": sorted(overrides)}


def _spec_diff(repo_root: Path, base: str | None) -> str:
    if base is None:
        return ""
    return _git(repo_root, "diff", base, "HEAD", "--", "specs/") or ""


# ---------------------------------------------------------------------------
# Screenshots (R-PACKET-014)
# ---------------------------------------------------------------------------

def _screenshots(repo_root: Path, component_id: str) -> list[str]:
    slug = component_id.removeprefix("comp-")
    shot_dir = Path(repo_root) / ".hotdocs" / "screenshots" / slug
    return sorted(
        p.relative_to(repo_root).as_posix()
        for p in shot_dir.rglob("*.png")
        if p.is_file()
    )


# ---------------------------------------------------------------------------
# Library entry point
# ---------------------------------------------------------------------------

def build_review_packet(changed_ids: list[str], repo_root: Path) -> dict:
    repo_root = Path(repo_root)
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, list(changed_ids))

    components = _get(report, "components") or {}
    capabilities = _get(report, "capabilities") or {}

    regenerated = list(components)

    verification_results = {}
    provenance_hit_status = {}
    license_flags = []
    residual_risk = []
    for cid in regenerated:
        result = components[cid]
        vr = _plain(_get(result, "verification_report"))
        verification_results[cid] = vr
        provenance_hit_status[cid] = _get(result, "hit") is True
        license_scan = _get(result, "license_scan")
        if _get(license_scan, "blocked") is True:
            license_flags.append(
                {"component_id": cid, "result": _plain(license_scan)}
            )
        score = _get(vr, "mutation_score")
        if _get(vr, "overall") == "pass" and score is not None and score < 1.0:
            residual_risk.append(
                {
                    "component_id": cid,
                    "message": f"mutation_score {score} < 1.0 despite overall=pass",
                }
            )

    secret = _get(report, "secret_scan")
    secret_flags = []
    if _get(secret, "flagged") is True:
        secret_flags.append({"component_id": None, "result": _plain(secret)})

    capability_scenarios = {
        pid: _plain(_get(cap, "capability_scenario_report"))
        for pid, cap in capabilities.items()
    }

    base = _diff_base(repo_root)

    return {
        "spec_diff": _spec_diff(repo_root, base),
        "changed_requirements": [i for i in changed_ids if _R_ID.fullmatch(i)],
        "regenerated_components": regenerated,
        "verification_results": verification_results,
        "compliance_flags": {
            "license_scan": license_flags,
            "secret_scan": secret_flags,
        },
        "provenance_hit_status": provenance_hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": _exemption_changes(repo_root, base),
        "screenshots": {cid: _screenshots(repo_root, cid) for cid in regenerated},
        "residual_risk": residual_risk,
    }


# ---------------------------------------------------------------------------
# Markdown rendering (R-PACKET-012)
# ---------------------------------------------------------------------------

def _dump(value) -> str:
    return json.dumps(value, sort_keys=True)


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] or ["_None._"]


def render_markdown(packet: dict) -> str:
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
        [f"{cid}: {_dump(vr)}" for cid, vr in packet["verification_results"].items()]
    )
    lines.append("")

    lines += ["## Screenshots", ""]
    shot_lines = []
    for cid, paths in packet["screenshots"].items():
        prefix = f".hotdocs/screenshots/{cid.removeprefix('comp-')}/"
        for path in paths:
            shot_lines.append(f"- {cid}: ![{path[len(prefix):]}]({path})")
    lines += shot_lines or ["_No screenshots._"]
    lines += [_SCREENSHOT_NOTE, ""]

    flags = packet["compliance_flags"]
    lines += ["## License and Secret Scan", ""]
    for title, key in (("License Scan", "license_scan"), ("Secret Scan", "secret_scan")):
        lines += [f"### {title}", ""]
        entries = [
            f"- {entry['component_id'] or 'repository'}: {_dump(entry['result'])}"
            for entry in flags[key]
        ]
        lines += entries or ["_Clean._"]
        lines.append("")

    lines += ["## Provenance Hit Status", ""]
    lines += _bullets(
        [
            f"{cid}: hit={_dump(hit)}"
            for cid, hit in packet["provenance_hit_status"].items()
        ]
    )
    lines.append("")

    lines += ["## Capability Scenarios", ""]
    lines += _bullets(
        [
            f"{pid}: {_dump(rep)}"
            for pid, rep in packet["capability_scenarios"].items()
        ]
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
        [f"{r['component_id']}: {r['message']}" for r in packet["residual_risk"]]
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI (R-PACKET-012, cli-conventions)
# ---------------------------------------------------------------------------

def _usage(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv[:2] != ["review-packet", "build"]:
        return _usage("expected subcommand 'review-packet build'")

    changed: list[str] = []
    repo_root = "."
    fmt = "markdown"
    rest = argv[2:]
    i = 0
    while i < len(rest):
        token = rest[i]
        name, eq, value = token.partition("=")
        if name not in ("--changed", "--repo-root", "--format"):
            return _usage(f"unknown argument: {token}")
        if not eq:
            if i + 1 >= len(rest):
                return _usage(f"{name} requires a value")
            value = rest[i + 1]
            i += 1
        i += 1
        if name == "--changed":
            changed.append(value)
        elif name == "--repo-root":
            repo_root = value
        else:
            fmt = value

    if not changed:
        return _usage("--changed is required")
    if fmt not in ("markdown", "json"):
        return _usage(f"invalid --format: {fmt}")

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


if __name__ == "__main__":
    sys.exit(main())
