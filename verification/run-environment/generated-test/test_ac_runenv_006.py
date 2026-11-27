# hotdocs-criterion: sha256:28510410ba8f4317ee7e7fffe253852ce196b9483444da4f65dc8bcbec561354
import hashlib
import importlib.util
import sys
from pathlib import Path

import run_environment


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha256_of(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _fake_driver_source(repo_root):
    log_path = str(repo_root / "closed.log")
    return (
        "NAME = " + repr("fake") + "\n"
        "FIXTURE = " + repr("fake_session") + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return {" + repr("test_author") + ": " + repr("Fake driver text.") + "}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\n"
        "        " + repr("ok") + ": True,\n"
        "        " + repr("reason") + ": " + repr("") + ",\n"
        "        " + repr("versions") + ": {" + repr("fakedrv") + ": " + repr("2.0") + "},\n"
        "        " + repr("lockfile_sha256") + ": None,\n"
        "    }\n"
        "\n"
        "\n"
        "class _Session:\n"
        "    def __init__(self, repo_root):\n"
        "        self.value = " + repr("open") + "\n"
        "        self._repo_root = repo_root\n"
        "\n"
        "    def close(self):\n"
        "        with open(" + repr(log_path) + ", " + repr("a") + ") as fh:\n"
        "            fh.write(" + repr("closed\n") + ")\n"
        "\n"
        "\n"
        "def open_session(repo_root, work_dir):\n"
        "    return _Session(repo_root)\n"
    )


def _build_corpus(repo_root):
    driver_dir = repo_root / "gen" / "driver-fake"
    driver_dir.mkdir(parents=True)
    (driver_dir / "driver_fake.py").write_text(_fake_driver_source(repo_root))

    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True)
    (product_dir / "x.md").write_text(
        "---\n"
        "id: P-X\n"
        "title: X\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "drivers: [fake]\n"
        "---\n"
        "\n"
        "# X\n"
    )


def _expected_python_versions(repo_root):
    adapter = Path(run_environment.__file__).parents[1] / "kind-python" / "kind_python.py"
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        module = load_module(adapter, "ac_runenv_006_kind_python")
    finally:
        sys.dont_write_bytecode = previous
    report = module.provision(repo_root)
    return report["versions"], adapter


def test_prepare_capability_with_declared_driver(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    env = run_environment.prepare_capability("P-X", repo_root)
    try:
        assert field(env, "ok") is True

        assets = list(field(env, "assets"))
        assert len(assets) == 1
        python_entry = assets[0]
        assert field(python_entry, "kind") == "python"
        assert field(python_entry, "path") == "."
        expected_versions, adapter = _expected_python_versions(repo_root)
        assert dict(field(python_entry, "versions")) == dict(expected_versions)
        assert field(python_entry, "adapter_sha256") == sha256_of(adapter)

        drivers = list(field(env, "drivers"))
        assert len(drivers) == 1
        driver = drivers[0]
        assert field(driver, "name") == "fake"
        assert dict(field(driver, "versions")) == {"fakedrv": "2.0"}
        assert field(driver, "adapter_sha256") == sha256_of(
            repo_root / "gen" / "driver-fake" / "driver_fake.py"
        )
        assert field(driver, "definition_sha256") is None
        assert field(driver, "lockfile_sha256") is None
    finally:
        env.close()


def test_prepare_capability_without_product_file_has_no_drivers(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    env = run_environment.prepare_capability("P-Y", repo_root)
    try:
        assert field(env, "ok") is True
        assert list(field(env, "drivers")) == []
        assets = list(field(env, "assets"))
        assert len(assets) == 1
        assert field(assets[0], "kind") == "python"
    finally:
        env.close()