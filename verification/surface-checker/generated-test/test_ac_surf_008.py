# hotdocs-criterion: sha256:a27898d002ad4339efc9ac28686958c30889c344474cb7a30da4f9f7e877ca76
import sys
from pathlib import Path

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def component_md(cid, depends_on):
    return (
        "---\n"
        + "id: " + cid + "\n"
        + "title: " + cid + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: [" + ", ".join(depends_on) + "]\n"
        + "---\n"
        + "\n"
        + "# " + cid + "\n"
    )


def build_repo(repo_root):
    # Planted python adapter, so no reliance on the tool's own.
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # comp-widget, the candidate
    write(
        repo_root / "specs" / "components" / "widget" / "component.md",
        component_md("comp-widget", ["comp-bar", "comp-baz"]),
    )
    write(
        repo_root / "specs" / "components" / "widget" / "interface" / "library.md",
        "# Library\n",
    )
    write(
        repo_root / "gen" / "widget" / "widget.py",
        "import importlib.util\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def _load_dep(repo_root, slug):\n"
        "    path = Path(repo_root) / \"gen\" / slug / (slug + \".py\")\n"
        "    spec = importlib.util.spec_from_file_location(slug, path)\n"
        "    module = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(module)\n"
        "    return module\n"
        "\n"
        "\n"
        "def one(repo_root):\n"
        "    mod = _load_dep(repo_root, 'bar')\n"
        "    a = mod.fetch_one(1)\n"
        "    b = mod.helper()\n"
        "    return a, b\n"
        "\n"
        "\n"
        "def two(repo_root):\n"
        "    mod = _load_dep(repo_root, 'baz')\n"
        "    return mod.baz_only()\n",
    )

    # comp-bar: documents fetch_one only
    write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        component_md("comp-bar", []),
    )
    write(
        repo_root / "specs" / "components" / "bar" / "interface" / "library.md",
        "fetch_one(x) -> int\n",
    )
    write(
        repo_root / "gen" / "bar" / "bar.py",
        "def fetch_one(x):\n"
        "    return 1\n"
        "\n"
        "\n"
        "def helper():\n"
        "    return 2\n",
    )

    # comp-baz: no interface files at all
    write(
        repo_root / "specs" / "components" / "baz" / "component.md",
        component_md("comp-baz", []),
    )
    write(
        repo_root / "gen" / "baz" / "baz.py",
        "def baz_only():\n"
        "    return 3\n",
    )


def test_ac_surf_008_only_undocumented_names_of_documented_dependency(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)

    assert not (repo_root / "specs" / "components" / "baz" / "interface").exists()

    report = surface_checker.check_surface("comp-widget", repo_root)
    findings = list(field(report, "findings"))

    normalized = [
        (field(f, "kind"), field(f, "message")) for f in findings
    ]

    # No cross-attribution of names between bar and baz.
    for kind, message in normalized:
        assert not ("baz_only" in message and message.startswith("bar ")), normalized
        assert not ("fetch_one" in message and message.startswith("baz ")), normalized
        assert not ("helper" in message and message.startswith("baz ")), normalized
        if kind == "dependency_undocumented":
            assert not message.startswith("baz "), normalized

    assert normalized == [
        (
            "dependency_undocumented",
            "bar does not document helper, which the candidate uses",
        )
    ], normalized
    assert field(report, "ok") is False