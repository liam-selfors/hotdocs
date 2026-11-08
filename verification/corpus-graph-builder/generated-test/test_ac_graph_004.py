import pytest

import corpus_graph_builder


def get_field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_component(repo_root, slug, *, depends_on=(), realizes=(), uses_var=(), sealed=False):
    depends_on_str = "[" + ", ".join(depends_on) + "]"
    realizes_str = "[" + ", ".join(realizes) + "]"
    uses_var_str = "[" + ", ".join(uses_var) + "]"
    sealed_str = "true" if sealed else "false"
    content = (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: Component {slug}\n"
        "status: draft\n"
        "owners: [alice]\n"
        f"depends_on: {depends_on_str}\n"
        f"realizes: {realizes_str}\n"
        f"uses_var: {uses_var_str}\n"
        f"sealed: {sealed_str}\n"
        "---\n"
        "\n"
        f"# Component {slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Test component {slug}.\n"
    )
    write_file(repo_root / "specs" / "components" / slug / "component.md", content)


def make_capability(repo_root, name, cap_id):
    content = (
        "---\n"
        f"id: {cap_id}\n"
        f"title: Capability {name}\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        f"# Capability {name}\n"
    )
    write_file(repo_root / "specs" / "product" / f"{name}.md", content)


def test_orphan_rates_with_capabilities_components_and_dependency(tmp_path):
    repo_root = tmp_path / "repo1"
    make_capability(repo_root, "one", "P-ONE")
    make_capability(repo_root, "two", "P-TWO")
    make_component(repo_root, "a", realizes=["P-ONE"], sealed=False)
    make_component(repo_root, "b", sealed=False)
    make_component(repo_root, "c", depends_on=["comp-b"], sealed=False)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    aggregates = get_field(graph, "aggregates")
    orphan_capability_rate = get_field(aggregates, "orphan_capability_rate")
    orphan_component_rate = get_field(aggregates, "orphan_component_rate")

    assert orphan_capability_rate == pytest.approx(0.5)
    assert orphan_component_rate == pytest.approx(1 / 3)


def test_orphan_capability_rate_zero_with_no_capabilities(tmp_path):
    repo_root = tmp_path / "repo2"
    make_component(repo_root, "solo", sealed=True)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    aggregates = get_field(graph, "aggregates")
    orphan_capability_rate = get_field(aggregates, "orphan_capability_rate")

    assert orphan_capability_rate == pytest.approx(0.0)