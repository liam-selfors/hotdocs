# hotdocs-criterion: sha256:7eaab2107668378c498f56a62c51662994737105054272bd2acedfe038c70701
import hashlib
import importlib.util
import sys
from pathlib import Path

import run_environment


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_component(repo_root, extra_lines):
    text = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
    )
    for line in extra_lines:
        text += line + "\n"
    text += "---\n\n# Foo\n"
    write(repo_root / "specs" / "components" / "foo" / "component.md", text)


def safe_close(env):
    try:
        env.close()
    except Exception:
        pass


def test_provision_raising_reports_adapter_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_component(
        repo_root,
        ["depends_on: [comp-kind-fake]", "assets: [fake:data/table.txt]"],
    )
    write(repo_root / "gen" / "foo" / "data" / "table.txt", "a=1\nb=2\n")
    write(
        repo_root / "specs" / "architecture" / "asset-kind-fake.md",
        "# Asset kind: fake\n\nA fake kind for tests.\n",
    )
    adapter_src = (
        "from pathlib import Path\n"
        "\n"
        "KIND = " + repr("fake") + "\n"
        "\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    def run(entry, args):\n"
        "        for line in Path(asset_file).read_text().splitlines():\n"
        "            if line.startswith(entry + " + repr("=") + "):\n"
        "                return int(line[len(entry) + 1:])\n"
        "        raise KeyError(entry)\n"
        "    return run\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    raise RuntimeError(" + repr("boom") + ")\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return {" + repr("generator") + ": " + repr("g") + ", "
        + repr("test_author") + ": " + repr("t") + "}\n"
        "\n"
        "\n"
        "def layout_errors(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {" + repr("names") + ": []}\n"
        "\n"
        "\n"
        "def strength_sites(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    return None\n"
    )
    write(repo_root / "gen" / "kind-fake" / "kind_fake.py", adapter_src)

    env = run_environment.prepare("comp-foo", repo_root)
    try:
        assert field(env, "ok") is False
        assert field(env, "failure_message") == "fake adapter failed: RuntimeError: boom"
    finally:
        safe_close(env)


def test_missing_component_md_declares_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    assert not (repo_root / "specs" / "components" / "foo" / "component.md").exists()

    adapter_path = (
        Path(run_environment.__file__).parents[1] / "kind-python" / "kind_python.py"
    )
    kind_python = load_module(adapter_path, "kind_python")
    expected = kind_python.provision(repo_root)

    env = run_environment.prepare("comp-foo", repo_root)
    try:
        assert field(env, "ok") is True
        assets = list(field(env, "assets"))
        assert len(assets) == 1
        entry = assets[0]
        assert field(entry, "kind") == "python"
        assert field(entry, "path") == "."
        assert field(entry, "definition_sha256") is None
        assert field(entry, "adapter_sha256") == sha(adapter_path)
        assert field(entry, "versions") == expected["versions"]
        assert field(entry, "lockfile_sha256") == expected["lockfile_sha256"]
        assert list(field(env, "drivers")) == []
    finally:
        safe_close(env)