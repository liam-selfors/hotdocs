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

_COMPONENT_MD = re.compile(r"^specs/components/([^/]+)/component\.md$")
_OVERRIDES = re.compile(r"^gen/([^/]+)/\.overrides\.json$")
_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
_SEALED_TRUE = re.compile(r"^sealed:\s*true\s*$", re.M | re.I)


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _load_provenance_tracker(repo_root: Path):
    dep_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not dep_dir.is_dir():
        tool_root = next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")
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
            ["git", *args], cwd=str(repo_root), capture_output=True, text=True
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _diff_base(repo_root: Path, head: str) -> str:
    refs = []
    origin_head = _git(repo_root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if origin_head:
        refs.append(origin_head.strip())
    refs.extend(["main", "master"])
    for ref in refs:
        out = _git(repo_root, "merge-base", "HEAD", ref)
        if out:
            merge_base = out.strip()
            return EMPTY_TREE if merge_base == head else merge_base
    return EMPTY_TREE


def _sealed_at(repo_root: Path, rev: str, path: str) -> bool:
    text = _git(repo_root, "show", f"{rev}:{path}") or ""
    m = _FRONTMATTER.match(text)
    if not m:
        return False
    return _SEALED_TRUE.search(m.group(1)) is not None


def _git_sections(repo_root: Path):
    head_out = _git(repo_root, "rev-parse", "HEAD")
    if not head_out:
        return "", {"sealed": [], "pinned_overrides": []}
    head = head_out.strip()
    base = _diff_base(repo_root, head)
    spec_diff = _git(repo_root, "diff", "--no-renames", base, "HEAD", "--", "specs/") or ""
    name_status = _git(repo_root, "diff", "--no-renames", "--name-status", base, "HEAD") or ""

    sealed = set()
    overrides = set()
    for line in name_status.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0], parts[-1]
        m = _COMPONENT_MD.match(path)
        if m:
            log = _git(repo_root, "log", "--follow", "--format=%H", "--", path)
            first = (log or "HEAD").split()[-1] if (log or "").split() else "HEAD"
            if _sealed_at(repo_root, "HEAD", path) and not _sealed_at(repo_root, first, path):
                sealed.add("comp-" + m.group(1))
            continue
        m = _OVERRIDES.match(path)
        if m and status == "A":
            overrides.add("comp-" + m.group(1))
    return spec_diff, {"sealed": sorted(sealed), "pinned_overrides": sorted(overrides)}


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
                and not isinstance(score, bool)
                and score < 1.0
            ):
                residual_risk.append(
                    {
                        "component_id": cid,
                        "message": f"mutation_score {score} < 1.0 despite overall=pass",
                    }
                )

    secret_flags = []
    repo_scan = _get(report, "secret_scan")
    if repo_scan is not None and _get(repo_scan, "flagged") is True:
        secret_flags.append({"component_id": None, "result": repo_scan})

    capability_scenarios = {
        pid: _get(capabilities[pid], "capability_scenario_report")
        for pid in sorted(capabilities.keys())
    }

    spec_diff, exemption_changes = _git_sections(repo_root)

    return {
        "spec_diff": spec_diff,
        "changed_requirements": [i for i in changed_ids if i.startswith("R-")],
        "regenerated_components": regenerated,
        "verification_results": verification_results,
        "compliance_flags": {"license_scan": license_flags, "secret_scan": secret_flags},
        "provenance_hit_status": provenance_hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": exemption_changes,
        "residual_risk": residual_risk,
    }


def _dump(value) -> str:
    return json.dumps(value, sort_keys=True)


def _items(lines: list[str]) -> list[str]:
    return lines if lines else ["(none)"]


def render_markdown(packet: dict) -> str:
    out = ["# Review Packet", ""]

    out += ["## Spec Diff", "", "```diff", packet["spec_diff"].rstrip("\n"), "```", ""]

    out += ["## Changed Requirements", ""]
    out += _items([f"- {rid}" for rid in packet["changed_requirements"]])
    out.append("")

    out += ["## Regenerated Components", ""]
    out += _items([f"- {cid}" for cid in packet["regenerated_components"]])
    out.append("")

    out += ["## Verification Results", ""]
    out += _items(
        [f"- {cid}: {_dump(vr)}" for cid, vr in packet["verification_results"].items()]
    )
    out.append("")

    flags = packet["compliance_flags"]
    out += ["## Compliance Flags", "", "### License Scan", ""]
    out += _items(
        [f"- {e['component_id']}: {_dump(e['result'])}" for e in flags["license_scan"]]
    )
    out += ["", "### Secret Scan", ""]
    out += _items([f"- repository: {_dump(e['result'])}" for e in flags["secret_scan"]])
    out.append("")

    out += ["## Provenance Hit Status", ""]
    out += _items(
        [
            f"- {cid}: hit={_dump(hit)}"
            for cid, hit in packet["provenance_hit_status"].items()
        ]
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
    out += _items([f"- {r['component_id']}: {r['message']}" for r in packet["residual_risk"]])
    out.append("")

    out += ["## Capability Scenarios", ""]
    out += _items(
        [f"- {pid}: {_dump(rep)}" for pid, rep in packet["capability_scenarios"].items()]
    )
    out.append("")

    return "\n".join(out)


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
    tokens = argv[2:]
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        name, eq, value = tok.partition("=")
        if name not in ("--changed", "--repo-root", "--format"):
            return _usage_error(f"unknown argument: {tok}")
        if not eq:
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

    if fmt not in ("markdown", "json"):
        return _usage_error(f"invalid --format: {fmt}")
    if not changed:
        return _usage_error("missing required --changed")

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
