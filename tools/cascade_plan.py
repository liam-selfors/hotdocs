"""Read-only: which components a change forces to regenerate, and in what order.

A component's `spec_bundle_hash` holds its direct dependencies' code bytes
(R-ASSEMBLE-007), so regenerating a component invalidates every direct
dependent's provenance; regenerating that dependent changes its code in
turn. The forced set is therefore the transitive closure of dependents.

    python tools/cascade_plan.py comp-generator [comp-...]
        prints the forced set in dependency order (dependencies first).
    python tools/cascade_plan.py --dependents comp-llm-endpoint
        prints only the direct dependents.
    python tools/cascade_plan.py --leaves
        prints the components no other component depends on.

Editing `specs/glossary.md` or a document named in some component's
`Implements:` line also changes bundle hashes; pass `--file <path>` to see
which components a file edit reaches directly.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMPONENTS = REPO / "specs" / "components"


def _frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return ""
    return text.split("\n---", 1)[0]


def depends_on() -> dict[str, list[str]]:
    """comp-id -> its direct `depends_on` comp-ids."""
    graph = {}
    for root in sorted(COMPONENTS.iterdir()):
        md = root / "component.md"
        if not md.is_file():
            continue
        front = _frontmatter(md)
        match = re.search(r"^depends_on:\s*\[(.*?)\]", front, re.M)
        deps = [d.strip() for d in match.group(1).split(",") if d.strip()] if match else []
        graph["comp-" + root.name] = deps
    return graph


def dependents(graph) -> dict[str, list[str]]:
    rev = {c: [] for c in graph}
    for comp, deps in graph.items():
        for dep in deps:
            rev.setdefault(dep, []).append(comp)
    return {c: sorted(v) for c, v in rev.items()}


def forced(changed, graph) -> list[str]:
    """The changed components plus every transitive dependent, in an order
    where each component comes after all of its dependencies in the set."""
    rev = dependents(graph)
    closure, todo = set(), list(changed)
    while todo:
        comp = todo.pop()
        if comp in closure:
            continue
        closure.add(comp)
        todo.extend(rev.get(comp, []))
    order, seen = [], set()

    def visit(comp):
        if comp in seen:
            return
        seen.add(comp)
        for dep in graph.get(comp, []):
            if dep in closure:
                visit(dep)
        order.append(comp)

    for comp in sorted(closure):
        visit(comp)
    return order


def _interface_text(slug: str) -> str:
    base = COMPONENTS / slug / "interface"
    return "".join(p.read_text(encoding="utf-8") for p in sorted(base.rglob("*.md"))) if base.is_dir() else ""


def files_reach(path: str) -> list[str]:
    """Components whose own bundle a file edit changes directly: the glossary
    reaches all; an `Implements:` document its implementers; a component's
    own file that component. An `interface/` file also reaches its direct
    dependents (their `dependency_interfaces`), and `interface/data/<Type>.md`
    every component with a dependency whose interface names `Type` without
    owning it (R-ASSEMBLE-013's one-level type resolution)."""
    rel = Path(path).as_posix()
    graph = depends_on()
    if rel in ("specs/glossary.md",):
        return sorted(graph)
    hit = set()
    for root in sorted(COMPONENTS.iterdir()):
        lib = root / "interface" / "library.md"
        if lib.is_file() and re.search(r"^Implements:.*`%s`" % re.escape(rel), lib.read_text(encoding="utf-8"), re.M):
            hit.add("comp-" + root.name)
        if rel.startswith(f"specs/components/{root.name}/"):
            hit.add("comp-" + root.name)
    match = re.match(r"specs/components/([^/]+)/interface/", rel)
    if match:
        owner = "comp-" + match.group(1)
        hit.update(dependents(graph).get(owner, []))
    match = re.match(r"specs/components/[^/]+/interface/data/([A-Za-z_][A-Za-z0-9_]*)\.md$", rel)
    if match:
        type_name = match.group(1)
        for comp, deps in graph.items():
            for dep in deps:
                slug = dep.removeprefix("comp-")
                if (COMPONENTS / slug / "interface" / "data" / f"{type_name}.md").is_file():
                    continue
                if re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(type_name), _interface_text(slug)):
                    hit.add(comp)
    return sorted(hit)


def main(argv) -> int:
    graph = depends_on()
    if argv[:1] == ["--leaves"]:
        rev = dependents(graph)
        print("\n".join(c for c in sorted(graph) if not rev.get(c)))
        return 0
    if argv[:1] == ["--dependents"] and len(argv) == 2:
        print("\n".join(dependents(graph).get(argv[1], [])))
        return 0
    if argv[:1] == ["--file"] and len(argv) == 2:
        direct = files_reach(argv[1])
        print("directly changed:", ", ".join(direct) or "(none)")
        print("forced, in order:")
        print("\n".join("  " + c for c in forced(direct, graph)))
        return 0
    unknown = [c for c in argv if c not in graph]
    if not argv or unknown:
        print(__doc__.strip() if not argv else f"unknown component(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    for comp in forced(argv, graph):
        print(comp)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
