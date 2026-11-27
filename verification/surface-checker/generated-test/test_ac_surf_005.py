# hotdocs-criterion: sha256:6464e422f38d0d62a5dbf244df8edf66e1df257986b4e6f8f35ccc69a30a4f15
import sys
from pathlib import Path

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FENCE = "`" * 3


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(repo_root, block_lines):
    # The planted python adapter.
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("")
        + ", " + repr("versions") + ": {}, " + repr("lockfile_sha256") + ": None,\n"
        "            " + repr("interpreter") + ": sys.executable}\n",
    )

    # The planted fake kind: definition and adapter.
    write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", "# Fake kind\n\nAny text.\n")
    write(
        repo_root / "gen" / "kind-fake" / "kind_fake.py",
        "KIND = " + repr("fake") + "\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {" + repr("names") + ": " + repr(["a", "b"]) + "}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("")
        + ", " + repr("versions") + ": {}, " + repr("lockfile_sha256") + ": None, "
        + repr("interpreter") + ": None}\n",
    )

    # The component's spec.
    comp_dir = repo_root / "specs" / "components" / "widget"
    write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "assets: [fake:static/app.js]\n"
        "---\n"
        "\n"
        "# Widget\n",
    )
    write(comp_dir / "interface" / "library.md", "# Library\n")
    write(
        comp_dir / "interface" / "assets" / "app.js.md",
        "# app.js\n"
        "\n"
        + FENCE + "\n"
        + "".join(line + "\n" for line in block_lines)
        + FENCE + "\n",
    )

    # The candidate's code and asset.
    write(repo_root / "gen" / "widget" / "widget.py", "X = 1\n")
    write(repo_root / "gen" / "widget" / "static" / "app.js", "export function a(x) { return x; }\n")


def findings_as_pairs(report):
    return [
        {"kind": field(f, "kind"), "message": field(f, "message")}
        for f in field(report, "findings")
    ]


def test_missing_stated_names_are_reported_sorted_and_distinct(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(
        repo_root,
        [
            "export function zeta(y, z)",
            "export function a(x)",
            "export const b",
            "export function c()",
            "export function c(q)",
        ],
    )

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert field(report, "ok") is False
    assert findings_as_pairs(report) == [
        {"kind": "asset_name_missing", "message": "static/app.js has no c, which its interface states"},
        {"kind": "asset_name_missing", "message": "static/app.js has no zeta, which its interface states"},
    ]


def test_all_stated_names_provided_gives_ok(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root, ["export function a(x)"])

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert findings_as_pairs(report) == []
    assert field(report, "ok") is True