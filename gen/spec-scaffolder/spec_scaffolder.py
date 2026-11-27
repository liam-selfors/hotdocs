"""Spec Scaffolder: writes the structure and frontmatter of specbase files."""

import re
import subprocess
import sys
from pathlib import Path

_KEBAB = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_DECISION_FILE = re.compile(r"^D([1-9][0-9]*)\.md$")
_DECISION_ID = re.compile(r"^D[1-9][0-9]*$")
_PENDING = "PENDING-COMMIT"


def _write_new(path, text):
    with open(path, "x", encoding="utf-8", newline="") as f:
        f.write(text)


def _read_lines(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read().splitlines(keepends=True)


def _write_lines(path, lines):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("".join(lines))


def _bare(line):
    return line.rstrip("\r\n")


def _replace(line, text):
    return text + line[len(_bare(line)):]


def _frontmatter_end(lines):
    return next(i for i in range(1, len(lines)) if _bare(lines[i]) == "---")


def _flow(items):
    return "[" + ", ".join(items) + "]"


def _owners(owners):
    return ["unassigned"] if owners is None else list(owners)


def _words_title(slug):
    return " ".join(word.capitalize() for word in slug.split("-"))


def _decisions_dir(repo_root):
    return Path(repo_root) / "specs" / "decisions"


def _check_decision_id(decision_id):
    if not _DECISION_ID.match(decision_id):
        raise ValueError(f"not a decision id of the form D<N>: {decision_id!r}")


def next_decision_id(repo_root):
    directory = _decisions_dir(repo_root)
    numbers = [0]
    if directory.is_dir():
        for entry in directory.iterdir():
            match = _DECISION_FILE.match(entry.name)
            if match:
                numbers.append(int(match.group(1)))
    return f"D{max(numbers) + 1}"


def new_decision(repo_root, title, owners=None, builds_on=None, supersedes=None):
    if not title:
        raise ValueError("title must not be empty")
    directory = _decisions_dir(repo_root)
    builds_on = list(builds_on or [])
    referenced = builds_on + ([supersedes] if supersedes is not None else [])
    for ref in referenced:
        if not (directory / f"{ref}.md").is_file():
            raise ValueError(f"no decision record for {ref}")
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
    _write_new(path, "".join(line + "\n" for line in lines))
    return path


def ratify(repo_root, decision_id):
    _check_decision_id(decision_id)
    directory = _decisions_dir(repo_root)
    path = directory / f"{decision_id}.md"
    if not path.is_file():
        raise LookupError(f"no decision record for {decision_id}")
    lines = _read_lines(path)
    end = _frontmatter_end(lines)
    front = [_bare(line) for line in lines[:end]]
    if "status: ratified" in front:
        raise LookupError(f"{decision_id} is already ratified")
    new_lines = [
        _replace(line, "status: ratified") if i < end and _bare(line) == "status: draft" else line
        for i, line in enumerate(lines)
    ]
    new_lines.insert(end, f"last_ratified_commit: {_PENDING}\n")
    changed = [(path, new_lines)]
    for entry in front:
        if entry.startswith("supersedes:"):
            old_id = entry[len("supersedes:"):].strip()
            old_path = directory / f"{old_id}.md"
            old_lines = _read_lines(old_path)
            old_end = _frontmatter_end(old_lines)
            old_new = [
                _replace(line, "status: deprecated")
                if 0 < i < old_end and _bare(line).startswith("status:")
                else line
                for i, line in enumerate(old_lines)
            ]
            changed.append((old_path, old_new))
    for changed_path, changed_lines in changed:
        _write_lines(changed_path, changed_lines)
    return [changed_path for changed_path, _ in changed]


def record_commit(repo_root, decision_id, commit=None):
    _check_decision_id(decision_id)
    path = _decisions_dir(repo_root) / f"{decision_id}.md"
    if not path.is_file():
        raise LookupError(f"no decision record for {decision_id}")
    lines = _read_lines(path)
    end = _frontmatter_end(lines)
    front = [_bare(line) for line in lines[:end]]
    if "status: ratified" not in front:
        raise LookupError(f"{decision_id} is not ratified")
    pending = f"last_ratified_commit: {_PENDING}"
    if pending not in front:
        raise LookupError(f"{decision_id} already records a commit")
    if commit is None:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--", f"specs/decisions/{decision_id}.md"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        commit = result.stdout.strip()
        if not commit:
            raise LookupError(f"no commit touches specs/decisions/{decision_id}.md")
    new_lines = [
        _replace(line, f"last_ratified_commit: {commit}")
        if i < end and _bare(line) == pending
        else line
        for i, line in enumerate(lines)
    ]
    _write_lines(path, new_lines)
    return commit


def new_component(repo_root, slug, title=None, owners=None, depends_on=None,
                  realizes=None, sealed=False):
    if not _KEBAB.match(slug):
        raise ValueError(f"slug is not kebab-case: {slug!r}")
    directory = Path(repo_root) / "specs" / "components" / slug
    if directory.exists():
        raise FileExistsError(f"{directory} already exists")
    if title is None:
        title = _words_title(slug)
    component_lines = [
        "---",
        f"id: comp-{slug}",
        f"title: {title}",
        "status: draft",
        f"owners: {_flow(_owners(owners))}",
        f"depends_on: {_flow(list(depends_on or []))}",
        f"realizes: {_flow(list(realizes or []))}",
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
    constraints_lines = [f"# {title} — Non-Functional Constraints", "", "- TODO."]
    directory.mkdir(parents=True)
    _write_new(directory / "component.md", "".join(l + "\n" for l in component_lines))
    _write_new(directory / "constraints.md", "".join(l + "\n" for l in constraints_lines))
    for sub in ("requirements", "acceptance", "interface", "interface/data"):
        subdir = directory / sub
        subdir.mkdir(parents=True)
        _write_new(subdir / ".gitkeep", "")
    return directory


def _definition_text(kind, title, owners):
    lines = [
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
        "TODO: state what the file at the declared path must be, and the exact message "
        "`layout_errors` returns for each way it can be wrong.",
        "",
        "## Environment",
        "",
        "TODO: list each program the kind needs with its minimum version and the command "
        f"that prints it, any lockfile under `environments/{kind}/`, and `provision`'s exact "
        "failure reasons.",
        "",
        "## Surface",
        "",
        "TODO: state what a consumer may rely on, extractable by code without judgement, "
        "and its notation in the asset's interface file.",
        "",
        "## Running criteria",
        "",
        "TODO: state what `asset_runner` takes and returns, with one example call and its "
        "JSON result.",
        "",
        "## Strength check",
        "",
        "TODO: write this section first: choose mutation, perturbation or evaluation, and "
        "list every site, so that each concrete wrong version of an asset is caught by at "
        "least one.",
        "",
        "## Test author guidance",
        "",
        "TODO: state exactly the text `guidance()[\"test_author\"]` returns: how a test "
        "builds fixtures and calls `asset_runner`, and what it must not do, never a "
        "requirement restated.",
        "",
        "## Generator guidance",
        "",
        "TODO: state exactly the text `guidance()[\"generator\"]` returns: the conventions "
        "the asset must follow, never test mechanics.",
    ]
    return "".join(line + "\n" for line in lines)


def _library_text(kind, module):
    lines = [
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
        "Implements: `specs/architecture/asset-kinds.md`, "
        f"`specs/architecture/asset-kind-{kind}.md`",
    ]
    return "".join(line + "\n" for line in lines)


def _requirement_text(kind, module, upper):
    lines = [
        f"# R-KIND-{upper}-001",
        "",
        f"**R-KIND-{upper}-001** — TODO: `kind_{module}` MUST carry out "
        f"`specs/architecture/asset-kind-{kind}.md`; replace this with one requirement per "
        "behaviour the definition states.",
    ]
    return "".join(line + "\n" for line in lines)


def _acceptance_text(upper):
    lines = [
        f"# AC-KIND-{upper}-001",
        "",
        f"Covers: R-KIND-{upper}-001",
        "Kind: generated-test",
        "",
        "```gherkin",
        "Given TODO: a correct asset with a suite that checks it, and the same asset with a "
        "weak suite",
        "When each site strength_sites lists is applied alone with apply_site and each suite "
        "is run",
        "Then the correct suite kills at least the bar's share of the sites and the weak "
        "suite fewer",
        "```",
    ]
    return "".join(line + "\n" for line in lines)


def new_kind(repo_root, kind, title=None, owners=None, realizes=None):
    if not _KEBAB.match(kind) or kind == "python":
        raise ValueError(f"invalid kind: {kind!r}")
    root = Path(repo_root)
    definition = root / "specs" / "architecture" / f"asset-kind-{kind}.md"
    component_dir = root / "specs" / "components" / f"kind-{kind}"
    if definition.exists():
        raise FileExistsError(f"{definition} already exists")
    if component_dir.exists():
        raise FileExistsError(f"{component_dir} already exists")
    if title is None:
        title = kind
    module = kind.replace("-", "_")
    upper = kind.upper()
    definition.parent.mkdir(parents=True, exist_ok=True)
    _write_new(definition, _definition_text(kind, title, owners))
    component_dir = new_component(root, f"kind-{kind}", title=f"Kind {title}",
                                  owners=owners, realizes=realizes)
    _write_new(component_dir / "interface" / "library.md", _library_text(kind, module))
    _write_new(component_dir / "requirements" / f"R-KIND-{upper}-001.md",
               _requirement_text(kind, module, upper))
    _write_new(component_dir / "acceptance" / f"AC-KIND-{upper}-001.md",
               _acceptance_text(upper))
    decision = new_decision(root, f"Asset kind {kind}", owners=owners)
    return [definition, component_dir, decision]


def new_capability(repo_root, name, title=None, owners=None):
    if not _KEBAB.match(name):
        raise ValueError(f"name is not kebab-case: {name!r}")
    path = Path(repo_root) / "specs" / "product" / f"{name}.md"
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    if title is None:
        title = _words_title(name)
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
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_new(path, "".join(line + "\n" for line in lines))
    return path


_COMMANDS = {
    ("decision", "new"): (
        "<title>",
        {"owners", "builds-on", "supersedes", "repo-root"},
        set(),
        "usage: hotdocs decision new <title> [--owners=<a,b>] [--builds-on=<D1,D2>] "
        "[--supersedes=<D<N>>] [--repo-root=<dir>]",
    ),
    ("decision", "ratify"): (
        "<D<N>>",
        {"repo-root"},
        set(),
        "usage: hotdocs decision ratify <D<N>> [--repo-root=<dir>]",
    ),
    ("decision", "record-commit"): (
        "<D<N>>",
        {"commit", "repo-root"},
        set(),
        "usage: hotdocs decision record-commit <D<N>> [--commit=<hash>] [--repo-root=<dir>]",
    ),
    ("component", "new"): (
        "<slug>",
        {"title", "owners", "depends-on", "realizes", "repo-root"},
        {"sealed"},
        "usage: hotdocs component new <slug> [--title=<title>] [--owners=<a,b>] "
        "[--depends-on=<comp-a,comp-b>] [--realizes=<P-a,P-b>] [--sealed] [--repo-root=<dir>]",
    ),
    ("kind", "new"): (
        "<kind>",
        {"title", "owners", "realizes", "repo-root"},
        set(),
        "usage: hotdocs kind new <kind> [--title=<title>] [--owners=<a,b>] "
        "[--realizes=<P-a,P-b>] [--repo-root=<dir>]",
    ),
    ("capability", "new"): (
        "<name>",
        {"title", "owners", "repo-root"},
        set(),
        "usage: hotdocs capability new <name> [--title=<title>] [--owners=<a,b>] "
        "[--repo-root=<dir>]",
    ),
}

_GENERAL_USAGE = (
    "usage: hotdocs {decision new|decision ratify|decision record-commit|"
    "component new|kind new|capability new} ..."
)


class _UsageError(Exception):
    pass


def _parse(tokens, value_flags, bool_flags, positional_name):
    positionals = []
    options = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            name, sep, value = token[2:].partition("=")
            if name in value_flags:
                if not sep:
                    if i + 1 >= len(tokens):
                        raise _UsageError(f"--{name} requires a value")
                    i += 1
                    value = tokens[i]
                options[name] = value
            elif name in bool_flags and not sep:
                options[name] = True
            else:
                raise _UsageError(f"unknown argument {token}")
        else:
            positionals.append(token)
        i += 1
    if not positionals:
        raise _UsageError(f"missing {positional_name}")
    if len(positionals) > 1:
        raise _UsageError(f"unexpected argument {positionals[1]}")
    return positionals[0], options


def _split(options, name):
    if name not in options:
        return None
    return [item.strip() for item in options[name].split(",")]


def _rel(path, repo_root):
    return Path(path).relative_to(repo_root).as_posix()


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    command = tuple(argv[:2])
    if command not in _COMMANDS:
        cause = f"unknown command {' '.join(argv[:2])}" if argv else "missing command"
        print(f"usage error: {cause}", file=sys.stderr)
        print(_GENERAL_USAGE, file=sys.stderr)
        return 2
    positional_name, value_flags, bool_flags, usage = _COMMANDS[command]
    try:
        arg, options = _parse(argv[2:], value_flags, bool_flags, positional_name)
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(usage, file=sys.stderr)
        return 2
    repo_root = Path(options["repo-root"]) if "repo-root" in options else Path.cwd()
    try:
        if command == ("decision", "new"):
            path = new_decision(repo_root, arg, owners=_split(options, "owners"),
                                builds_on=_split(options, "builds-on"),
                                supersedes=options.get("supersedes"))
            print(_rel(path, repo_root))
        elif command == ("decision", "ratify"):
            for path in ratify(repo_root, arg):
                print(_rel(path, repo_root))
        elif command == ("decision", "record-commit"):
            print(record_commit(repo_root, arg, commit=options.get("commit")))
        elif command == ("component", "new"):
            path = new_component(repo_root, arg, title=options.get("title"),
                                 owners=_split(options, "owners"),
                                 depends_on=_split(options, "depends-on"),
                                 realizes=_split(options, "realizes"),
                                 sealed=bool(options.get("sealed", False)))
            print(_rel(path, repo_root) + "/")
        elif command == ("kind", "new"):
            definition, component_dir, decision = new_kind(
                repo_root, arg, title=options.get("title"),
                owners=_split(options, "owners"), realizes=_split(options, "realizes"))
            print(_rel(definition, repo_root))
            print(_rel(component_dir, repo_root) + "/")
            print(_rel(decision, repo_root))
        else:
            path = new_capability(repo_root, arg, title=options.get("title"),
                                  owners=_split(options, "owners"))
            print(_rel(path, repo_root))
            print(f"id: P-{arg.upper()}")
    except (ValueError, FileExistsError, LookupError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0
