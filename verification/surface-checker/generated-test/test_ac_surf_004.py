# hotdocs-criterion: sha256:ddc31b5e0966f4da9e4ce318b66561c6765d94674bb5d4eedd78067ac36a89ee
import sys
from pathlib import Path

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def component_md(component_id, depends_on):
    return (
        "---\n"
        + "id: " + component_id + "\n"
        + "title: " + component_id + "\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "depends_on: [" + ", ".join(depends_on) + "]\n"
        + "---\n"
        + "\n"
        + "# " + component_id + "\n"
    )


def build_repo(repo_root):
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

    write(
        repo_root / "specs" / "components" / "widget" / "component.md",
        component_md("comp-widget", ["comp-zed", "comp-alpha"]),
    )
    write(
        repo_root / "specs" / "components" / "widget" / "interface" / "library.md",
        "# Library\n"
        "\n"
        "Implements: `specs/architecture/cli-conventions.md`\n",
    )

    for slug in ("zed", "alpha"):
        write(
            repo_root / "specs" / "components" / slug / "component.md",
            component_md("comp-" + slug, []),
        )
        write(
            repo_root / "specs" / "components" / slug / "interface" / "library.md",
            "# Library\n",
        )
        write(
            repo_root / "gen" / slug / (slug + ".py"),
            "\"\"\"A module defining nothing.\"\"\"\n",
        )

    write(
        repo_root / "gen" / "widget" / "widget.py",
        "try:\n"
        "    import zed\n"
        "    import alpha\n"
        "except ImportError:\n"
        "    pass\n"
        "\n"
        "\n"
        "def use():\n"
        "    first = zed.b\n"
        "    second = zed.a\n"
        "    third = alpha.c\n"
        "    return first, second, third\n"
        "\n"
        "\n"
        "def main(argv):\n"
        "    return 0\n",
    )


def test_ac_surf_004_findings_in_check_order(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)

    report = surface_checker.check_surface("comp-widget", repo_root)

    findings = field(report, "findings")
    got = [(field(f, "kind"), field(f, "message")) for f in findings]
    assert got == [
        ("dependency_name", "zed has no a, which the candidate uses"),
        ("dependency_name", "zed has no b, which the candidate uses"),
        ("dependency_name", "alpha has no c, which the candidate uses"),
        ("cli_usage", "exit 0, no usage error line"),
    ]

    as_dict = report.to_dict()
    assert as_dict["ok"] is False