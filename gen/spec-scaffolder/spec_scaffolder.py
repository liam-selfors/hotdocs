"""Spec Scaffolder: writes the structure and frontmatter of specbase files."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_KEBAB = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_DECISION_FILE = re.compile(r"^D([1-9][0-9]*)\.md$")
_DECISION_ID = re.compile(r"^D[1-9][0-9]*$")
_PENDING_LINE = "last_ratified_commit: PENDING-COMMIT"


def _decisions_dir(repo_root: Path) -> Path:
    return Path(repo_root) / "specs" / "decisions"


def _flow(items) -> str:
    return "[" + ", ".join(items) + "]"


def _owners(owners):
    return owners if owners is not None else ["unassigned"]


def _text(lines) -> str:
    return "\n".join(lines) + "\n"


def _write_new(path: Path, text: str) -> None:
    with open(path, "x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _rewrite(path: Path, lines) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write("".join(lines))


def _read_lines(path: Path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        lines = handle.read().splitlines(keepends=True)
    stripped = [line.rstrip("\r\n") for line in lines]
    end = stripped.index("---", 1)
    return lines, stripped, end


def _ending(line: str) -> str:
    return line[len(line.rstrip("\r\n")):]


def _title_from(slug: str) -> str:
    return " ".join(word.capitalize() for word in slug.split("-"))


def _check_decision_id(decision_id: str) -> None:
    if not _DECISION_ID.match(decision_id):
        raise ValueError(f"invalid decision id: {decision_id!r}")


def _record_path(repo_root: Path, decision_id: str) -> Path:
    _check_decision_id(decision_id)
    path = _decisions_dir(repo_root) / f"{decision_id}.md"
    if not path.is_file():
        raise LookupError(f"no decision record: {decision_id}")
    return path


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
    referenced = list(builds_on or [])
    if supersedes is not None:
        referenced.append(supersedes)
    for ref in referenced:
        if not (directory / f"{ref}.md").is_file():
            raise ValueError(f"no decision record: {ref}")
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
    _write_new(path, _text(lines))
    return path


def ratify(repo_root: Path, decision_id: str) -> list[Path]:
    path = _record_path(repo_root, decision_id)
    lines, stripped, end = _read_lines(path)
    front = stripped[1:end]
    if "status: draft" not in front:
        raise LookupError(f"decision {decision_id} is not a draft")
    idx = stripped.index("status: draft", 1)
    lines[idx] = "status: ratified" + _ending(lines[idx])
    lines.insert(end, _PENDING_LINE + "\n")

    changed = [path]
    superseded = None
    for item in front:
        if item.startswith("supersedes: "):
            sup_id = item[len("supersedes: "):].strip()
            sup_path = _decisions_dir(repo_root) / f"{sup_id}.md"
            sup_lines, sup_stripped, sup_end = _read_lines(sup_path)
            for i in range(1, sup_end):
                if sup_stripped[i].startswith("status:"):
                    sup_lines[i] = "status: deprecated" + _ending(sup_lines[i])
            superseded = (sup_path, sup_lines)

    _rewrite(path, lines)
    if superseded is not None:
        _rewrite(superseded[0], superseded[1])
        changed.append(superseded[0])
    return changed


def record_commit(repo_root: Path, decision_id: str,
                  commit: str | None = None) -> str:
    path = _record_path(repo_root, decision_id)
    lines, stripped, end = _read_lines(path)
    front = stripped[1:end]
    if "status: ratified" not in front:
        raise LookupError(f"decision {decision_id} is not ratified")
    if _PENDING_LINE not in front:
        raise LookupError(f"decision {decision_id} already has a recorded commit")
    if commit is None:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--",
             f"specs/decisions/{decision_id}.md"],
            cwd=str(repo_root), capture_output=True, text=True,
        )
        commit = result.stdout.strip()
        if not commit:
            raise LookupError(f"no commit touches decision {decision_id}")
    idx = stripped.index(_PENDING_LINE, 1)
    lines[idx] = f"last_ratified_commit: {commit}" + _ending(lines[idx])
    _rewrite(path, lines)
    return commit


def _check_component(repo_root: Path, slug: str) -> Path:
    if not _KEBAB.match(slug):
        raise ValueError(f"slug is not kebab-case: {slug!r}")
    directory = Path(repo_root) / "specs" / "components" / slug
    if directory.exists():
        raise FileExistsError(f"already exists: specs/components/{slug}/")
    return directory


def new_component(repo_root: Path, slug: str, title: str | None = None,
                  owners: list[str] | None = None,
                  depends_on: list[str] | None = None,
                  realizes: list[str] | None = None,
                  sealed: bool = False) -> Path:
    directory = _check_component(repo_root, slug)
    if title is None:
        title = _title_from(slug)
    component = [
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
    constraints = [f"# {title} — Non-Functional Constraints", "", "- TODO."]
    directory.mkdir(parents=True)
    _write_new(directory / "component.md", _text(component))
    _write_new(directory / "constraints.md", _text(constraints))
    for sub in ("requirements", "acceptance", "interface", "interface/data"):
        subdir = directory / sub
        subdir.mkdir(parents=True, exist_ok=True)
        _write_new(subdir / ".gitkeep", "")
    return directory


def new_kind(repo_root: Path, kind: str, title: str | None = None,
             owners: list[str] | None = None,
             realizes: list[str] | None = None) -> list[Path]:
    if not _KEBAB.match(kind) or kind == "python":
        raise ValueError(f"invalid kind: {kind!r}")
    arch_dir = Path(repo_root) / "specs" / "architecture"
    definition = arch_dir / f"asset-kind-{kind}.md"
    if definition.exists():
        raise FileExistsError(
            f"already exists: specs/architecture/asset-kind-{kind}.md")
    _check_component(repo_root, f"kind-{kind}")
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

    arch_dir.mkdir(parents=True, exist_ok=True)
    _write_new(definition, _text(definition_lines))
    component_dir = new_component(repo_root, f"kind-{kind}",
                                  title=f"Kind {title}", owners=owners,
                                  realizes=realizes)
    _write_new(component_dir / "interface" / "library.md", _text(library_lines))
    _write_new(component_dir / "requirements" / f"R-KIND-{upper}-001.md",
               _text(requirement_lines))
    _write_new(component_dir / "acceptance" / f"AC-KIND-{upper}-001.md",
               _text(acceptance_lines))
    decision = new_decision(repo_root, f"Asset kind {kind}", owners=owners)
    return [definition, component_dir, decision]


def new_capability(repo_root: Path, name: str, title: str | None = None,
                   owners: list[str] | None = None) -> Path:
    if not _KEBAB.match(name):
        raise ValueError(f"name is not kebab-case: {name!r}")
    directory = Path(repo_root) / "specs" / "product"
    path = directory / f"{name}.md"
    if path.exists():
        raise FileExistsError(f"already exists: specs/product/{name}.md")
    if title is None:
        title = _title_from(name)
    lines = [
        "---",
        f"id: P-{name.upper()}",
        f"title: {title}",
        "status: draft",
        f"owners: {_flow(_owners(owners))}",
        "---",
        "",
        f"# {title}",
        "",
        "## Purpose",
        "",
        "TODO.",
    ]
    directory.mkdir(parents=True, exist_ok=True)
    _write_new(path, _text(lines))
    return path


# ---------------------------------------------------------------------------
# CLI

_COMMANDS = {
    ("decision", "new"): (
        ["<title>"], {"owners", "builds-on", "supersedes", "repo-root"}, set(),
        "hotdocs decision new <title> [--owners=<a,b>] [--builds-on=<D1,D2>] "
        "[--supersedes=<D<N>>] [--repo-root=<dir>]"),
    ("decision", "ratify"): (
        ["<D<N>>"], {"repo-root"}, set(),
        "hotdocs decision ratify <D<N>> [--repo-root=<dir>]"),
    ("decision", "record-commit"): (
        ["<D<N>>"], {"commit", "repo-root"}, set(),
        "hotdocs decision record-commit <D<N>> [--commit=<hash>] [--repo-root=<dir>]"),
    ("component", "new"): (
        ["<slug>"], {"title", "owners", "depends-on", "realizes", "repo-root"},
        {"sealed"},
        "hotdocs component new <slug> [--title=<title>] [--owners=<a,b>] "
        "[--depends-on=<comp-a,comp-b>] [--realizes=<P-a,P-b>] [--sealed] "
        "[--repo-root=<dir>]"),
    ("kind", "new"): (
        ["<kind>"], {"title", "owners", "realizes", "repo-root"}, set(),
        "hotdocs kind new <kind> [--title=<title>] [--owners=<a,b>] "
        "[--realizes=<P-a,P-b>] [--repo-root=<dir>]"),
    ("capability", "new"): (
        ["<name>"], {"title", "owners", "repo-root"}, set(),
        "hotdocs capability new <name> [--title=<title>] [--owners=<a,b>] "
        "[--repo-root=<dir>]"),
}


class _UsageError(Exception):
    pass


def _usage_error(cause: str, usage_lines) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print("usage: " + "\n       ".join(usage_lines), file=sys.stderr)
    return 2


def _split(value):
    if value is None:
        return None
    return [part.strip() for part in value.split(",")]


def _parse(tokens, positional_names, value_flags, bool_flags):
    positional = []
    values = {}
    flags = set()
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            name, eq, value = token[2:].partition("=")
            if name in value_flags:
                if not eq:
                    if i + 1 >= len(tokens):
                        raise _UsageError(f"missing value for --{name}")
                    i += 1
                    value = tokens[i]
                values[name] = value
            elif name in bool_flags and not eq:
                flags.add(name)
            else:
                raise _UsageError(f"unknown argument: {token}")
        elif len(positional) < len(positional_names):
            positional.append(token)
        else:
            raise _UsageError(f"unknown argument: {token}")
        i += 1
    if len(positional) < len(positional_names):
        raise _UsageError(
            f"missing required argument: {positional_names[len(positional)]}")
    return positional, values, flags


def _rel(path: Path, repo_root: Path) -> str:
    return Path(path).relative_to(repo_root).as_posix()


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    key = tuple(argv[:2])
    if key not in _COMMANDS:
        cause = ("missing command" if not argv
                 else f"unknown command: {' '.join(argv[:2])}")
        return _usage_error(cause, [spec[3] for spec in _COMMANDS.values()])
    positional_names, value_flags, bool_flags, usage = _COMMANDS[key]
    try:
        positional, values, flags = _parse(argv[2:], positional_names,
                                           value_flags, bool_flags)
    except _UsageError as exc:
        return _usage_error(str(exc), [usage])

    repo_root = Path(values["repo-root"]) if "repo-root" in values else Path.cwd()
    arg = positional[0]
    try:
        if key == ("decision", "new"):
            path = new_decision(repo_root, arg, owners=_split(values.get("owners")),
                                builds_on=_split(values.get("builds-on")),
                                supersedes=values.get("supersedes"))
            print(_rel(path, repo_root))
        elif key == ("decision", "ratify"):
            for path in ratify(repo_root, arg):
                print(_rel(path, repo_root))
        elif key == ("decision", "record-commit"):
            print(record_commit(repo_root, arg, commit=values.get("commit")))
        elif key == ("component", "new"):
            path = new_component(repo_root, arg, title=values.get("title"),
                                 owners=_split(values.get("owners")),
                                 depends_on=_split(values.get("depends-on")),
                                 realizes=_split(values.get("realizes")),
                                 sealed="sealed" in flags)
            print(_rel(path, repo_root) + "/")
        elif key == ("kind", "new"):
            definition, component_dir, decision = new_kind(
                repo_root, arg, title=values.get("title"),
                owners=_split(values.get("owners")),
                realizes=_split(values.get("realizes")))
            print(_rel(definition, repo_root))
            print(_rel(component_dir, repo_root) + "/")
            print(_rel(decision, repo_root))
        else:
            path = new_capability(repo_root, arg, title=values.get("title"),
                                  owners=_split(values.get("owners")))
            print(_rel(path, repo_root))
            print(f"id: P-{arg.upper()}")
    except (ValueError, FileExistsError, LookupError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0
