# hotdocs-criterion: sha256:388f1a87ce641c0af330c0f01e07fc1da6451eb5b55379eb3ccbe9930c01ae86
"""AC-SURF-002: dependency names are read from the syntax tree and checked
against the dependency's real module."""

from pathlib import Path

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PYTHON_ADAPTER = "\n".join([
    "import sys",
    "from pathlib import Path",
    "",
    "",
    "def provision(repo_root):",
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,",
    "            \"interpreter\": sys.executable}",
    "",
])

BAR_ONE = "\n".join([
    "def fetch_one(x):",
    "    return {\"id\": x}",
    "",
])

BAR_BOTH = "\n".join([
    "def fetch_one(x):",
    "    return {\"id\": x}",
    "",
    "",
    "def fetch_all():",
    "    return []",
    "",
])

WIDGET_LOAD_DEP = "\n".join([
    "import importlib.util",
    "from pathlib import Path",
    "",
    "",
    "def _load_dep(repo_root, slug):",
    "    path = Path(repo_root) / \"gen\" / slug / (slug + \".py\")",
    "    spec = importlib.util.spec_from_file_location(slug, str(path))",
    "    module = importlib.util.module_from_spec(spec)",
    "    spec.loader.exec_module(module)",
    "    return module",
    "",
    "",
    "def run(repo_root):",
    "    bar_mod = _load_dep(repo_root, 'bar')",
    "    one = bar_mod.fetch_one(1)",
    "    every = bar_mod.fetch_all()",
    "    return one, every, bar_mod.__name__",
    "",
])


def widget_direct(last_line):
    return "\n".join([
        "\"\"\"Widget module: uses bar.gone_a() somewhere.\"\"\"",
        "import importlib.util",
        "",
        "# bar.gone_b is not called",
        "",
        "",
        "def load(directory):",
        "    spec = importlib.util.spec_from_file_location('bar', str(directory / 'bar.py'))",
        "    bar = importlib.util.module_from_spec(spec)",
        "    spec.loader.exec_module(bar)",
        "    " + last_line,
        "",
    ])


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_repo(root, widget_src, bar_src, bar_sealed=False):
    write(root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)

    write(
        root / "specs" / "components" / "widget" / "component.md",
        "\n".join([
            "---",
            "id: comp-widget",
            "title: Widget",
            "status: draft",
            "owners: [test-team]",
            "depends_on: [comp-bar]",
            "---",
            "",
            "# Widget",
            "",
        ]),
    )
    write(root / "specs" / "components" / "widget" / "interface" / "library.md", "# Library\n")
    write(root / "gen" / "widget" / "widget.py", widget_src)

    bar_lines = [
        "---",
        "id: comp-bar",
        "title: Bar",
        "status: draft",
        "owners: [test-team]",
        "depends_on: []",
    ]
    if bar_sealed:
        bar_lines += ["sealed: true", "source_path: legacy/bar/"]
    bar_lines += ["---", "", "# Bar", ""]
    write(root / "specs" / "components" / "bar" / "component.md", "\n".join(bar_lines))
    write(
        root / "specs" / "components" / "bar" / "interface" / "library.md",
        "\n".join([
            "# Library",
            "",
            "```",
            "fetch_one(x)",
            "fetch_all()",
            "```",
            "",
        ]),
    )
    if bar_sealed:
        write(root / "legacy" / "bar" / "bar.py", bar_src)
    else:
        write(root / "gen" / "bar" / "bar.py", bar_src)


def findings_of(report):
    return [
        (field(f, "kind"), field(f, "message")) for f in field(report, "findings")
    ]


EXPECTED = [("dependency_name", "bar has no fetch_all, which the candidate uses")]


def test_alias_from_load_dep_call_finds_missing_name(tmp_path):
    root = tmp_path / "repo"
    build_repo(root, WIDGET_LOAD_DEP, BAR_ONE)
    report = surface_checker.check_surface("comp-widget", root)
    assert findings_of(report) == EXPECTED
    assert field(report, "ok") is False


def test_names_in_strings_comments_docstrings_are_ignored(tmp_path):
    root = tmp_path / "repo"
    build_repo(root, widget_direct("return bar.fetch_one(1)"), BAR_ONE)
    report = surface_checker.check_surface("comp-widget", root)
    assert field(report, "ok") is True
    assert findings_of(report) == []


def test_module_name_use_of_missing_name_is_found(tmp_path):
    root = tmp_path / "repo"
    build_repo(root, widget_direct("return bar.fetch_all()"), BAR_ONE)
    report = surface_checker.check_surface("comp-widget", root)
    assert findings_of(report) == EXPECTED
    assert field(report, "ok") is False


def test_sealed_dependency_checked_at_source_path(tmp_path):
    root = tmp_path / "repo"
    build_repo(root, widget_direct("return bar.fetch_all()"), BAR_BOTH, bar_sealed=True)
    assert not (root / "gen" / "bar").exists()
    report = surface_checker.check_surface("comp-widget", root)
    assert findings_of(report) == []
    assert field(report, "ok") is True