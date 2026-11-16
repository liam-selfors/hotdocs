"""Spec Scaffolder: mechanical structure and frontmatter for a specbase.

Allocates decision ids, writes decision-record skeletons, ratifies them,
records the commit that landed them, and lays out new component
directories. Writes structure and frontmatter only, never normative
content, and only under ``<repo_root>/specs/``.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

__all__ = [
    "next_decision_id",
    "new_decision",
    "ratify",
    "record_commit",
    "new_component",
    "main",
]

_DECISION_FILE_RE = re.compile(r"D([1-9][0-9]*)\.md")
_DECISION_ID_RE = re.compile(r"D[1-9][0-9]*")
_SLUG_RE = re.compile(r"[a-z][a-z0-9]*(-[a-z0-9]+)*")

_PENDING = "PENDING-COMMIT"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _decisions_dir(repo_root: Path) -> Path:
    return Path(repo_root) / "specs" / "decisions"


def _write_new(path: Path, text: str) -> None:
    with open(path, "x", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _rewrite(path: Path, lines: list[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("".join(lines))


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def _frontmatter_end(lines: list[str]) -> int:
    """Index of the closing ``---`` line of the frontmatter."""
    return lines.index("---\n", 1)


def _fm_find(lines: list[str], end: int, key: str) -> tuple[int | None, str | None]:
    prefix = key + ": "
    for i in range(1, end):
        if lines[i].startswith(prefix):
            return i, lines[i][len(prefix):].rstrip("\n")
    return None, None


def _existing_decision(repo_root: Path, decision_id: str) -> Path:
    if not _DECISION_ID_RE.fullmatch(decision_id):
        raise ValueError(f"invalid decision id: {decision_id!r} (expected D<N>)")
    path = _decisions_dir(repo_root) / f"{decision_id}.md"
    if not path.is_file():
        raise LookupError(f"no decision record {decision_id}: {path}")
    return path


def _flow_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


# ---------------------------------------------------------------------------
# library
# ---------------------------------------------------------------------------


def next_decision_id(repo_root: Path) -> str:
    """Return ``D<N+1>`` for the largest ``D<N>.md`` under specs/decisions/."""
    decisions = _decisions_dir(repo_root)
    numbers = [0]
    if decisions.is_dir():
        for entry in decisions.iterdir():
            match = _DECISION_FILE_RE.fullmatch(entry.name)
            if match:
                numbers.append(int(match.group(1)))
    return f"D{max(numbers) + 1}"


def new_decision(
    repo_root: Path,
    title: str,
    owners: list[str] | None = None,
    builds_on: list[str] | None = None,
    supersedes: str | None = None,
) -> Path:
    """Write a draft decision record skeleton and return its path."""
    if not title:
        raise ValueError("title must not be empty")
    decisions = _decisions_dir(repo_root)
    refs = list(builds_on or [])
    if supersedes is not None:
        refs.append(supersedes)
    for ref in refs:
        if not (decisions / f"{ref}.md").is_file():
            raise ValueError(f"no decision record for {ref!r} under specs/decisions/")

    owners = ["unassigned"] if owners is None else owners
    decision_id = next_decision_id(repo_root)

    lines = [
        "---",
        f"id: {decision_id}",
        f"title: {title}",
        "status: draft",
        f"owners: {_flow_list(owners)}",
    ]
    if builds_on:
        lines.append(f"builds_on: {_flow_list(builds_on)}")
    if supersedes is not None:
        lines.append(f"supersedes: {supersedes}")
    lines += [
        "---",
        "",
        f"# {decision_id} \u2014 {title}",
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

    decisions.mkdir(parents=True, exist_ok=True)
    path = decisions / f"{decision_id}.md"
    _write_new(path, "".join(line + "\n" for line in lines))
    return path


def ratify(repo_root: Path, decision_id: str) -> list[Path]:
    """Ratify a draft record; deprecate any record it supersedes."""
    path = _existing_decision(repo_root, decision_id)
    lines = _read_lines(path)
    end = _frontmatter_end(lines)
    if "status: draft\n" not in lines[1:end]:
        raise LookupError(f"decision {decision_id} is already ratified")

    lines[lines.index("status: draft\n", 1, end)] = "status: ratified\n"
    lines.insert(end, f"last_ratified_commit: {_PENDING}\n")
    changes: list[tuple[Path, list[str]]] = [(path, lines)]

    _, superseded = _fm_find(lines, end, "supersedes")
    if superseded is not None:
        old_path = _decisions_dir(repo_root) / f"{superseded}.md"
        old_lines = _read_lines(old_path)
        old_end = _frontmatter_end(old_lines)
        status_idx, _ = _fm_find(old_lines, old_end, "status")
        old_lines[status_idx] = "status: deprecated\n"
        changes.append((old_path, old_lines))

    for changed_path, changed_lines in changes:
        _rewrite(changed_path, changed_lines)
    return [changed_path for changed_path, _ in changes]


def record_commit(repo_root: Path, decision_id: str, commit: str | None = None) -> str:
    """Replace ``last_ratified_commit: PENDING-COMMIT`` with the commit."""
    path = _existing_decision(repo_root, decision_id)
    lines = _read_lines(path)
    end = _frontmatter_end(lines)

    _, status = _fm_find(lines, end, "status")
    if status != "ratified":
        raise LookupError(f"decision {decision_id} is not ratified")
    commit_idx, current = _fm_find(lines, end, "last_ratified_commit")
    if current != _PENDING:
        raise LookupError(
            f"decision {decision_id} already records commit {current!r}"
        )

    if commit is None:
        result = subprocess.run(
            [
                "git",
                "log",
                "-1",
                "--format=%h",
                "--",
                f"specs/decisions/{decision_id}.md",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        commit = result.stdout.strip()
        if not commit:
            raise LookupError(f"no commit touches specs/decisions/{decision_id}.md")

    lines[commit_idx] = f"last_ratified_commit: {commit}\n"
    _rewrite(path, lines)
    return commit


def new_component(
    repo_root: Path,
    slug: str,
    title: str | None = None,
    owners: list[str] | None = None,
    depends_on: list[str] | None = None,
    realizes: list[str] | None = None,
    sealed: bool = False,
) -> Path:
    """Lay out ``specs/components/<slug>/`` and return its path."""
    if not _SLUG_RE.fullmatch(slug):
        raise ValueError(f"slug is not kebab-case: {slug!r}")
    directory = Path(repo_root) / "specs" / "components" / slug
    if directory.exists():
        raise FileExistsError(f"component directory already exists: {directory}")

    if title is None:
        title = " ".join(word.capitalize() for word in slug.split("-"))
    owners = ["unassigned"] if owners is None else owners
    depends_on = [] if depends_on is None else depends_on
    realizes = [] if realizes is None else realizes

    component_lines = [
        "---",
        f"id: comp-{slug}",
        f"title: {title}",
        "status: draft",
        f"owners: {_flow_list(owners)}",
        f"depends_on: {_flow_list(depends_on)}",
        f"realizes: {_flow_list(realizes)}",
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
        f"# {title} \u2014 Non-Functional Constraints",
        "",
        "- TODO.",
    ]

    directory.mkdir(parents=True)
    _write_new(directory / "component.md", "".join(l + "\n" for l in component_lines))
    _write_new(directory / "constraints.md", "".join(l + "\n" for l in constraints_lines))
    for sub in ("requirements", "acceptance", "interface", "interface/data"):
        subdir = directory / sub
        subdir.mkdir(parents=True)
        _write_new(subdir / ".gitkeep", "")
    return directory


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_GENERAL_USAGE = (
    "usage: hotdocs {decision new|decision ratify|decision record-commit|component new} ..."
)

_COMMANDS: dict[tuple[str, str], tuple[str, str, set[str], set[str]]] = {
    ("decision", "new"): (
        "usage: hotdocs decision new <title> [--owners=<a,b>] [--builds-on=<D1,D2>] "
        "[--supersedes=<D<N>>] [--repo-root=<dir>]",
        "<title>",
        {"owners", "builds-on", "supersedes", "repo-root"},
        set(),
    ),
    ("decision", "ratify"): (
        "usage: hotdocs decision ratify <D<N>> [--repo-root=<dir>]",
        "<D<N>>",
        {"repo-root"},
        set(),
    ),
    ("decision", "record-commit"): (
        "usage: hotdocs decision record-commit <D<N>> [--commit=<hash>] [--repo-root=<dir>]",
        "<D<N>>",
        {"commit", "repo-root"},
        set(),
    ),
    ("component", "new"): (
        "usage: hotdocs component new <slug> [--title=<title>] [--owners=<a,b>] "
        "[--depends-on=<comp-a,comp-b>] [--realizes=<P-a,P-b>] [--sealed] [--repo-root=<dir>]",
        "<slug>",
        {"title", "owners", "depends-on", "realizes", "repo-root"},
        {"sealed"},
    ),
}


def _usage_error(cause: str, usage: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(usage, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point; returns the exit code."""
    argv = sys.argv[1:] if argv is None else list(argv)
    command = tuple(argv[:2])
    if command not in _COMMANDS:
        return _usage_error(
            f"unknown or missing command: {' '.join(argv[:2])!r}", _GENERAL_USAGE
        )
    usage, positional_name, value_flags, bool_flags = _COMMANDS[command]

    opts: dict[str, object] = {}
    positionals: list[str] = []
    tokens = argv[2:]
    i = 0
    while i < len(tokens):
        token = tokens[i]
        i += 1
        if token.startswith("--"):
            name, eq, value = token[2:].partition("=")
            if name in value_flags:
                if not eq:
                    if i >= len(tokens):
                        return _usage_error(f"--{name} requires a value", usage)
                    value = tokens[i]
                    i += 1
                opts[name] = value
            elif token[2:] in bool_flags:
                opts[token[2:]] = True
            else:
                return _usage_error(f"unknown argument: {token}", usage)
        else:
            positionals.append(token)

    if len(positionals) != 1:
        cause = (
            f"missing required argument {positional_name}"
            if not positionals
            else f"unexpected argument: {positionals[1]}"
        )
        return _usage_error(cause, usage)

    root = Path(str(opts.get("repo-root", ".")))

    def as_list(key: str) -> list[str] | None:
        value = opts.get(key)
        return None if value is None else [s.strip() for s in str(value).split(",")]

    def rel(path: Path) -> str:
        return Path(path).relative_to(root).as_posix()

    try:
        if command == ("decision", "new"):
            written = new_decision(
                root,
                positionals[0],
                owners=as_list("owners"),
                builds_on=as_list("builds-on"),
                supersedes=opts.get("supersedes"),
            )
            output = [rel(written)]
        elif command == ("decision", "ratify"):
            output = [rel(p) for p in ratify(root, positionals[0])]
        elif command == ("decision", "record-commit"):
            output = [record_commit(root, positionals[0], opts.get("commit"))]
        else:
            written = new_component(
                root,
                positionals[0],
                title=opts.get("title"),
                owners=as_list("owners"),
                depends_on=as_list("depends-on"),
                realizes=as_list("realizes"),
                sealed=bool(opts.get("sealed", False)),
            )
            output = [rel(written) + "/"]
    except (ValueError, FileExistsError, LookupError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("\n".join(output))
    return 0
