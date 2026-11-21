"""Spec Scaffolder: writes the structure and frontmatter of specbase files."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_KEBAB = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_DECISION_FILE = re.compile(r"^D([1-9][0-9]*)\.md$")
_DECISION_ID = re.compile(r"^D[1-9][0-9]*$")
_PENDING_LINE = "last_ratified_commit: PENDING-COMMIT\n"


def _flow(items):
    return "[" + ", ".join(items) + "]"


def _owners(owners):
    return ["unassigned"] if owners is None else list(owners)


def _decisions_dir(repo_root):
    return Path(repo_root) / "specs" / "decisions"


def _record_path(repo_root, decision_id):
    if not _DECISION_ID.match(decision_id):
        raise ValueError(f"decision id {decision_id!r} is not of the form D<N>")
    path = _decisions_dir(repo_root) / f"{decision_id}.md"
    if not path.is_file():
        raise LookupError(f"no decision record {decision_id}")
    return path


def _read_lines(path):
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    end = lines.index("---\n", 1)
    return lines, end


def next_decision_id(repo_root: Path) -> str:
    directory = _decisions_dir(repo_root)
    largest = 0
    if directory.is_dir():
        for entry in directory.iterdir():
            match = _DECISION_FILE.match(entry.name)
            if match:
                largest = max(largest, int(match.group(1)))
    return f"D{largest + 1}"


def new_decision(repo_root: Path, title: str, owners: list[str] | None = None,
                 builds_on: list[str] | None = None,
                 supersedes: str | None = None) -> Path:
    if not title:
        raise ValueError("title must not be empty")
    directory = _decisions_dir(repo_root)
    builds_on = list(builds_on or [])
    referenced = builds_on + ([supersedes] if supersedes is not None else [])
    for ref in referenced:
        if not (directory / f"{ref}.md").is_file():
            raise ValueError(f"no decision record {ref} under specs/decisions/")
    decision_id = next_decision_id(repo_root)
    lines = [
        "---",
        f"id: {decision_id}",
        f"title: {title}",
        "status: draft",
        f"owners: {_flow(_owners(owners))}",
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
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{decision_id}.md"
    with open(path, "x", encoding="utf-8") as handle:
        handle.write("".join(line + "\n" for line in lines))
    return path


def ratify(repo_root: Path, decision_id: str) -> list[Path]:
    path = _record_path(repo_root, decision_id)
    lines, end = _read_lines(path)
    frontmatter = lines[1:end]
    if "status: draft\n" not in frontmatter:
        raise LookupError(f"decision {decision_id} is already ratified")
    status_index = lines.index("status: draft\n", 1)
    lines[status_index] = "status: ratified\n"
    lines.insert(end, _PENDING_LINE)
    changed = [path]
    writes = [(path, lines)]
    for line in frontmatter:
        if line.startswith("supersedes: "):
            old_id = line[len("supersedes: "):].strip()
            old_path = _decisions_dir(repo_root) / f"{old_id}.md"
            old_lines, old_end = _read_lines(old_path)
            for index in range(1, old_end):
                if old_lines[index].startswith("status:"):
                    old_lines[index] = "status: deprecated\n"
            changed.append(old_path)
            writes.append((old_path, old_lines))
    for target, content in writes:
        target.write_text("".join(content), encoding="utf-8")
    return changed


def record_commit(repo_root: Path, decision_id: str, commit: str | None = None) -> str:
    path = _record_path(repo_root, decision_id)
    lines, end = _read_lines(path)
    index = None
    for i in range(1, end):
        if lines[i].startswith("last_ratified_commit:"):
            index = i
    if index is None:
        raise LookupError(f"decision {decision_id} is not ratified")
    if lines[index] != _PENDING_LINE:
        raise LookupError(f"decision {decision_id} already records a commit")
    if commit is None:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--",
             f"specs/decisions/{decision_id}.md"],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        commit = result.stdout.strip()
        if not commit:
            raise LookupError(f"no commit touches specs/decisions/{decision_id}.md")
    lines[index] = f"last_ratified_commit: {commit}\n"
    path.write_text("".join(lines), encoding="utf-8")
    return commit


def new_component(repo_root: Path, slug: str, title: str | None = None,
                  owners: list[str] | None = None, depends_on: list[str] | None = None,
                  realizes: list[str] | None = None, sealed: bool = False) -> Path:
    if not _KEBAB.match(slug):
        raise ValueError(f"slug {slug!r} is not kebab-case")
    directory = Path(repo_root) / "specs" / "components" / slug
    if directory.exists():
        raise FileExistsError(f"{directory} already exists")
    if title is None:
        title = " ".join(word.capitalize() for word in slug.split("-"))
    lines = [
        "---",
        f"id: comp-{slug}",
        f"title: {title}",
        "status: draft",
        f"owners: {_flow(_owners(owners))}",
        f"depends_on: {_flow(depends_on or [])}",
        f"realizes: {_flow(realizes or [])}",
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
    directory.mkdir(parents=True)
    (directory / "component.md").write_text(
        "".join(line + "\n" for line in lines), encoding="utf-8")
    (directory / "constraints.md").write_text(
        f"# {title} — Non-Functional Constraints\n\n- TODO.\n", encoding="utf-8")
    for sub in ("requirements", "acceptance", "interface", "interface/data"):
        sub_dir = directory / sub
        sub_dir.mkdir(parents=True)
        (sub_dir / ".gitkeep").write_text("", encoding="utf-8")
    return directory


def new_kind(repo_root: Path, kind: str, title: str | None = None,
             owners: list[str] | None = None,
             realizes: list[str] | None = None) -> list[Path]:
    if not _KEBAB.match(kind) or kind == "python":
        raise ValueError(f"kind {kind!r} is not a kebab-case kind other than python")
    root = Path(repo_root)
    definition = root / "specs" / "architecture" / f"asset-kind-{kind}.md"
    component_dir = root / "specs" / "components" / f"kind-{kind}"
    for target in (definition, component_dir):
        if target.exists():
            raise FileExistsError(f"{target} already exists")
    if title is None:
        title = kind
    module = kind.replace("-", "_")
    upper = kind.upper()
    definition_lines = [
        "---",
        f"id: arch-asset-kind-{kind}",
        f"title: Asset kind {title}",
        "status: draft",
        f"owners: {_flow(_owners(owners))}",
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
    library_lines = [
        "# Library",
        "",
        f"One module file, `kind_{module}.py`, never a package.",
        "",
        "```",
        f"KIND: str           # \"{kind}\"",
        f"GATE_VERSION: str   # \"kind-{kind}@0.1.0\"",
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
    requirement_lines = [
        f"# R-KIND-{upper}-001",
        "",
        f"**R-KIND-{upper}-001** — TODO: `kind_{module}` MUST carry out `specs/architecture/asset-kind-{kind}.md`; replace this with one requirement per behaviour the definition states.",
    ]
    acceptance_lines = [
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
    definition.parent.mkdir(parents=True, exist_ok=True)
    definition.write_text("".join(line + "\n" for line in definition_lines), encoding="utf-8")
    directory = new_component(root, f"kind-{kind}", title=f"Kind {title}",
                              owners=owners, realizes=realizes)
    extras = [
        (directory / "interface" / "library.md", library_lines),
        (directory / "requirements" / f"R-KIND-{upper}-001.md", requirement_lines),
        (directory / "acceptance" / f"AC-KIND-{upper}-001.md", acceptance_lines),
    ]
    for target, content in extras:
        target.write_text("".join(line + "\n" for line in content), encoding="utf-8")
    decision = new_decision(root, f"Asset kind {kind}", owners=owners)
    return [definition, directory, decision]


_USAGE = {
    ("decision", "new"): "usage: hotdocs decision new <title> [--owners=<a,b>] [--builds-on=<D1,D2>] [--supersedes=<D<N>>] [--repo-root=<dir>]",
    ("decision", "ratify"): "usage: hotdocs decision ratify <D<N>> [--repo-root=<dir>]",
    ("decision", "record-commit"): "usage: hotdocs decision record-commit <D<N>> [--commit=<hash>] [--repo-root=<dir>]",
    ("component", "new"): "usage: hotdocs component new <slug> [--title=<title>] [--owners=<a,b>] [--depends-on=<comp-a,comp-b>] [--realizes=<P-a,P-b>] [--sealed] [--repo-root=<dir>]",
    ("kind", "new"): "usage: hotdocs kind new <kind> [--title=<title>] [--owners=<a,b>] [--realizes=<P-a,P-b>] [--repo-root=<dir>]",
}

_SPECS = {
    ("decision", "new"): ("<title>", ("owners", "builds-on", "supersedes", "repo-root"), ()),
    ("decision", "ratify"): ("<D<N>>", ("repo-root",), ()),
    ("decision", "record-commit"): ("<D<N>>", ("commit", "repo-root"), ()),
    ("component", "new"): ("<slug>", ("title", "owners", "depends-on", "realizes", "repo-root"), ("sealed",)),
    ("kind", "new"): ("<kind>", ("title", "owners", "realizes", "repo-root"), ()),
}


class _UsageError(Exception):
    pass


def _parse(tokens, positional_name, value_flags, bool_flags):
    opts = {}
    positionals = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            name, eq, value = token[2:].partition("=")
            if name in value_flags:
                if not eq:
                    i += 1
                    if i == len(tokens):
                        raise _UsageError(f"--{name} requires a value")
                    value = tokens[i]
                opts[name] = value
            elif name in bool_flags and not eq:
                opts[name] = True
            else:
                raise _UsageError(f"unrecognized argument: {token}")
        else:
            positionals.append(token)
        i += 1
    if not positionals:
        raise _UsageError(f"missing required argument {positional_name}")
    if len(positionals) > 1:
        raise _UsageError(f"unrecognized argument: {positionals[1]}")
    return positionals[0], opts


def _split(value):
    if value is None:
        return None
    return [item.strip() for item in value.split(",")]


def _rel(path, repo_root):
    return Path(path).relative_to(repo_root).as_posix()


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    command = tuple(argv[:2])
    if command not in _SPECS:
        print(f"usage error: unknown command: {' '.join(argv[:2]) or '(none)'}", file=sys.stderr)
        print("\n".join(_USAGE.values()), file=sys.stderr)
        return 2
    positional_name, value_flags, bool_flags = _SPECS[command]
    try:
        arg, opts = _parse(argv[2:], positional_name, value_flags, bool_flags)
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(_USAGE[command], file=sys.stderr)
        return 2
    repo_root = Path(opts.get("repo-root", "."))
    try:
        if command == ("decision", "new"):
            path = new_decision(repo_root, arg, owners=_split(opts.get("owners")),
                                builds_on=_split(opts.get("builds-on")),
                                supersedes=opts.get("supersedes"))
            print(_rel(path, repo_root))
        elif command == ("decision", "ratify"):
            for path in ratify(repo_root, arg):
                print(_rel(path, repo_root))
        elif command == ("decision", "record-commit"):
            print(record_commit(repo_root, arg, commit=opts.get("commit")))
        elif command == ("component", "new"):
            path = new_component(repo_root, arg, title=opts.get("title"),
                                 owners=_split(opts.get("owners")),
                                 depends_on=_split(opts.get("depends-on")),
                                 realizes=_split(opts.get("realizes")),
                                 sealed=bool(opts.get("sealed", False)))
            print(_rel(path, repo_root) + "/")
        else:
            definition, directory, decision = new_kind(
                repo_root, arg, title=opts.get("title"),
                owners=_split(opts.get("owners")),
                realizes=_split(opts.get("realizes")))
            print(_rel(definition, repo_root))
            print(_rel(directory, repo_root) + "/")
            print(_rel(decision, repo_root))
    except (ValueError, FileExistsError, LookupError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0
