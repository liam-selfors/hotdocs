# hotdocs-criterion: sha256:e9b7fe009f3fb8b79ae41f4f84031ba11cd96ebf053958662696b7e24f9c54d3
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

FAKE_ADAPTER = (
    "KIND = \"fake\"\n"
    "\n"
    "\n"
    "def surface(asset_file):\n"
    "    return {\"names\": [\"a\", \"b\"]}\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None}\n"
)


def build_repo(repo_root, stated_lines):
    repo_root = Path(repo_root)
    write(
        repo_root / "specs" / "components" / "widget" / "component.md",
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
    write(
        repo_root / "specs" / "components" / "widget" / "interface" / "library.md",
        "# Library\n",
    )
    write(
        repo_root / "specs" / "components" / "widget" / "interface" / "assets" / "app.js.md",
        "# app.js\n"
        "\n"
        "```\n"
        + "".join(line + "\n" for line in stated_lines)
        + "```\n",
    )
    write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", "# Fake kind\n")
    write(repo_root / "gen" / "kind-python" / "kind_python.py", PYTHON_ADAPTER)
    write(repo_root / "gen" / "kind-fake" / "kind_fake.py", FAKE_ADAPTER)
    write(repo_root / "gen" / "widget" / "widget.py", "X = 1\n")
    write(repo_root / "gen" / "widget" / "static" / "app.js", "export function a(x) { return x; }\n")
    return repo_root


def test_missing_stated_names_give_sorted_distinct_findings(tmp_path):
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
    findings = field(report, "findings")
    simplified = [
        {"kind": field(f, "kind"), "message": field(f, "message")} for f in findings
    ]
    assert simplified == [
        {"kind": "asset_name_missing", "message": "static/app.js has no c, which its interface states"},
        {"kind": "asset_name_missing", "message": "static/app.js has no zeta, which its interface states"},
    ]
    assert field(report, "ok") is False


def test_all_stated_names_provided_gives_ok(tmp_path):
    repo_root = build_repo(tmp_path / "repo", ["export function a(x)"])
    report = surface_checker.check_surface("comp-widget", repo_root)
    assert list(field(report, "findings")) == []
    assert field(report, "ok") is True