# hotdocs-criterion: sha256:fd738218e9ab0cceafd4d53b93bbe802fd8ee2e112a1a1d6c62389f3d429a7e6
import sys
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

FAKE_ADAPTER = (
    "KIND = " + repr("fake") + "\n"
    "\n"
    "\n"
    "def surface(asset_file):\n"
    "    return {\"names\": " + repr(["a", "b"]) + "}\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None}\n"
)


def build_repo(root, block_lines):
    root = Path(root)
    comp = root / "specs" / "components" / "widget"
    (comp / "interface" / "assets").mkdir(parents=True)
    (comp / "component.md").write_text(
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "assets: [fake:static/app.js]\n"
        "---\n"
        "\n"
        "# Widget\n"
    )
    (comp / "interface" / "library.md").write_text("# Library\n")
    (comp / "interface" / "assets" / "app.js.md").write_text(
        "# app.js\n"
        "\n"
        "```\n"
        + "".join(line + "\n" for line in block_lines)
        + "```\n"
    )

    gen_widget = root / "gen" / "widget"
    (gen_widget / "static").mkdir(parents=True)
    (gen_widget / "widget.py").write_text("X = 1\n")
    (gen_widget / "static" / "app.js").write_text("// any text\n")

    arch = root / "specs" / "architecture"
    arch.mkdir(parents=True)
    (arch / "asset-kind-fake.md").write_text("# Asset kind: fake\n")

    kind_python = root / "gen" / "kind-python"
    kind_python.mkdir(parents=True)
    (kind_python / "kind_python.py").write_text(PYTHON_ADAPTER)

    kind_fake = root / "gen" / "kind-fake"
    kind_fake.mkdir(parents=True)
    (kind_fake / "kind_fake.py").write_text(FAKE_ADAPTER)
    return root


def test_stated_names_not_provided_give_sorted_distinct_findings(tmp_path):
    repo_root = build_repo(
        tmp_path / "repo",
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
    findings = [
        {"kind": field(f, "kind"), "message": field(f, "message")}
        for f in field(report, "findings")
    ]
    assert findings == [
        {
            "kind": "asset_name_missing",
            "message": "static/app.js has no c, which its interface states",
        },
        {
            "kind": "asset_name_missing",
            "message": "static/app.js has no zeta, which its interface states",
        },
    ]


def test_all_stated_names_provided_gives_no_findings(tmp_path):
    repo_root = build_repo(tmp_path / "repo", ["export function a(x)"])

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert field(report, "ok") is True
    assert list(field(report, "findings")) == []