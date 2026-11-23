"""Review Packet Builder: assembles the human-readable review summary for a merge."""

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

_R_ID = re.compile(r"^R-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d+$")
_SEALED_PATH = re.compile(r"^specs/components/([^/]+)/component\.md$")
_OVERRIDES_PATH = re.compile(r"^gen/([^/]+)/\.overrides\.json$")


def _get(obj, key):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_provenance_tracker(repo_root: Path):
    module_dir = Path(repo_root) / "gen" / "provenance-tracker"
    if not module_dir.is_dir():
        module_dir = _tool_root() / "gen" / "provenance-tracker"
    path = module_dir / "provenance_tracker.py"
    name = "provenance_tracker"
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _git(repo_root: Path, *args: str):
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = str(Path(repo_root).resolve().parent)
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env=env,
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
    for candidate in ("origin/HEAD", "main", "master"):
        mb = _git(repo_root, "merge-base", "HEAD", candidate)
        if mb is not None:
            mb = mb.strip()
            if mb == head:
                return EMPTY_TREE
            return mb
    return EMPTY_TREE


def _is_sealed(text) -> bool:
    if text is None:
        return False
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("sealed:"):
            return line[len("sealed:"):].strip().lower() == "true"
    return False


def _exemption_changes(repo_root: Path, base):
    sealed = []
    pinned = []
    if base is None:
        return {"sealed": sealed, "pinned_overrides": pinned}
    out = _git(repo_root, "diff", "--name-status", "--no-renames", base, "HEAD")
    if out is None:
        return {"sealed": sealed, "pinned_overrides": pinned}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0], parts[-1]
        m = _SEALED_PATH.match(path)
        if m:
            log = _git(repo_root, "log", "--follow", "--format=%H", "--", path)
            revs = [r for r in (log or "").splitlines() if r.strip()]
            if revs:
                first = revs[-1].strip()
                at_first = _is_sealed(_git(repo_root, "show", f"{first}:{path}"))
                at_head = _is_sealed(_git(repo_root, "show", f"HEAD:{path}"))
                if at_head and not at_first:
                    sealed.append("comp-" + m.group(1))
            continue
        m = _OVERRIDES_PATH.match(path)
        if m and status == "A":
            pinned.append("comp-" + m.group(1))
    return {"sealed": sorted(set(sealed)), "pinned_overrides": sorted(set(pinned))}


def build_review_packet(changed_ids, repo_root):
    repo_root = Path(repo_root)
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids=list(changed_ids))
    components = _get(report, "components") or {}
    capabilities = _get(report, "capabilities") or {}

    base = _diff_base(repo_root)
    spec_diff = ""
    if base is not None:
        out = _git(repo_root, "diff", "--no-color", "--no-ext-diff", base, "HEAD", "--", "specs/")
        if out is not None:
            spec_diff = out

    regenerated = sorted(components.keys())
    verification_results = {}
    license_flags = []
    secret_flags = []
    hit_status = {}
    residual_risk = []
    for cid in regenerated:
        entry = components[cid]
        vr = _get(entry, "verification_report")
        verification_results[cid] = vr
        ls = _get(entry, "license_scan")
        if _get(ls, "blocked") is True:
            license_flags.append({"component_id": cid, "result": ls})
        ss = _get(entry, "secret_scan")
        if _get(ss, "flagged") is True:
            secret_flags.append({"component_id": cid, "result": ss})
        hit_status[cid] = _get(entry, "hit")
        score = _get(vr, "mutation_score")
        if (
            _get(vr, "overall") == "pass"
            and isinstance(score, (int, float))
            and score < 1.0
        ):
            residual_risk.append({
                "component_id": cid,
                "message": f"mutation_score {score} < 1.0 despite overall=pass",
            })

    capability_scenarios = {
        pid: _get(capabilities[pid], "capability_scenario_report")
        for pid in sorted(capabilities.keys())
    }

    return {
        "spec_diff": spec_diff,
        "changed_requirements": sorted({i for i in changed_ids if _R_ID.match(i)}),
        "regenerated_components": regenerated,
        "verification_results": verification_results,
        "compliance_flags": {"license_scan": license_flags, "secret_scan": secret_flags},
        "provenance_hit_status": hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": _exemption_changes(repo_root, base),
        "residual_risk": residual_risk,
    }


def _dump(value) -> str:
    return json.dumps(value, sort_keys=True)


def render_markdown(packet) -> str:
    none = "(none)"
    lines = ["# Review Packet", "", "## Spec Diff", ""]
    if packet["spec_diff"]:
        lines += ["```diff", packet["spec_diff"].rstrip("\n"), "```"]
    else:
        lines.append(none)

    lines += ["", "## Changed Requirements", ""]
    lines += [f"- {r}" for r in packet["changed_requirements"]] or [none]

    lines += ["", "## Regenerated Components", ""]
    lines += [f"- {c}" for c in packet["regenerated_components"]] or [none]

    lines += ["", "## Verification Results", ""]
    lines += [
        f"- {c}: {_dump(v)}" for c, v in packet["verification_results"].items()
    ] or [none]

    flags = packet["compliance_flags"]
    lines += ["", "## License and Secret Scan", "", "### License Scan", ""]
    lines += [
        f"- {e['component_id']}: {_dump(e['result'])}" for e in flags["license_scan"]
    ] or [none]
    lines += ["", "### Secret Scan", ""]
    lines += [
        f"- {e['component_id']}: {_dump(e['result'])}" for e in flags["secret_scan"]
    ] or [none]

    lines += ["", "## Provenance Hit Status", ""]
    lines += [
        f"- {c}: {_dump(h)} ({'hit' if h is True else 'miss'})"
        for c, h in packet["provenance_hit_status"].items()
    ] or [none]

    lines += ["", "## Capability Scenarios", ""]
    lines += [
        f"- {p}: {_dump(v)}" for p, v in packet["capability_scenarios"].items()
    ] or [none]

    ex = packet["exemption_changes"]
    lines += [
        "",
        "## Exemption Changes",
        "",
        f"**Sealed:** {', '.join(ex['sealed']) or none}",
        "",
        f"**Pinned Overrides:** {', '.join(ex['pinned_overrides']) or none}",
    ]

    lines += ["", "## Residual Risk", ""]
    lines += [
        f"- {r['component_id']}: {r['message']}" for r in packet["residual_risk"]
    ] or [none]

    return "\n".join(lines) + "\n"


def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv[:2] != ["review-packet", "build"]:
        return _usage_error("expected subcommand 'review-packet build'")
    changed = []
    repo_root = None
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
    if not changed:
        return _usage_error("--changed is required")
    if fmt not in ("markdown", "json"):
        return _usage_error(f"invalid --format: {fmt}")
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
