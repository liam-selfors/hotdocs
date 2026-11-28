# hotdocs-criterion: sha256:b48601584c31faa894e375eff9724a8760cfd9e5a06ccfb9d616eec89c2a5b91
import sys
from pathlib import Path

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


FENCE = "`" * 3


def build_repo(repo_root, interface_lines):
    # The python adapter, planted so no criterion depends on the tool's own.
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

    # The planted kind fake.
    write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", "# Fake\n")
    write(
        repo_root / "gen" / "kind-fake" / "kind_fake.py",
        "KIND = " + repr("fake") + "\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {" + repr("names") + ": [" + repr("a") + ", " + repr("b") + "]}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None}\n",
    )

    # The component spec.
    comp_dir = repo_root / "specs" / "components" / "widget"
    write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
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
        + "".join(line + "\n" for line in interface_lines)
        + FENCE + "\n",
    )

    # The candidate code and asset.
    write(repo_root / "gen" / "widget" / "widget.py", "X = 1\n")
    write(repo_root / "gen" / "widget" / "static" / "app.js", "export function a(x) { return x; }\n")


def test_stated_names_not_provided_are_reported_sorted(tmp_path):
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
    findings = [
        {"kind": field(f, "kind"), "message": field(f, "message")}
        for f in field(report, "findings")
    ]
    assert findings == [
        {"kind": "asset_name_missing",
         "message": "static/app.js has no c, which its interface states"},
        {"kind": "asset_name_missing",
         "message": "static/app.js has no zeta, which its interface states"},
    ]


def test_all_stated_names_provided_is_ok(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root, ["export function a(x)"])

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert list(field(report, "findings")) == []
    assert field(report, "ok") is True