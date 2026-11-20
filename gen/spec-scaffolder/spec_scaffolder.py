"""Spec Scaffolder: mechanical scaffolding of decisions, components and asset kinds."""

import os
import re
import subprocess
import sys
from pathlib import Path

_DECISION_FILE_RE = re.compile(r"^D([1-9][0-9]*)\.md$")
_DECISION_ID_RE = re.compile(r"^D[1-9][0-9]*$")
_SLUG_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_KIND_RE = re.compile(r"^[a-z][a-z0-9]*$")

_PENDING = "PENDING-COMMIT"


def _decisions_dir(repo_root):
    return Path(repo_root) / "specs" / "decisions"


def _flow(items):
    return "[" + ", ".join(items) + "]"


def _write_new(path, text):
    with open(path, "x", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _read(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _eol(line):
    return line[len(line.rstrip("\r\n")):]


def _frontmatter_end(lines):
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            return i
    return len(lines)


def _check_decision_id(decision_id):
    if not _DECISION_ID_RE.match(decision_id):
        raise ValueError(f"invalid decision id: {decision_id!r}")


def _record_lines(repo_root, decision_id):
    _check_decision_id(decision_id)
    path = _decisions_dir(repo_root) / f"{decision_id}.md"
    if not path.is_file():
        raise LookupError(f"no decision record: {decision_id}")
    lines = _read(path).splitlines(keepends=True)
    return path, lines, _frontmatter_end(lines)


def next_decision_id(repo_root):
    ddir = _decisions_dir(repo_root)
    largest = 0
    if ddir.is_dir():
        for entry in ddir.iterdir():
            m = _DECISION_FILE_RE.match(entry.name)
            if m and entry.is_file():
                largest = max(largest, int(m.group(1)))
    return f"D{largest + 1}"


def new_decision(repo_root, title, owners=None, builds_on=None, supersedes=None):
    owners = ["unassigned"] if owners is None else list(owners)
    builds_on = [] if builds_on is None else list(builds_on)
    if not title:
        raise ValueError("title must not be empty")
    ddir = _decisions_dir(repo_root)
    referenced = list(builds_on)
    if supersedes is not None:
        referenced.append(supersedes)
    for ref in referenced:
        if not (ddir / f"{ref}.md").is_file():
            raise ValueError(f"no decision record for {ref!r}")
    decision_id = next_decision_id(repo_root)
    lines = [
        "---",
        f"id: {decision_id}",
        f"title: {title}",
        "status: draft",
        f"owners: {_flow(owners)}",
    ]
    if builds_on:
        lines.append(f"builds_on: {_flow(builds_on)}")
    if supersedes is not None:
        lines.append(f"supersedes: {supersedes}")
    lines += [
        "---",
        "",
        f"# {decision_id} — {title}",
        "",
        "## Context",
        "",
        "TODO.",
        "",
        "## Decision",
        "",
        "TODO.",
        "",
        "## Consequences",
        "",
        "TODO.",
    ]
    ddir.mkdir(parents=True, exist_ok=True)
    path = ddir / f"{decision_id}.md"
    _write_new(path, "".join(line + "\n" for line in lines))
    return path


def ratify(repo_root, decision_id):
    path, lines, end = _record_lines(repo_root, decision_id)
    front = [line.rstrip("\r\n") for line in lines[1:end]]
    if "status: ratified" in front:
        raise LookupError(f"decision {decision_id} is already ratified")
    new_lines = list(lines)
    superseded = None
    for i in range(1, end):
        bare = lines[i].rstrip("\r\n")
        if bare == "status: draft":
            new_lines[i] = "status: ratified" + _eol(lines[i])
        elif bare.startswith("supersedes: "):
            superseded = bare[len("supersedes: "):].strip()
    new_lines.insert(end, f"last_ratified_commit: {_PENDING}\n")
    changes = [(path, "".join(new_lines))]
    if superseded is not None:
        old_path = _decisions_dir(repo_root) / f"{superseded}.md"
        old_lines = _read(old_path).splitlines(keepends=True)
        old_end = _frontmatter_end(old_lines)
        for i in range(1, old_end):
            if old_lines[i].startswith("status:"):
                old_lines[i] = "status: deprecated" + _eol(old_lines[i])
        changes.append((old_path, "".join(old_lines)))
    for target, text in changes:
        _write(target, text)
    return [target for target, _ in changes]


def record_commit(repo_root, decision_id, commit=None):
    path, lines, end = _record_lines(repo_root, decision_id)
    front = [line.rstrip("\r\n") for line in lines[1:end]]
    if "status: ratified" not in front:
        raise LookupError(f"decision {decision_id} is not ratified")
    pending_line = f"last_ratified_commit: {_PENDING}"
    if pending_line not in front:
        raise LookupError(f"decision {decision_id} already has a recorded commit")
    if commit is None:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--",
             f"specs/decisions/{decision_id}.md"],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        commit = proc.stdout.strip()
        if not commit:
            raise LookupError(f"no commit touches decision {decision_id}")
    index = 1 + front.index(pending_line)
    lines[index] = f"last_ratified_commit: {commit}" + _eol(lines[index])
    _write(path, "".join(lines))
    return commit


def new_component(repo_root, slug, title=None, owners=None, depends_on=None,
                  realizes=None, sealed=False):
    if not _SLUG_RE.match(slug):
        raise ValueError(f"slug is not kebab-case: {slug!r}")
    cdir = Path(repo_root) / "specs" / "components" / slug
    if cdir.exists():
        raise FileExistsError(f"component directory already exists: {slug}")
    if title is None:
        title = " ".join(word.capitalize() for word in slug.split("-"))
    owners = ["unassigned"] if owners is None else list(owners)
    depends_on = [] if depends_on is None else list(depends_on)
    realizes = [] if realizes is None else list(realizes)
    component_lines = [
        "---",
        f"id: comp-{slug}",
        f"title: {title}",
        "status: draft",
        f"owners: {_flow(owners)}",
        f"depends_on: {_flow(depends_on)}",
        f"realizes: {_flow(realizes)}",
        f"sealed: {'true' if sealed else 'false'}",
        "---",
        "",
        f"# {title}",
        "",
        "## Purpose",
        "",
        "TODO.",
        "",
        "## Scope",
        "",
        "TODO.",
        "",
        "## Definitions",
        "",
        "No deltas from `specs/glossary.md`.",
        "",
        "## Behavior",
        "",
        "See `requirements/`.",
        "",
        "## Interfaces",
        "",
        "See `interface/`.",
        "",
        "## Data",
        "",
        "See `interface/data/`.",
        "",
        "## Acceptance criteria",
        "",
        "See `acceptance/`.",
        "",
        "## Non-functional constraints",
        "",
        "See `constraints.md`.",
        "",
        "## Open questions",
        "",
        "None.",
        "",
        "## Change log",
        "",
        "- Initial draft.",
    ]
    constraints_lines = [
        f"# {title} — Non-Functional Constraints",
        "",
        "- TODO.",
    ]
    cdir.mkdir(parents=True)
    _write_new(cdir / "component.md",
               "".join(line + "\n" for line in component_lines))
    _write_new(cdir / "constraints.md",
               "".join(line + "\n" for line in constraints_lines))
    for sub in ("requirements", "acceptance", "interface",
                os.path.join("interface", "data")):
        sdir = cdir / sub
        sdir.mkdir(parents=True, exist_ok=True)
        _write_new(sdir / ".gitkeep", "")
    return cdir


def _definition_text(kind, title, owners):
    lines = [
        "---",
        f"id: arch-asset-kind-{kind}",
        f"title: Asset kind {title}",
        "status: draft",
        f"owners: {_flow(owners)}",
        "depends_on: []",
        "---",
        "",
        f"# Asset kind `{kind}`",
        "",
        f"TODO: say what the asset is and who consumes it; `comp-kind-{kind}` is its adapter.",
        "",
        "## Layout",
        "",
        "TODO: state what the file at the declared path must be, and the exact message `layout_errors` returns for each way it can be wrong.",
        "",
        "## Environment",
        "",
        f"TODO: list each program the kind needs with its minimum version and the command that prints it, any lockfile under `environments/{kind}/`, and `provision`'s exact failure reasons.",
        "",
        "## Surface",
        "",
        "TODO: state what a consumer may rely on, extractable by code without judgement, and its notation in the asset's interface file.",
        "",
        "## Running criteria",
        "",
        "TODO: state what `asset_runner` takes and returns, with one example call and its JSON result.",
        "",
        "## Strength check",
        "",
        "TODO: write this section first: choose mutation, perturbation or evaluation, and list every site, so that each concrete wrong version of an asset is caught by at least one.",
        "",
        "## Test author guidance",
        "",
        "TODO: state exactly the text `guidance()[\"test_author\"]` returns: how a test builds fixtures and calls `asset_runner`, and what it must not do, never a requirement restated.",
        "",
        "## Generator guidance",
        "",
        "TODO: state exactly the text `guidance()[\"generator\"]` returns: the conventions the asset must follow, never test mechanics.",
    ]
    return "".join(line + "\n" for line in lines)


def _adapter_files(kind):
    module = kind.replace("-", "_")
    upper = kind.upper()
    library = [
        "# Library",
        "",
        f"One module file, `kind_{module}.py`, never a package.",
        "",
        "```",
        "KIND: str           # \"" + kind + "\"",
        "GATE_VERSION: str   # \"kind-" + kind + "@0.1.0\"",
        "class AssetError(Exception)",
        "layout_errors(asset_file: Path) -> list[str]",
        "surface(asset_file: Path) -> dict",
        "provision(repo_root: Path) -> dict",
        "asset_runner(asset_file: Path) -> Callable[[str, list], object]",
        "strength_sites(asset_file: Path) -> list[dict]",
        "apply_site(asset_file: Path, site: dict) -> None",
        "guidance() -> dict",
        "```",
        "",
        f"Implements: `specs/architecture/asset-kinds.md`, `specs/architecture/asset-kind-{kind}.md`",
    ]
    requirement = [
        f"# R-KIND-{upper}-001",
        "",
        f"**R-KIND-{upper}-001** — TODO: `kind_{module}` MUST carry out `specs/architecture/asset-kind-{kind}.md`; replace this with one requirement per behaviour the definition states.",
    ]
    acceptance = [
        f"# AC-KIND-{upper}-001",
        "",
        f"Covers: R-KIND-{upper}-001",
        "Kind: generated-test",
        "",
        "```gherkin",
        "Given TODO: a correct asset with a suite that checks it, and the same asset with a weak suite",
        "When each site strength_sites lists is applied alone with apply_site and each suite is run",
        "Then the correct suite kills at least the bar's share of the sites and the weak suite fewer",
        "```",
    ]
    return [
        (os.path.join("interface", "library.md"), library),
        (os.path.join("requirements", f"R-KIND-{upper}-001.md"), requirement),
        (os.path.join("acceptance", f"AC-KIND-{upper}-001.md"), acceptance),
    ]


def new_kind(repo_root, kind, title=None, owners=None, realizes=None):
    if not _KIND_RE.match(kind) or kind == "python":
        raise ValueError(f"invalid asset kind: {kind!r}")
    root = Path(repo_root)
    arch_dir = root / "specs" / "architecture"
    definition = arch_dir / f"asset-kind-{kind}.md"
    cdir = root / "specs" / "components" / f"kind-{kind}"
    if definition.exists() or cdir.exists():
        raise FileExistsError(f"asset kind already exists: {kind}")
    if title is None:
        title = kind
    owners = ["unassigned"] if owners is None else list(owners)
    arch_dir.mkdir(parents=True, exist_ok=True)
    _write_new(definition, _definition_text(kind, title, owners))
    component_dir = new_component(root, f"kind-{kind}", title=f"Kind {title}",
                                  owners=owners, realizes=realizes)
    for rel, lines in _adapter_files(kind):
        _write_new(component_dir / rel, "".join(line + "\n" for line in lines))
    decision = new_decision(root, f"Asset kind {kind}", owners=owners)
    return [definition, component_dir, decision]


# ---------------------------------------------------------------- CLI

_USAGE = {
    ("decision", "new"): "hotdocs decision new <title> [--owners=<a,b>] [--builds-on=<D1,D2>] [--supersedes=<D<N>>] [--repo-root=<dir>]",
    ("decision", "ratify"): "hotdocs decision ratify <D<N>> [--repo-root=<dir>]",
    ("decision", "record-commit"): "hotdocs decision record-commit <D<N>> [--commit=<hash>] [--repo-root=<dir>]",
    ("component", "new"): "hotdocs component new <slug> [--title=<title>] [--owners=<a,b>] [--depends-on=<comp-a,comp-b>] [--realizes=<P-a,P-b>] [--sealed] [--repo-root=<dir>]",
    ("kind", "new"): "hotdocs kind new <kind> [--title=<title>] [--owners=<a,b>] [--realizes=<P-a,P-b>] [--repo-root=<dir>]",
}

_FLAGS = {
    ("decision", "new"): (("--owners", "--builds-on", "--supersedes", "--repo-root"), ()),
    ("decision", "ratify"): (("--repo-root",), ()),
    ("decision", "record-commit"): (("--commit", "--repo-root"), ()),
    ("component", "new"): (("--title", "--owners", "--depends-on", "--realizes",
                            "--repo-root"), ("--sealed",)),
    ("kind", "new"): (("--title", "--owners", "--realizes", "--repo-root"), ()),
}


class _UsageError(Exception):
    pass


def _parse(tokens, value_flags, bool_flags):
    positionals = []
    opts = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--"):
            name, eq, value = tok.partition("=")
            if name in value_flags:
                if not eq:
                    if i + 1 >= len(tokens):
                        raise _UsageError(f"{name} needs a value")
                    i += 1
                    value = tokens[i]
                opts[name] = value
            elif name in bool_flags and not eq:
                opts[name] = True
            else:
                raise _UsageError(f"unknown argument {tok}")
        else:
            positionals.append(tok)
        i += 1
    if not positionals:
        raise _UsageError("missing required argument")
    if len(positionals) > 1:
        raise _UsageError(f"unknown argument {positionals[1]}")
    return positionals[0], opts


def _split(value):
    if value is None:
        return None
    return [part.strip() for part in value.split(",")]


def _rel(path, root):
    return Path(path).relative_to(root).as_posix()


def _run(command, arg, opts):
    root = Path(opts.get("--repo-root", os.getcwd()))
    if command == ("decision", "new"):
        path = new_decision(root, arg, owners=_split(opts.get("--owners")),
                            builds_on=_split(opts.get("--builds-on")),
                            supersedes=opts.get("--supersedes"))
        return [_rel(path, root)]
    if command == ("decision", "ratify"):
        return [_rel(p, root) for p in ratify(root, arg)]
    if command == ("decision", "record-commit"):
        return [record_commit(root, arg, commit=opts.get("--commit"))]
    if command == ("component", "new"):
        path = new_component(root, arg, title=opts.get("--title"),
                             owners=_split(opts.get("--owners")),
                             depends_on=_split(opts.get("--depends-on")),
                             realizes=_split(opts.get("--realizes")),
                             sealed=bool(opts.get("--sealed", False)))
        return [_rel(path, root) + "/"]
    definition, cdir, decision = new_kind(root, arg, title=opts.get("--title"),
                                          owners=_split(opts.get("--owners")),
                                          realizes=_split(opts.get("--realizes")))
    return [_rel(definition, root), _rel(cdir, root) + "/", _rel(decision, root)]


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    command = tuple(argv[:2])
    if command not in _USAGE:
        cause = "unknown command " + " ".join(argv[:2]) if argv else "missing command"
        print(f"usage error: {cause}", file=sys.stderr)
        for line in _USAGE.values():
            print(f"usage: {line}", file=sys.stderr)
        return 2
    value_flags, bool_flags = _FLAGS[command]
    try:
        arg, opts = _parse(argv[2:], value_flags, bool_flags)
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(f"usage: {_USAGE[command]}", file=sys.stderr)
        return 2
    try:
        output = _run(command, arg, opts)
    except (ValueError, FileExistsError, LookupError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for line in output:
        print(line)
    return 0
