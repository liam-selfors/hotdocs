import json
import textwrap

import capability_scenario_verifier


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_ac_scenario_010(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write(repo_root / "specs" / "glossary.md", "GLOSS")

    capability_text = textwrap.dedent(
        """\
        ---
        id: P-X
        title: Capability P-X
        status: draft
        owners: [alice]
        ---

        ### CS-X-001

        Covers: P-X
        Kind: generated-test

        ```gherkin
        Given a thing
        When it happens
        Then it works
        ```
        """
    )
    _write(repo_root / "specs" / "product" / "p-x.md", capability_text)

    for slug, owner_name in (("foo", "alice"), ("bar", "bob")):
        component_text = textwrap.dedent(
            """\
            ---
            id: comp-{slug}
            title: Component {slug}
            status: draft
            owners: [{owner_name}]
            realizes: [P-X]
            sealed: false
            ---
            """
        ).format(slug=slug, owner_name=owner_name)
        _write(repo_root / "specs" / "components" / slug / "component.md", component_text)
        _write(
            repo_root / "specs" / "components" / slug / "interface" / "library.md",
            "{}_IFACE".format(slug.upper()),
        )
        _write(repo_root / "gen" / slug / "{}.py".format(slug), "# placeholder\n")

    log_path = tmp_path / "author_test_calls.jsonl"

    fake_test_author_src = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    record = {\n"
        "        'bundle': bundle,\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'repo_root': str(repo_root),\n"
        "        'llm_backend': llm_backend,\n"
        "    }\n"
        "    with open(LOG_PATH, 'a') as handle:\n"
        "        handle.write(json.dumps(record) + chr(10))\n"
        "    return {\n"
        "        'model_call_error': None,\n"
        "        'file': {\n"
        "            'path': 'verification/capabilities/P-X/generated-test/test_cs_x_001.py',\n"
        "            'content': 'def test_x():' + chr(10) + '    assert True' + chr(10),\n"
        "        },\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", fake_test_author_src)

    llm_backend_sentinel = "sentinel-llm-backend-873c6bf6"

    capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=3, llm_backend=llm_backend_sentinel
    )

    assert log_path.exists()
    lines = [line for line in log_path.read_text().splitlines() if line.strip()]
    assert len(lines) == 1

    record = json.loads(lines[0])

    assert record["model"] == "m"
    assert record["seed"] == 3
    assert record["repo_root"] == str(repo_root)
    assert record["llm_backend"] == llm_backend_sentinel

    bundle = record["bundle"]
    assert bundle["component_id"] == "capabilities/P-X"
    assert bundle["criterion_id"] == "CS-X-001"
    assert bundle["covers"] == "P-X"

    criterion_text = bundle["criterion_text"]
    assert "Given a thing" in criterion_text
    assert "When it happens" in criterion_text
    assert "Then it works" in criterion_text

    assert capability_text in bundle["requirement_text"]

    assert bundle["glossary"] == "GLOSS"
    assert bundle["dependency_interfaces"] == {}
    assert bundle["module_names"] == ["bar", "foo"]

    interface_text = bundle["interface"]
    for marker in ("## comp-bar", "BAR_IFACE", "## comp-foo", "FOO_IFACE"):
        assert marker in interface_text

    bar_header = interface_text.index("## comp-bar")
    bar_iface = interface_text.index("BAR_IFACE")
    foo_header = interface_text.index("## comp-foo")
    foo_iface = interface_text.index("FOO_IFACE")
    assert bar_header < bar_iface < foo_header < foo_iface