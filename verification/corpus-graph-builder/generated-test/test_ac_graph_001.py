import tempfile
from pathlib import Path

import pytest

import corpus_graph_builder


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _build_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "product" / "p-one.md",
        "---\n"
        "id: P-ONE\n"
        "title: Capability One\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n\n"
        "Capability one body.\n",
    )
    _write(
        repo_root / "specs" / "product" / "p-two.md",
        "---\n"
        "id: P-TWO\n"
        "title: Capability Two\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n\n"
        "Capability two body.\n",
    )

    for slug in ("a", "b", "c"):
        _write(
            repo_root / "specs" / "components" / slug / "component.md",
            "---\n"
            f"id: comp-{slug}\n"
            f"title: Component {slug.upper()}\n"
            "status: draft\n"
            "owners: [alice]\n"
            "depends_on: []\n"
            "realizes: []\n"
            "uses_var: []\n"
            "sealed: true\n"
            f"source_path: fake/{slug}/\n"
            "---\n\n"
            f"## Purpose\n\nComponent {slug} purpose text.\n",
        )

    _write(
        repo_root / "specs" / "components" / "a" / "requirements" / "R-A-001.md",
        "# R-A-001\n\n"
        "**R-A-001** \u2014 A placeholder requirement for component a.\n",
    )
    _write(
        repo_root / "specs" / "components" / "a" / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n\n"
        "Covers: R-A-001\n\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it happens\n"
        "Then it works\n"
        "```\n",
    )

    _write(
        repo_root / "specs" / "vars" / "one.md",
        "---\n"
        "id: VAR-ONE\n"
        "title: Var One\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n\n"
        "Var one body.\n",
    )

    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Decision One\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n\n"
        "Decision one body.\n",
    )


def test_build_corpus_graph_has_exactly_the_expected_nodes_and_types():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _build_corpus(repo_root)

        graph = corpus_graph_builder.build_corpus_graph(repo_root)

        nodes = _get(graph, "nodes")
        assert nodes is not None

        assert set(nodes.keys()) == {
            "P-ONE",
            "P-TWO",
            "comp-a",
            "comp-b",
            "comp-c",
            "VAR-ONE",
        }

        expected_types = {
            "P-ONE": "capability",
            "P-TWO": "capability",
            "comp-a": "component",
            "comp-b": "component",
            "comp-c": "component",
            "VAR-ONE": "var",
        }
        for node_id, expected_type in expected_types.items():
            node = nodes[node_id]
            assert _get(node, "type") == expected_type