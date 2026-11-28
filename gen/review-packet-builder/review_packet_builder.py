"""Review Packet Builder.

Assembles the human-readable summary a reviewer reads before merging: the
spec diff, changed requirements, regenerated components, verification
results, compliance flags, provenance-hit status, capability scenarios,
exemption changes, screenshots and residual risk -- never generated code.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

USAGE = (
    "usage: hotdocs review-packet build --changed=<spec-id>... "
    "[--repo-root=<dir>] [--format=markdown|json]"
)

SCREENSHOT_NOTE = (
    "Screenshots are local files under .hotdocs/ (not committed); "
    "attach them to the PR to show them there."
)


# ---------------------------------------------------------------------------
# Dependency loading (R-PACKET-013)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _plain(value):
    """Turn a dependency's report value into plain JSON values (D390)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _plain(getattr(value, f.name))
            for f in dataclasses.fields(value)
        }
    if isinstance(value, Path):
        return value.as_posix()
    return {str(k): _plain(v) for k, v in vars(value).items()}


def _items(mapping):
    """Items of a dependency map read as either a dict or an object."""
    if isinstance(mapping, dict):
        return list(mapping.items())
    if mapping is None:
        return []
    return list(vars(mapping).items())


# ---------------------------------------------------------------------------
# Git (R-PACKET-001, R-PACKET-007, R-PACKET-009)
# ---------------------------------------------------------------------------


def _git(repo_root: Path, *args: str):
    env = dict(os.environ)
    root = Path(repo_root).resolve()
    env["GIT_CEILING_DIRECTORIES"] = str(root.parent)
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "-c", "core.quotepath=off", *args],
            capture_output=True,
            env=env,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="replace")


def _default_branch(repo_root: Path):
    out = _git(repo_root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if out is not None and out.strip():
        return out.strip()
    for candidate in ("main", "master"):
        if _git(repo_root, "rev-parse", "--verify", "--quiet", candidate) is not None:
            return candidate
    return None


def _diff_base(repo_root: Path):
    head = _git(repo_root, "rev-parse", "HEAD")
    if head is None:
        return None
    head = head.strip()
    branch = _default_branch(repo_root)
    base = None
    if branch is not None:
        out = _git(repo_root, "merge-base", "HEAD", branch)
        if out is not None:
            base = out.strip()
    if base is None or base == head:
        return EMPTY_TREE
    return base


def _spec_diff(repo_root: Path, base):
    if base is None:
        return ""
    out = _git(
        repo_root, "diff", "--no-color", "--no-ext-diff", base, "HEAD", "--", "specs/"
    )
    return out if out is not None else ""


def _frontmatter_sealed(text) -> bool:
    if text is None:
        return False
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, val = line.partition(":")
        if sep and key.strip() == "sealed":
            return val.strip().strip("'\"").lower() == "true"
    return False


def _exemption_changes(repo_root: Path, base):
    sealed: set[str] = set()
    overrides: set[str] = set()
    if base is None:
        return {"sealed": [], "pinned_overrides": []}
    out = _git(repo_root, "diff", "--no-renames", "--name-status", base, "HEAD")
    for line in (out or "").splitlines():
        status, _, path = line.partition("\t")
        parts = path.split("/")
        if (
            len(parts) == 4
            and parts[0] == "specs"
            and parts[1] == "components"
            and parts[3] == "component.md"
            and status != "D"
        ):
            log = _git(repo_root, "log", "--follow", "--format=%H", "HEAD", "--", path)
            revs = (log or "").split()
            if not revs:
                continue
            first = revs[-1]
            before = _frontmatter_sealed(_git(repo_root, "show", f"{first}:{path}"))
            now = _frontmatter_sealed(_git(repo_root, "show", f"HEAD:{path}"))
            if now and not before:
                sealed.add(f"comp-{parts[2]}")
        elif (
            len(parts) == 3
            and parts[0] == "gen"
            and parts[2] == ".overrides.json"
            and status == "A"
        ):
            overrides.add(f"comp-{parts[1]}")
    return {"sealed": sorted(sealed), "pinned_overrides": sorted(overrides)}


# ---------------------------------------------------------------------------
# Packet
# ---------------------------------------------------------------------------


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _screenshots(repo_root: Path, component_ids):
    root = Path(repo_root)
    result = {}
    for cid in component_ids:
        directory = root / ".hotdocs" / "screenshots" / _slug(cid)
        files = []
        if directory.is_dir():
            files = sorted(
                p.relative_to(root).as_posix()
                for p in directory.rglob("*.png")
                if p.is_file()
            )
        result[cid] = files
    return result


def _residual_risk(verification_results):
    risks = []
    for cid, vr in verification_results.items():
        if not isinstance(vr, dict):
            continue
        score = vr.get("mutation_score")
        overall = vr.get("overall")
        if overall == "pass" and isinstance(score, (int, float)) and score < 1.0:
            risks.append(
                {
                    "component_id": cid,
                    "message": f"mutation_score {score} < 1.0 despite overall={overall}",
                }
            )
    return risks


def build_review_packet(changed_ids: list[str], repo_root: Path) -> dict:
    repo_root = Path(repo_root)
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, list(changed_ids))

    components = _items(_get(report, "components"))
    capabilities = _items(_get(report, "capabilities"))

    regenerated = [cid for cid, _ in components]

    verification_results = {
        cid: _plain(_get(entry, "verification_report")) for cid, entry in components
    }

    license_flags = []
    for cid, entry in components:
        scan = _get(entry, "license_scan")
        if _get(scan, "blocked") is True:
            license_flags.append({"component_id": cid, "result": _plain(scan)})

    secret = _get(report, "secret_scan")
    secret_flags = []
    if _get(secret, "flagged") is True:
        secret_flags.append({"component_id": None, "result": _plain(secret)})

    base = _diff_base(repo_root)

    return {
        "spec_diff": _spec_diff(repo_root, base),
        "changed_requirements": [i for i in changed_ids if i.startswith("R-")],
        "regenerated_components": regenerated,
        "verification_results": verification_results,
        "compliance_flags": {"license_scan": license_flags, "secret_scan": secret_flags},
        "provenance_hit_status": {
            cid: _get(entry, "hit") is True for cid, entry in components
        },
        "capability_scenarios": {
            pid: _plain(_get(cap, "capability_scenario_report"))
            for pid, cap in capabilities
        },
        "exemption_changes": _exemption_changes(repo_root, base),
        "screenshots": _screenshots(repo_root, regenerated),
        "residual_risk": _residual_risk(verification_results),
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _dump(value) -> str:
    return json.dumps(value, sort_keys=True)


def _bullets(lines):
    return lines if lines else ["_None._"]


def render_markdown(packet: dict) -> str:
    out = ["# Review Packet", ""]

    out += ["## Spec Diff", ""]
    if packet["spec_diff"]:
        out += ["```diff", packet["spec_diff"].rstrip("\n"), "```"]
    else:
        out += ["_No spec changes._"]
    out.append("")

    out += ["## Changed Requirements", ""]
    out += _bullets([f"- {rid}" for rid in packet["changed_requirements"]])
    out.append("")

    out += ["## Regenerated Components", ""]
    out += _bullets([f"- {cid}" for cid in packet["regenerated_components"]])
    out.append("")

    out += ["## Verification Results", ""]
    out += _bullets(
        [f"- {cid}: {_dump(vr)}" for cid, vr in packet["verification_results"].items()]
    )
    out.append("")

    out += ["## Screenshots", ""]
    shot_lines = []
    for cid, paths in packet["screenshots"].items():
        prefix = f".hotdocs/screenshots/{_slug(cid)}/"
        for path in paths:
            shot_lines.append(f"- {cid}: ![{path[len(prefix):]}]({path})")
    out += shot_lines if shot_lines else ["_No screenshots._"]
    out += [SCREENSHOT_NOTE, ""]

    out += ["## Capability Scenarios", ""]
    out += _bullets(
        [f"- {pid}: {_dump(rep)}" for pid, rep in packet["capability_scenarios"].items()]
    )
    out.append("")

    flags = packet["compliance_flags"]
    out += ["## Compliance Flags", "", "### License Scan", ""]
    out += [
        f"- {e['component_id']}: {_dump(e['result'])}" for e in flags["license_scan"]
    ] or ["_Clean — no components blocked._"]
    out += ["", "### Secret Scan", ""]
    out += [
        f"- {e['component_id'] or 'repository'}: {_dump(e['result'])}"
        for e in flags["secret_scan"]
    ] or ["_Clean — nothing flagged._"]
    out.append("")

    out += ["## Provenance Hit Status", ""]
    out += _bullets(
        [
            f"- {cid}: hit={'true' if hit else 'false'}"
            for cid, hit in packet["provenance_hit_status"].items()
        ]
    )
    out.append("")

    ex = packet["exemption_changes"]
    out += ["## Exemption Changes", ""]
    out.append("**Sealed:** " + (", ".join(ex["sealed"]) or "(none)"))
    out.append("")
    out.append("**Pinned Overrides:** " + (", ".join(ex["pinned_overrides"]) or "(none)"))
    out.append("")

    out += ["## Residual Risk", ""]
    out += _bullets(
        [f"- {r['component_id']}: {r['message']}" for r in packet["residual_risk"]]
    )
    out.append("")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI (R-PACKET-012)
# ---------------------------------------------------------------------------


class _UsageError(Exception):
    pass


def _parse(argv):
    if argv[:2] != ["review-packet", "build"]:
        raise _UsageError("expected subcommand 'review-packet build'")
    changed: list[str] = []
    repo_root = None
    fmt = "markdown"
    rest = argv[2:]
    i = 0
    while i < len(rest):
        token = rest[i]
        name, eq, value = token.partition("=")
        if name not in ("--changed", "--repo-root", "--format"):
            raise _UsageError(f"unknown argument {token}")
        if not eq:
            if i + 1 >= len(rest):
                raise _UsageError(f"{name} requires a value")
            i += 1
            value = rest[i]
        if name == "--changed":
            changed.append(value)
        elif name == "--repo-root":
            repo_root = value
        else:
            fmt = value
        i += 1
    if not changed:
        raise _UsageError("missing required --changed")
    if fmt not in ("markdown", "json"):
        raise _UsageError(f"invalid --format {fmt}")
    return changed, repo_root, fmt


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        changed, repo_root, fmt = _parse(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    try:
        packet = build_review_packet(changed, root)
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
