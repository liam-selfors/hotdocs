# hotdocs-criterion: sha256:2c8412f2c1fa79dcdfd555e2133cd18dbdfc6f2fa9e82ecab6b7146710a71500
import sys
from pathlib import Path

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(cid, depends_on):
    return (
        "---\n"
        + "id: " + cid + "\n"
        + "title: " + cid + "\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "depends_on: [" + ", ".join(depends_on) + "]\n"
        + "---\n"
        + "\n"
        + "# " + cid + "\n"
    )


def build_repo(repo_root):
    repo_root = Path(repo_root)

    # Planted python adapter, so no criterion depends on the tool's own.
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
        repo_root / "specs" / "architecture" / "cli-conventions.md",
        "# CLI conventions\n\nAny text.\n",
    )

    # Dependencies: zed and alpha, each with a module defining nothing.
    for slug in ("zed", "alpha"):
        write(
            repo_root / "specs" / "components" / slug / "component.md",
            component_md("comp-" + slug, []),
        )
        write(
            repo_root / "specs" / "components" / slug / "interface" / "library.md",
            "# Library\n",
        )
        write(repo_root / "gen" / slug / (slug + ".py"), "# defines nothing\n")

    # The candidate: comp-widget.
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
    write(
        repo_root / "gen" / "widget" / "widget.py",
        "try:\n"
        "    import zed\n"
        "except ImportError:\n"
        "    zed = None\n"
        "\n"
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
        "def main(argv=None):\n"
        "    return 0\n",
    )
    return repo_root


def test_ac_surf_004_findings_in_check_order(tmp_path):
    repo_root = build_repo(tmp_path / "repo")

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