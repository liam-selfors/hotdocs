# hotdocs-criterion: sha256:e675cc3803ccdd58f372852f2a49baded467e8098f969c2bc6e2caf4decc4d1d
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
    "KIND = " + repr("python") + "\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("") + ", "
    + repr("versions") + ": {}, " + repr("lockfile_sha256") + ": None,\n"
    "            " + repr("interpreter") + ": sys.executable}\n"
)


def ok_provision():
    return (
        "def provision(repo_root):\n"
        "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("") + ", "
        + repr("versions") + ": {}, " + repr("lockfile_sha256") + ": None, "
        + repr("interpreter") + ": None}\n"
    )


def fake_adapter(kind):
    return (
        "KIND = " + repr(kind) + "\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {" + repr("names") + ": [" + repr("a") + ", " + repr("b") + "]}\n"
        "\n"
        "\n"
        + ok_provision()
    )


def fakebad_adapter():
    return (
        "KIND = " + repr("fakebad") + "\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    raise RuntimeError(" + repr("boom") + ")\n"
        "\n"
        "\n"
        + ok_provision()
    )


def fakeoff_adapter():
    return (
        "KIND = " + repr("fakeoff") + "\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {" + repr("names") + ": [" + repr("a") + ", " + repr("b") + "]}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {" + repr("ok") + ": False, " + repr("reason") + ": "
        + repr("fakeoff needs fakeprog >= 2") + ", "
        + repr("versions") + ": {}, " + repr("lockfile_sha256") + ": None, "
        + repr("interpreter") + ": None}\n"
    )


def build_repo(repo_root):
    repo_root = Path(repo_root)

    # Adapters
    write(repo_root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)
    write(repo_root / "gen" / "kind-fake" / "kind_fake.py", fake_adapter("fake"))
    write(repo_root / "gen" / "kind-fakebad" / "kind_fakebad.py", fakebad_adapter())
    write(repo_root / "gen" / "kind-fakeoff" / "kind_fakeoff.py", fakeoff_adapter())
    for kind in ("fake", "fakebad", "fakeoff"):
        write(
            repo_root / "specs" / "architecture" / ("asset-kind-" + kind + ".md"),
            "# Asset kind " + kind + "\n",
        )

    # Component spec
    comp = repo_root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
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
    write(comp / "interface" / "library.md", "# Library\n")
    fence = "`" * 3
    for name in ("x.js", "off.js", "gone.js", "bad.js", "app.js"):
        write(
            comp / "interface" / "assets" / (name + ".md"),
            "# " + name + "\n"
            "\n"
            + fence + "\n"
            "export function zz()\n"
            + fence + "\n",
        )

    # Code
    code = repo_root / "gen" / "widget"
    write(code / "widget.py", "X = 1\n")
    for name in ("x.js", "off.js", "noiface.js", "bad.js", "app.js"):
        write(code / "static" / name, "// " + name + "\n")


def test_ac_surf_006_asset_errors_and_missing_names(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)

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