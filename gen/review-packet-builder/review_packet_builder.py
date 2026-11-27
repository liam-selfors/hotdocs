"""Review Packet Builder: assembles the human-readable summary a reviewer reads before merging."""

from __future__ import annotations

import dataclasses
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

_SEALED_PATH_RE = re.compile(r"^specs/components/([^/]+)/component\.md$")
_OVERRIDE_PATH_RE = re.compile(r"^gen/([^/]+)/\.overrides\.json$")
_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
_SEALED_TRUE_RE = re.compile(r"^sealed:\s*true\s*(#.*)?$", re.M | re.I)


def _get(obj, key):
    """Dual dict-or-attribute access."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _json_default(obj):
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return vars(obj)


def _dump(value):
    return json.dumps(value, sort_keys=True, default=_json_default)


def _load_tracker(repo_root: Path):
    rel = Path("gen") / "provenance-tracker"
    directory = Path(repo_root) / rel
    if not directory.is_dir():
        here = Path(__file__).resolve()
        gen_dir = next(p for p in here.parents if p.name == "gen")
        directory = gen_dir.parent / rel
    path = directory / "provenance_tracker.py"
    spec = importlib.util.spec_from_file_location("provenance_tracker", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["provenance_tracker"] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- git


def _git(repo_root: Path, *args):
    """Run git in repo_root; return stdout, or None on any failure."""
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = str(Path(repo_root).resolve().parent)
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=off", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except OSError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def _default_branch(repo_root: Path):
    ref = _git(repo_root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if ref:
        return ref.strip()
    for name in ("main", "master"):
        if _git(repo_root, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}") is not None:
            return name
    return None


def _diff_base(repo_root: Path):
    head = _git(repo_root, "rev-parse", "HEAD")
    if head is None:
        return None
    default = _default_branch(repo_root)
    merge_base = _git(repo_root, "merge-base", "HEAD", default) if default else None
    if merge_base is None or merge_base.strip() == head.strip():
        return EMPTY_TREE
    return merge_base.strip()


def _show(repo_root: Path, rev: str, path: str):
    return _git(repo_root, "show", f"{rev}:{path}")


def _is_sealed(text) -> bool:
    match = _FRONTMATTER_RE.match(text or "")
    frontmatter = match.group(1) if match else ""
    return _SEALED_TRUE_RE.search(frontmatter) is not None


def _spec_diff(repo_root: Path, base) -> str:
    if base is None:
        return ""
    return _git(repo_root, "diff", "--no-color", base, "HEAD", "--", "specs/") or ""


def _exemption_changes(repo_root: Path, base) -> dict:
    sealed: set[str] = set()
    overrides: set[str] = set()
    if base is None:
        return {"sealed": [], "pinned_overrides": []}
    names = _git(repo_root, "diff", "--name-only", base, "HEAD") or ""
    for path in names.splitlines():
        sealed_match = _SEALED_PATH_RE.match(path)
        if sealed_match:
            log = _git(repo_root, "log", "--follow", "--format=%H", "--", path) or ""
            revs = log.split()
            if (
                revs
                and not _is_sealed(_show(repo_root, revs[-1], path))
                and _is_sealed(_show(repo_root, "HEAD", path))
            ):
                sealed.add("comp-" + sealed_match.group(1))
        override_match = _OVERRIDE_PATH_RE.match(path)
        if override_match:
            if _show(repo_root, "HEAD", path) is not None and _show(repo_root, base, path) is None:
                overrides.add("comp-" + override_match.group(1))
    return {"sealed": sorted(sealed), "pinned_overrides": sorted(overrides)}


# --------------------------------------------------------------------- library


def build_review_packet(changed_ids: list[str], repo_root: Path) -> dict:
    repo_root = Path(repo_root)
    tracker = _load_tracker(repo_root)
    report = tracker.check_readiness(repo_root, changed_ids=list(changed_ids))

    components = _get(report, "components")
    capabilities = _get(report, "capabilities")
    component_ids = sorted(components.keys())

    verification_results = {}
    provenance_hit_status = {}
    license_flags = []
    residual_risk = []
    for cid in component_ids:
        result = components[cid]
        vreport = _get(result, "verification_report")
        verification_results[cid] = vreport
        provenance_hit_status[cid] = bool(_get(result, "hit"))
        license_scan = _get(result, "license_scan")
        if _get(license_scan, "blocked"):
            license_flags.append({"component_id": cid, "result": license_scan})
        score = _get(vreport, "mutation_score")
        if _get(vreport, "overall") == "pass" and score is not None and score < 1.0:
            residual_risk.append(
                {
                    "component_id": cid,
                    "message": f"mutation_score {score} < 1.0 despite overall=pass",
                }
            )

    repo_scan = _get(report, "secret_scan")
    secret_flags = []
    if _get(repo_scan, "flagged"):
        secret_flags.append({"component_id": None, "result": repo_scan})

    capability_scenarios = {
        pid: _get(capabilities[pid], "capability_scenario_report")
        for pid in sorted(capabilities.keys())
    }

    base = _diff_base(repo_root)

    return {
        "spec_diff": _spec_diff(repo_root, base),
        "changed_requirements": [i for i in changed_ids if i.startswith("R-")],
        "regenerated_components": component_ids,
        "verification_results": verification_results,
        "compliance_flags": {"license_scan": license_flags, "secret_scan": secret_flags},
        "provenance_hit_status": provenance_hit_status,
        "capability_scenarios": capability_scenarios,
        "exemption_changes": _exemption_changes(repo_root, base),
        "residual_risk": residual_risk,
    }


# -------------------------------------------------------------------- markdown


def _bullets(items) -> list[str]:
    return [f"- {item}" for item in items] or ["(none)"]


def _fence(text: str) -> list[str]:
    runs = re.findall(r"`+", text)
    fence = "`" * max([3] + [len(r) + 1 for r in runs])
    return [fence + "diff", text.rstrip("\n"), fence]


def render_markdown(packet: dict) -> str:
    lines: list[str] = ["# Review Packet", ""]

    def section(title, body):
        lines.extend([f"## {title}", "", *body, ""])

    section("Spec Diff", _fence(packet["spec_diff"]))
    section("Changed Requirements", _bullets(packet["changed_requirements"]))
    section("Regenerated Components", _bullets(packet["regenerated_components"]))
    section(
        "Verification Results",
        _bullets(f"{cid}: {_dump(v)}" for cid, v in packet["verification_results"].items()),
    )
    flags = packet["compliance_flags"]
    section(
        "Compliance Flags",
        [
            "### License Scan",
            "",
            *_bullets(f"{e['component_id']}: {_dump(e['result'])}" for e in flags["license_scan"]),
            "",
            "### Secret Scan",
            "",
            *_bullets(
                f"{e['component_id'] or '(repository)'}: {_dump(e['result'])}"
                for e in flags["secret_scan"]
            ),
        ],
    )
    section(
        "Provenance Hit Status",
        _bullets(
            f"{cid}: hit={'true' if hit else 'false'}"
            for cid, hit in packet["provenance_hit_status"].items()
        ),
    )
    exemptions = packet["exemption_changes"]
    section(
        "Exemption Changes",
        [
            f"**Sealed:** {', '.join(exemptions['sealed']) or '(none)'}",
            "",
            f"**Pinned Overrides:** {', '.join(exemptions['pinned_overrides']) or '(none)'}",
        ],
    )
    section(
        "Residual Risk",
        _bullets(f"{e['component_id']}: {e['message']}" for e in packet["residual_risk"]),
    )
    section(
        "Capability Scenarios",
        _bullets(f"{pid}: {_dump(v)}" for pid, v in packet["capability_scenarios"].items()),
    )
    return "\n".join(lines)


# ------------------------------------------------------------------------- CLI


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

    flags = {"--changed": [], "--repo-root": [], "--format": []}
    tokens = argv[2:]
    i = 0
    while i < len(tokens):
        token = tokens[i]
        name, sep, value = token.partition("=")
        if name not in flags:
            return _usage_error(f"unknown argument {token}")
        if not sep:
            if i + 1 >= len(tokens):
                return _usage_error(f"{name} requires a value")
            i += 1
            value = tokens[i]
        flags[name].append(value)
        i += 1

    if not flags["--changed"]:
        return _usage_error("--changed is required")
    fmt = (flags["--format"] or ["markdown"])[-1]
    if fmt not in ("markdown", "json"):
        return _usage_error(f"invalid --format {fmt}")
    repo_root = Path((flags["--repo-root"] or [os.getcwd()])[-1])

    try:
        packet = build_review_packet(flags["--changed"], repo_root)
    except Exception as exc:  # a required upstream result was missing
        print(str(exc), file=sys.stderr)
        return 1

    if fmt == "json":
        print(json.dumps(packet, indent=2, sort_keys=True, default=_json_default))
    else:
        print(render_markdown(packet))
    return 0


if __name__ == "__main__":
    sys.exit(main())
