# hotdocs-criterion: sha256:16d911175fc2324e98c5f0e7fd50002d29f7f093ef3e891ba12b17f4de404240
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
    "    return {'ok': True, 'reason': '', 'versions': {}, 'lockfile_sha256': None,\n"
    "            'interpreter': sys.executable}\n"
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
        "    return {'ok': " + repr(ok) + ", 'reason': " + repr(reason) + ",\n"
        "            'versions': {}, 'lockfile_sha256': None, 'interpreter': None}\n"
    )


def build_repo(repo_root):
    repo_root = Path(repo_root)

    # Planted python adapter, so no criterion depends on the tool's own.
    write(repo_root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)
    write(repo_root / "specs" / "architecture" / "asset-kind-python.md", "# python\n")

    # Planted kinds: fake, fakebad, fakeoff. nokind_q is not planted.
    ok_surface = "return {'names': ['a', 'b']}"
    write(
        repo_root / "gen" / "kind-fake" / "kind_fake.py",
        kind_adapter("fake", ok_surface, True, ""),
    )
    write(
        repo_root / "gen" / "kind-fakebad" / "kind_fakebad.py",
        kind_adapter("fakebad", "raise RuntimeError(" + repr("boom") + ")", True, ""),
    )
    write(
        repo_root / "gen" / "kind-fakeoff" / "kind_fakeoff.py",
        kind_adapter("fakeoff", ok_surface, False, "fakeoff needs fakeprog >= 2"),
    )
    for kind in ("fake", "fakebad", "fakeoff"):
        write(
            repo_root / "specs" / "architecture" / ("asset-kind-" + kind + ".md"),
            "# " + kind + "\n",
        )

    # Component comp-widget.
    comp_dir = repo_root / "specs" / "components" / "widget"
    write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "assets: [nokind_q:static/x.js, fakeoff:static/off.js, fake:static/gone.js, "
        "fake:static/noiface.js, fakebad:static/bad.js, fake:static/app.js]\n"
        "---\n"
        "\n"
        "# Widget\n",
    )
    write(comp_dir / "interface" / "library.md", "# Library\n")

    fence = "```"
    for name in ("x.js", "off.js", "gone.js", "bad.js", "app.js"):
        write(
            comp_dir / "interface" / "assets" / (name + ".md"),
            "# " + name + "\n"
            "\n"
            + fence + "\n"
            "export function zz()\n"
            + fence + "\n",
        )

    # Candidate code.
    code_dir = repo_root / "gen" / "widget"
    write(code_dir / "widget.py", "X = 1\n")
    for name in ("x.js", "off.js", "noiface.js", "bad.js", "app.js"):
        write(code_dir / "static" / name, "// asset " + name + "\n")

    return repo_root


def test_ac_surf_006_asset_errors_and_missing_names_in_declaration_order(tmp_path):
    repo_root = build_repo(tmp_path)
    assert not (repo_root / "gen" / "widget" / "static" / "gone.js").exists()

    report = surface_checker.check_surface("comp-widget", repo_root)

    findings = field(report, "findings")
    got = [(field(f, "kind"), field(f, "message")) for f in findings]
    expected = [
        ("asset_error", "unknown asset kind: nokind_q"),
        ("asset_error", "static/off.js: fakeoff needs fakeprog >= 2"),
        ("asset_error", "static/gone.js: no such asset file"),
        (
            "asset_error",
            "static/noiface.js: no interface file interface/assets/noiface.js.md",
        ),
        ("asset_error", "static/bad.js: surface failed: RuntimeError: boom"),
        ("asset_name_missing", "static/app.js has no zz, which its interface states"),
    ]
    assert got == expected
    assert field(report, "ok") is False