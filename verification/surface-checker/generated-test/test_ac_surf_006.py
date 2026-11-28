# hotdocs-criterion: sha256:198b0217f54c0e58fad6846be944c6e353ebe159e3d5b5c297f532918a5b8fed
import sys
from pathlib import Path

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


PYTHON_ADAPTER = (
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
    "            \"interpreter\": sys.executable}\n"
)


def adapter_source(kind, surface_body, ok, reason):
    return (
        "KIND = " + repr(kind) + "\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    " + surface_body + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": " + repr(ok) + ", \"reason\": " + repr(reason)
        + ", \"versions\": {}, \"lockfile_sha256\": None, \"interpreter\": None}\n"
    )


def plant_kind(repo_root, kind, source):
    write(repo_root / "specs" / "architecture" / ("asset-kind-" + kind + ".md"),
          "# Asset kind " + kind + "\n")
    module = "kind_" + kind.replace("-", "_")
    write(repo_root / "gen" / ("kind-" + kind) / (module + ".py"), source)


def build_repo(repo_root):
    write(repo_root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)

    plant_kind(repo_root, "fake",
               adapter_source("fake", "return {\"names\": [\"a\", \"b\"]}", True, ""))
    plant_kind(repo_root, "fakebad",
               adapter_source("fakebad", "raise RuntimeError(\"boom\")", True, ""))
    plant_kind(repo_root, "fakeoff",
               adapter_source("fakeoff", "return {\"names\": [\"a\", \"b\"]}",
                              False, "fakeoff needs fakeprog >= 2"))

    comp = repo_root / "specs" / "components" / "widget"
    write(comp / "component.md",
          "---\n"
          "id: comp-widget\n"
          "title: Widget\n"
          "status: draft\n"
          "owners: [pipeline-team]\n"
          "depends_on: []\n"
          "assets: [nokind_q:static/x.js, fakeoff:static/off.js, fake:static/gone.js, "
          "fake:static/noiface.js, fakebad:static/bad.js, fake:static/app.js]\n"
          "---\n"
          "\n"
          "# Widget\n")
    write(comp / "interface" / "library.md", "# Library\n")

    code = repo_root / "gen" / "widget"
    write(code / "widget.py", "X = 1\n")
    for name in ["x.js", "off.js", "noiface.js", "bad.js", "app.js"]:
        write(code / "static" / name, "// asset " + name + "\n")

    fence = "```"
    for name in ["x.js", "off.js", "gone.js", "bad.js", "app.js"]:
        write(comp / "interface" / "assets" / (name + ".md"),
              "# " + name + "\n"
              "\n"
              + fence + "\n"
              "export function zz()\n"
              + fence + "\n")


def test_ac_surf_006_asset_findings_in_declaration_order(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)

    report = surface_checker.check_surface("comp-widget", repo_root)

    assert field(report, "ok") is False
    findings = field(report, "findings")
    got = [(field(f, "kind"), field(f, "message")) for f in findings]
    assert got == [
        ("asset_error", "unknown asset kind: nokind_q"),
        ("asset_error", "static/off.js: fakeoff needs fakeprog >= 2"),
        ("asset_error", "static/gone.js: no such asset file"),
        ("asset_error",
         "static/noiface.js: no interface file interface/assets/noiface.js.md"),
        ("asset_error", "static/bad.js: surface failed: RuntimeError: boom"),
        ("asset_name_missing", "static/app.js has no zz, which its interface states"),
    ]