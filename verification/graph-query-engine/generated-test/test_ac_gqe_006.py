import re

import duckdb

import graph_query_engine


def _expected_word_count(repo_root, slug):
    comp_dir = repo_root / "specs" / "components" / slug
    total = 0
    for path in sorted(comp_dir.rglob("*.md")):
        content = path.read_text()
        stripped = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)
        trimmed = stripped.strip(" ")
        tokens = [t for t in re.split(r"\s+", trimmed) if t != ""]
        total += len(tokens)
    return total


def _write_component(repo_root, slug, title, purpose_words, req_words, ac_words):
    comp_dir = repo_root / "specs" / "components" / slug
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)

    purpose_text = " ".join(f"word{i}" for i in range(purpose_words))
    component_md = (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {title}\n"
        "status: ratified\n"
        "owners: [lselfors]\n"
        "sealed: true\n"
        f"source_path: tools/{slug}.py\n"
        "depends_on: []\n"
        "last_ratified_commit: deadbeef\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{purpose_text}\n"
    )
    (comp_dir / "component.md").write_text(component_md)

    req_id = f"R-{slug.upper()}-001"
    req_text = " ".join(f"reqword{i}" for i in range(req_words))
    (comp_dir / "requirements" / f"{req_id}.md").write_text(
        f"# {req_id}\n\n**{req_id}** \u2014 {req_text}\n"
    )

    ac_id = f"AC-{slug.upper()}-001"
    ac_text = " ".join(f"acword{i}" for i in range(ac_words))
    (comp_dir / "acceptance" / f"{ac_id}.md").write_text(
        f"# {ac_id}\n\nCovers: {req_id}\n\n"
        "```gherkin\n"
        f"Given {ac_text}\n"
        "When something happens\n"
        "Then something else happens\n"
        "```\n"
    )


def test_component_size_word_count_matches_reference(tmp_path):
    repo_root = tmp_path

    _write_component(repo_root, "alpha", "Alpha", purpose_words=5, req_words=7, ac_words=3)
    _write_component(repo_root, "beta", "Beta", purpose_words=10, req_words=2, ac_words=6)

    nested_dir = repo_root / "specs" / "components" / "beta" / "interface" / "data"
    nested_dir.mkdir(parents=True, exist_ok=True)
    (nested_dir / "Thing.md").write_text(
        "# Thing\n\nfieldone fieldtwo fieldthree\n"
    )

    con = duckdb.connect(":memory:")
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")

    graph_query_engine.load_views(con, repo_root)

    rows = con.execute(
        "SELECT component_id, word_count FROM component_size ORDER BY component_id"
    ).fetchall()

    actual = {component_id: word_count for component_id, word_count in rows}

    expected_alpha = _expected_word_count(repo_root, "alpha")
    expected_beta = _expected_word_count(repo_root, "beta")

    assert actual == {"alpha": expected_alpha, "beta": expected_beta}
    assert actual["alpha"] > 0
    assert actual["beta"] > 0