"""Review Packet Builder.

Assembles the human-readable summary a reviewer reads before merging: the
spec diff, changed requirements, regenerated components, verification
results, compliance flags, provenance-hit status, capability scenarios,
exemption changes, and residual risk -- never the generated code itself.

Every upstream result is read from provenance-tracker's own
``check_readiness`` (R-PACKET-011); nothing here computes or gates.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

_R_ID = re.compile(r"R-[A-Z0-9]+(?:-[A-Z0-9]+)*")
_COMPONENT_MD = re.compile(r"specs/components/([^/]+)/component\.md")
_OVERRIDES = re.compile(r"gen/([^/]+)/\.overrides\.json")

_DEFAULT_BRANCH_CANDIDATES = ("origin/HEAD", "main", "master")


# ---------------------------------------------------------------------------
# Dependency loading (R-PACKET-013)
# ---------------------------------------------------------------------------

def _tool_root():
    return next(d.parent for d in Path(__file__).resolve().parents if d.name == "gen")


def _load_provenance_tracker(repo_root):
    rel = Path("gen") / "provenance-tracker"
    base = Path(repo_root) / rel
    if not base.is_dir():
        base = _tool_root() / rel
    path = base / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


# ---------------------------------------------------------------------------
# Git helpers (R-PACKET-001, R-PACKET-007, R-PACKET-009)
# ---------------------------------------------------------------------------

def _git(repo_root, *args):
    root = Path(repo_root)
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = str(root.resolve().parent)
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _diff_base(repo_root):
    head = _git(repo_root, "rev-parse", "HEAD")
    if head is None:
        return None
    head = head.strip()
    for ref in _DEFAULT_BRANCH_CANDIDATES:
        merge_base = _git(repo_root, "merge-base", "HEAD", ref)
        if merge_base is not None:
            merge_base = merge_base.strip()
            return EMPTY_TREE if merge_base == head else merge_base
    return EMPTY_TREE


def _spec_diff(repo_root, base):
    if base is None:
        return ""
    out = _git(repo_root, "diff", "--no-color", "--no-ext-diff", base, "HEAD", "--", "specs/")
    return out or ""


def _is_sealed(text):
    lines = (text or "").splitlines()
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _sep, value = line.partition(":")
        if key.strip() == "sealed":
            return value.strip().lower() == "true"
    return False


def _exemption_changes(repo_root, base):
    sealed = set()
    pinned = set()
    if base is not None:
        out = _git(repo_root, "diff", "--name-status", "--no-renames", base, "HEAD") or ""
        for line in out.splitlines():
            status, _tab, path = line.partition("\t")
            component_match = _COMPONENT_MD.fullmatch(path)
            if component_match:
                if not _is_sealed(_git(repo_root, "show", f"HEAD:{path}")):
                    continue
                revs = (_git(repo_root, "log", "--follow", "--format=%H", "--", path) or "").split()
                first_text = _git(repo_root, "show", f"{revs[-1]}:{path}") if revs else None
                if not _is_sealed(first_text):
                    sealed.add("comp-" + component_match.group(1))
            override_match = _OVERRIDES.fullmatch(path)
            if override_match and status == "A":
                pinned.add("comp-" + override_match.group(1))
    return {"sealed": sorted(sealed), "pinned_overrides": sorted(pinned)}


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

def build_review_packet(changed_ids, repo_root):
    repo_root = Path(repo_root)
    tracker = _load_provenance_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids=list(changed_ids))

    components = _get(report, "components") or {}
    capabilities = _get(report, "capabilities") or {}
    component_ids = sorted(components)

    verification_results = {}
    license_flags = []
    secret_flags = []
    provenance_hit_status = {}
    residual_risk = []
    for cid in component_ids:
        entry = components[cid]
        verification = _get(entry, "verification_report")
        license_scan = _get(entry, "license_scan")
        secret_scan = _get(entry, "secret_scan")
        verification_results[cid] = verification
        provenance_hit_status[cid] = _get(entry, "hit")
        if _get(license_scan, "blocked"):
            license_flags.append({"component_id": cid, "result": license_scan})
        if _get(secret_scan, "flagged"):
            secret_flags.append({"component_id": cid, "result": secret_scan})
        score = _get(verification, "mutation_score")
        if score is not None and score < 1.0 and _get(verification, "overall") == "pass":
            residual_risk.append({
                "component_id": cid,
                "message": f"mutation_score {score} < 1.0 despite overall=pass",
            })

    capability_scenarios = {
        pid: _get(capabilities[pid], "capability_scenario_report")
        for pid in sorted(capabilities)
    }

    base = _diff_base(repo_root)
    return {
        "spec_diff": _spec_diff(repo_root, base),
        "changed_requirements": [sid for sid in changed_ids if _R_ID.fullmatch(sid)],
        "regenerated_components": component_ids,
        "verification_results": verification_results,
        "compliance_flags": {"license_scan": license_flags, "secret_scan": secret_flags},
        "provenance_hit_status": provenance_hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": _exemption_changes(repo_root, base),
        "residual_risk": residual_risk,
    }


# ---------------------------------------------------------------------------
# Markdown rendering (R-PACKET-012)
# ---------------------------------------------------------------------------

def _dump(value):
    return json.dumps(value, sort_keys=True)


def _section(title, lines, level="##"):
    return [f"{level} {title}", "", *(lines or ["(none)"]), ""]


def _flag_lines(entries):
    return [f"- {e['component_id']}: {_dump(e['result'])}" for e in entries]


def _label(items):
    return ", ".join(items) or "(none)"


def render_markdown(packet):
    flags = packet["compliance_flags"]
    exemptions = packet["exemption_changes"]
    out = ["# Review Packet", ""]
    out += ["## Spec Diff", "", "```diff", packet["spec_diff"].rstrip("\n"), "```", ""]
    out += _section("Changed Requirements", [f"- {r}" for r in packet["changed_requirements"]])
    out += _section("Regenerated Components", [f"- {c}" for c in packet["regenerated_components"]])
    out += _section(
        "Verification Results",
        [f"- {c}: {_dump(v)}" for c, v in packet["verification_results"].items()],
    )
    out += ["## Compliance Flags", "", "License- and secret-scan results, listed even when clean.", ""]
    out += _section("License Scan", _flag_lines(flags["license_scan"]), level="###")
    out += _section("Secret Scan", _flag_lines(flags["secret_scan"]), level="###")
    out += _section(
        "Provenance Hit Status",
        [f"- {c}: hit={_dump(v)}" for c, v in packet["provenance_hit_status"].items()],
    )
    out += _section(
        "Capability Scenarios",
        [f"- {p}: {_dump(v)}" for p, v in packet["capability_scenarios"].items()],
    )
    out += [
        "## Exemption Changes",
        "",
        f"**Sealed:** {_label(exemptions['sealed'])}",
        "",
        f"**Pinned Overrides:** {_label(exemptions['pinned_overrides'])}",
        "",
    ]
    out += _section(
        "Residual Risk",
        [f"- {e['component_id']}: {e['message']}" for e in packet["residual_risk"]],
    )
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI (R-PACKET-012)
# ---------------------------------------------------------------------------

_USAGE = "usage: hotdocs review-packet build --changed=<spec-id>... [--repo-root=<dir>] [--format=markdown|json]"


def _usage(message):
    print(f"{message}\n{_USAGE}", file=sys.stderr)
    return 2


def main(argv):
    argv = list(argv)
    if argv[:2] != ["review-packet", "build"]:
        return _usage("expected subcommand: review-packet build")
    changed = []
    repo_root = "."
    fmt = "markdown"
    args = argv[2:]
    i = 0
    while i < len(args):
        arg = args[i]
        name, eq, value = arg.partition("=")
        if name not in ("--changed", "--repo-root", "--format"):
            return _usage(f"unknown argument: {arg}")
        if not eq:
            i += 1
            if i >= len(args):
                return _usage(f"{name} requires a value")
            value = args[i]
        if name == "--changed":
            changed.append(value)
        elif name == "--repo-root":
            repo_root = value
        else:
            fmt = value
        i += 1
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
        sys.stdout.write(render_markdown(packet))
    return 0
