# hotdocs-criterion: sha256:3888aa6232055c60654ad5d5eb1036e108979b79545fc8157c6163a430822850
from pathlib import Path

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PYTHON_ADAPTER = (
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
    "            \"interpreter\": sys.executable}\n"
)

BAR_ONE = (
    "def fetch_one(x):\n"
    "    return x\n"
)

BAR_BOTH = (
    "def fetch_one(x):\n"
    "    return x\n"
    "\n"
    "\n"
    "def fetch_all():\n"
    "    return []\n"
)

WIDGET_LOADER = (
    "import importlib.util\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def _load_dep(repo_root, slug):\n"
    "    path = Path(repo_root) / \"gen\" / slug / (slug + \".py\")\n"
    "    spec = importlib.util.spec_from_file_location(slug, str(path))\n"
    "    module = importlib.util.module_from_spec(spec)\n"
    "    spec.loader.exec_module(module)\n"
    "    return module\n"
    "\n"
    "\n"
    "def run(repo_root):\n"
    "    bar_mod = _load_dep(repo_root, 'bar')\n"
    "    first = bar_mod.fetch_one(1)\n"
    "    rest = bar_mod.fetch_all()\n"
    "    return first, rest, bar_mod.__name__\n"
)


def widget_direct(last_line):
    return (
        "\"\"\"Widget module.\n"
        "\n"
        "uses bar.gone_a()\n"
        "\"\"\"\n"
        "import importlib.util\n"
        "\n"
        "# bar.gone_b is not called\n"
        "\n"
        "\n"
        "def load(directory):\n"
        "    spec = importlib.util.spec_from_file_location('bar', str(directory / 'bar.py'))\n"
        "    bar = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(bar)\n"
        "    " + last_line + "\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def component_md(cid, depends_on, extra_lines=()):
    lines = [
        "---",
        "id: " + cid,
        "title: " + cid,
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: [" + ", ".join(depends_on) + "]",
    ]
    lines.extend(extra_lines)
    lines.append("---")
    lines.append("")
    lines.append("# " + cid)
    lines.append("")
    return "\n".join(lines)


def build_repo(root, widget_source, bar_sealed=False):
    write(root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)
    write(
        root / "specs" / "components" / "widget" / "component.md",
        component_md("comp-widget", ["comp-bar"]),
    )
    write(root / "specs" / "components" / "widget" / "interface" / "library.md", "# Library\n")
    write(root / "gen" / "widget" / "widget.py", widget_source)
    if bar_sealed:
        write(
            root / "specs" / "components" / "bar" / "component.md",
            component_md("comp-bar", [], ["sealed: true", "source_path: legacy/bar/"]),
        )
        write(root / "legacy" / "bar" / "bar.py", BAR_BOTH)
    else:
        write(
            root / "specs" / "components" / "bar" / "component.md",
            component_md("comp-bar", []),
        )
        write(root / "gen" / "bar" / "bar.py", BAR_ONE)
    write(root / "specs" / "components" / "bar" / "interface" / "library.md", "# Library\n")
    return root


def findings_of(report):
    return [
        (field(f, "kind"), field(f, "message")) for f in field(report, "findings")
    ]


EXPECTED = [("dependency_name", "bar has no fetch_all, which the candidate uses")]


def test_loader_alias_missing_name(tmp_path):
    root = build_repo(tmp_path / "r1", WIDGET_LOADER)
    report = surface_checker.check_surface("comp-widget", root)
    assert findings_of(report) == EXPECTED
    assert field(report, "ok") is False


def test_docstring_and_comment_ignored_direct_alias_ok(tmp_path):
    root = build_repo(tmp_path / "r2", widget_direct("return bar.fetch_one(1)"))
    report = surface_checker.check_surface("comp-widget", root)
    assert findings_of(report) == []
    assert field(report, "ok") is True


def test_direct_alias_missing_name(tmp_path):
    root = build_repo(tmp_path / "r3", widget_direct("return bar.fetch_all()"))
    report = surface_checker.check_surface("comp-widget", root)
    assert findings_of(report) == EXPECTED
    assert field(report, "ok") is False


def test_sealed_dependency_checked_at_source_path(tmp_path):
    root = build_repo(
        tmp_path / "r4", widget_direct("return bar.fetch_all()"), bar_sealed=True
    )
    assert not (root / "gen" / "bar").exists()
    report = surface_checker.check_surface("comp-widget", root)
    assert findings_of(report) == []
    assert field(report, "ok") is True