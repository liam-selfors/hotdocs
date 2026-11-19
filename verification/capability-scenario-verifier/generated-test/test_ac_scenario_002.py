# hotdocs-criterion: sha256:7d3243aae3585ae96aaf5bfd9b7a94a98a31a16febda3cabba405b9f947c8a8f
import capability_scenario_verifier

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def keys_of(value):
    if isinstance(value, dict):
        return set(value.keys())
    return set(vars(value).keys())


def get_entry(report, key):
    return report[key] if isinstance(report, dict) else getattr(report, key)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_component(repo_root, slug, realizes=None, sealed=False, source_path=None):
    lines = ["---"]
    lines.append("id: comp-" + slug)
    lines.append("title: " + slug.capitalize() + " component")
    lines.append("status: draft")
    lines.append("owners: [pipeline-team]")
    if realizes is not None:
        lines.append("realizes: [" + ", ".join(realizes) + "]")
    if sealed:
        lines.append("sealed: true")
        lines.append("source_path: " + source_path)
    else:
        lines.append("sealed: false")
    lines.append("---")
    lines.append("")
    lines.append("# " + slug)
    lines.append("")
    lines.append("A fixture component.")
    lines.append("")
    write(repo_root / "specs" / "components" / slug / "component.md", "\n".join(lines))


def write_capability(repo_root, name, cap_id, scenario_suffix, kind):
    scenario_id = "CS-" + scenario_suffix + "-001"
    text = (
        "---\n"
        + "id: " + cap_id + "\n"
        + "title: " + name + " capability\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# " + name + "\n"
        + "\n"
        + "### " + scenario_id + "\n"
        + "\n"
        + "Covers: " + cap_id + "\n"
        + "Kind: " + kind + "\n"
        + "\n"
        + "```gherkin\n"
        + "Given a system\n"
        + "When it runs\n"
        + "Then it works\n"
        + "```\n"
    )
    write(repo_root / "specs" / "product" / (name + ".md"), text)


def write_fake_dependencies(repo_root):
    author_src = (
        "def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):\n"
        "    cid = bundle['criterion_id']\n"
        "    name = 'test_' + cid.lower().replace('-', '_') + '.py'\n"
        "    return {\n"
        "        'component_id': bundle.get('component_id', ''),\n"
        "        'criterion_id': cid,\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {\n"
        "            'path': 'verification/capabilities/fake/generated-test/' + name,\n"
        "            'content': 'def test_x():\\n    assert True\\n',\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    write(repo_root / "gen" / "test-author" / "test_author.py", author_src)
    endpoint_src = (
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\n"
        "        'text': 'pass',\n"
        "        'model': model,\n"
        "        'backend': 'fake',\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )
    write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


def make_test_author(content_by_capability):
    def test_author(bundle):
        cap_id = bundle["capability_id"]
        scenario_id = bundle["scenario_id"]
        name = "test_" + scenario_id.lower().replace("-", "_") + ".py"
        return {
            "component_id": "",
            "criterion_id": scenario_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/capabilities/" + cap_id + "/generated-test/" + name,
                "content": content_by_capability.get(
                    cap_id, "def test_x():\n    assert True\n"
                ),
            },
            "model_call_error": None,
        }

    return test_author


def judge(bundle):
    return {"result": "pass", "rationale": "ok"}


def test_report_keys_only_capabilities_realized_in_blast_radius(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_fake_dependencies(repo_root)

    write_component(repo_root, "foo", realizes=["P-ZERO-EDIT"], sealed=False)
    write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")
    write_component(repo_root, "bar", realizes=None, sealed=False)
    write(repo_root / "gen" / "bar" / "bar.py", "VALUE = 2\n")

    write_capability(repo_root, "zero-edit", "P-ZERO-EDIT", "ZERO-EDIT", "generated-test")
    write_capability(repo_root, "unrelated", "P-UNRELATED", "UNRELATED", "generated-test")

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo", "comp-bar"],
        repo_root,
        judge=judge,
        test_author=make_test_author({}),
    )

    assert keys_of(report) == {"P-ZERO-EDIT"}


def test_sealed_component_code_directory_is_its_source_path(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_fake_dependencies(repo_root)

    write_component(
        repo_root, "baz", realizes=["P-SEALED"], sealed=True, source_path="pipeline/baz/"
    )
    write(repo_root / "pipeline" / "baz" / "baz.py", "MARKER = " + repr("sealed-baz") + "\n")
    assert not (repo_root / "gen" / "baz").exists()

    write_capability(repo_root, "sealed", "P-SEALED", "SEALED", "generated-test")

    sealed_test_content = (
        "import baz\n"
        "\n"
        "\n"
        "def test_sealed_import():\n"
        "    assert baz.MARKER == " + repr("sealed-baz") + "\n"
    )

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-baz"],
        repo_root,
        judge=judge,
        test_author=make_test_author({"P-SEALED": sealed_test_content}),
    )

    assert keys_of(report) == {"P-SEALED"}
    entry = get_entry(report, "P-SEALED")
    scenarios = field(entry, "scenarios")
    assert len(scenarios) == 1
    assert field(scenarios[0], "id") == "CS-SEALED-001"
    assert field(scenarios[0], "result") == "pass"
    assert field(entry, "overall") == "pass"