# hotdocs-criterion: sha256:c5846904953a17961659dd97b392e4283385d4287d4085780f20923c7ba208c9
import sys
from pathlib import Path

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def component_md(cid, title, depends_on, source_path):
    return (
        "---\n"
        + "id: " + cid + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "depends_on: [" + ", ".join(depends_on) + "]\n"
        + "sealed: true\n"
        + "source_path: " + source_path + "\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
    )


def plant_python_adapter(repo_root):
    src = (
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n"
    )
    write(repo_root / "gen" / "kind-python" / "kind_python.py", src)


def build_repo(repo_root):
    plant_python_adapter(repo_root)

    # Dependencies: modules defining nothing.
    for slug in ("zed", "alpha"):
        cid = "comp-" + slug
        write(
            repo_root / "specs" / "components" / slug / "component.md",
            component_md(cid, slug.capitalize(), [], "legacy/" + slug + "/"),
        )
        write(
            repo_root / "specs" / "components" / slug / "interface" / "library.md",
            "# Library\n",
        )
        write(repo_root / "legacy" / slug / (slug + ".py"), "")
        write(repo_root / "gen" / slug / (slug + ".py"), "")

    # Candidate component.
    write(
        repo_root / "specs" / "components" / "widget" / "component.md",
        component_md("comp-widget", "Widget", ["comp-zed", "comp-alpha"], "legacy/widget/"),
    )
    write(
        repo_root / "specs" / "components" / "widget" / "interface" / "library.md",
        "# Library\n"
        + "\n"
        + "Implements: `specs/architecture/cli-conventions.md`\n",
    )
    widget_src = (
        "try:\n"
        "    import zed\n"
        "except ImportError:\n"
        "    zed = None\n"
        "try:\n"
        "    import alpha\n"
        "except ImportError:\n"
        "    alpha = None\n"
        "\n"
        "\n"
        "def use():\n"
        "    return zed.b, zed.a, alpha.c\n"
        "\n"
        "\n"
        "def main(argv):\n"
        "    return 0\n"
    )
    code_dir = repo_root / "legacy" / "widget"
    write(code_dir / "widget.py", widget_src)
    return code_dir


def test_ac_surf_004_findings_in_check_order(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    code_dir = build_repo(repo_root)

    report = surface_checker.check_surface("comp-widget", repo_root, code_dir)

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