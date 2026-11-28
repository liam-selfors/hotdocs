# hotdocs-criterion: sha256:2625dc5cee885c593a609d9bf0572911efa73c88c886672791eaad90f4aab3a6
import sys
from pathlib import Path

import surface_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
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


def kind_adapter(kind, surface_body, ok, reason):
    return (
        "KIND = " + repr(kind) + "\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    " + surface_body + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": " + repr(ok) + ", \"reason\": " + repr(reason) + ", "
        "\"versions\": {}, \"lockfile_sha256\": None, \"interpreter\": None}\n"
    )


def build_repo(repo_root):
    repo_root = Path(repo_root)

    # Python adapter, always planted.
    write(repo_root / "specs" / "architecture" / "asset-kind-python.md", "# python\n")
    write(repo_root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)

    good_surface = "return {\"names\": [\"a\", \"b\"]}"
    kinds = {
        "fake": kind_adapter("fake", good_surface, True, ""),
        "fakebad": kind_adapter("fakebad", "raise RuntimeError(\"boom\")", True, ""),
        "fakeoff": kind_adapter("fakeoff", good_surface, False, "fakeoff needs fakeprog >= 2"),
    }
    for kind, source in kinds.items():
        write(repo_root / "specs" / "architecture" / ("asset-kind-" + kind + ".md"), "# " + kind + "\n")
        write(repo_root / "gen" / ("kind-" + kind) / ("kind_" + kind + ".py"), source)

    comp_dir = repo_root / "specs" / "components" / "widget"
    write(
        comp_dir / "component.md",
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
        "# Widget\n",
    )
    write(comp_dir / "interface" / "library.md", "# Library\n")

    for name in ["x.js", "off.js", "gone.js", "bad.js", "app.js"]:
        write(
            comp_dir / "interface" / "assets" / (name + ".md"),
            "# " + name + "\n\n```\nexport function zz()\n```\n",
        )

    code_dir = repo_root / "gen" / "widget"
    write(code_dir / "widget.py", "X = 1\n")
    for name in ["x.js", "off.js", "noiface.js", "bad.js", "app.js"]:
        write(code_dir / "static" / name, "// " + name + "\n")

    return repo_root


def test_ac_surf_006(tmp_path):
    repo_root = build_repo(tmp_path)
    assert not (repo_root / "gen" / "widget" / "static" / "gone.js").exists()

    report = surface_checker.check_surface("comp-widget", repo_root)

    findings = field(report, "findings")
    got = [(field(f, "kind"), field(f, "message")) for f in findings]
    expected = [
        ("asset_error", "unknown asset kind: nokind_q"),
        ("asset_error", "static/off.js: fakeoff needs fakeprog >= 2"),
        ("asset_error", "static/gone.js: no such asset file"),
        ("asset_error", "static/noiface.js: no interface file interface/assets/noiface.js.md"),
        ("asset_error", "static/bad.js: surface failed: RuntimeError: boom"),
        ("asset_name_missing", "static/app.js has no zz, which its interface states"),
    ]
    assert got == expected
    assert field(report, "ok") is False