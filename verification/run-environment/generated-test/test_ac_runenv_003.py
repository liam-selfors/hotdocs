# hotdocs-criterion: sha256:eb0f47b224386f969e87fcdcd1b4611297f879ecc5407ebc4a49dbeda3496bf0
import hashlib
from pathlib import Path

import pytest

import run_environment


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_component(repo_root, extra_lines):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
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
        text = text + line + "\n"
    text = text + "---\n\n# Foo\n"
    (comp_dir / "component.md").write_text(text)


def driver_source(ok):
    if ok:
        report = {
            "ok": True,
            "reason": "",
            "versions": {"fakedrv": "2.0"},
            "lockfile_sha256": None,
        }
    else:
        report = {
            "ok": False,
            "reason": "fake needs fakedrv >= 3",
            "versions": {},
            "lockfile_sha256": None,
        }
    return (
        "from pathlib import Path\n"
        "NAME = " + repr("fake") + "\n"
        "FIXTURE = " + repr("fake_session") + "\n"
        "def guidance():\n"
        "    return " + repr({"test_author": "Fake driver text."}) + "\n"
        "def provision(repo_root):\n"
        "    return " + repr(report) + "\n"
        "class _Session:\n"
        "    def __init__(self, repo_root):\n"
        "        self.value = " + repr("open") + "\n"
        "        self._log = Path(repo_root) / " + repr("closed.log") + "\n"
        "    def close(self):\n"
        "        with open(self._log, " + repr("a") + ") as f:\n"
        "            f.write(" + repr("closed\n") + ")\n"
        "def open_session(repo_root, work_dir):\n"
        "    return _Session(repo_root)\n"
    )


def kind_source(ok):
    if ok:
        report = {
            "ok": True,
            "reason": "",
            "versions": {"fake": "1.0"},
            "lockfile_sha256": None,
            "interpreter": None,
        }
    else:
        report = {
            "ok": False,
            "reason": "fake needs fakeprog >= 2",
            "versions": {},
            "lockfile_sha256": None,
            "interpreter": None,
        }
    return (
        "from pathlib import Path\n"
        "KIND = " + repr("fake") + "\n"
        "class AssetError(Exception):\n"
        "    pass\n"
        "def layout_errors(asset_file):\n"
        "    return []\n"
        "def surface(asset_file):\n"
        "    return " + repr({"names": []}) + "\n"
        "def provision(repo_root):\n"
        "    return " + repr(report) + "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "Fake generator text.", "test_author": "Fake kind text."}) + "\n"
        "def asset_runner(asset_file):\n"
        "    def run(entry, args):\n"
        "        for line in Path(asset_file).read_text().splitlines():\n"
        "            if line.startswith(entry + " + repr("=") + "):\n"
        "                return int(line[len(entry) + 1:])\n"
        "        raise AssetError(" + repr("no entry: ") + " + entry)\n"
        "    return run\n"
        "def strength_sites(asset_file):\n"
        "    return []\n"
        "def apply_site(asset_file, site):\n"
        "    return None\n"
    )


def plant_driver(repo_root, ok):
    d = repo_root / "gen" / "driver-fake"
    d.mkdir(parents=True, exist_ok=True)
    path = d / "driver_fake.py"
    path.write_text(driver_source(ok))
    return path


def plant_kind(repo_root, ok):
    arch = repo_root / "specs" / "architecture"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "asset-kind-fake.md").write_text("# Fake kind\n\nAny text.\n")
    d = repo_root / "gen" / "kind-fake"
    d.mkdir(parents=True, exist_ok=True)
    (d / "kind_fake.py").write_text(kind_source(ok))
    data = repo_root / "gen" / "foo" / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "table.txt").write_text("a=1\nb=2\n")


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_provisioned_fake_driver_is_recorded(tmp_path):
    repo_root = tmp_path
    write_component(repo_root, ["drivers: [fake]"])
    adapter = plant_driver(repo_root, ok=True)

    env = run_environment.prepare("comp-foo", repo_root)
    try:
        assert field(env, "ok") is True
        assert field(env, "drivers") == [
            {
                "name": "fake",
                "definition_sha256": None,
                "adapter_sha256": sha(adapter),
                "versions": {"fakedrv": "2.0"},
                "lockfile_sha256": None,
            }
        ]
    finally:
        env.close()


def setup_unprovisioned_driver(repo_root):
    write_component(repo_root, ["drivers: [fake]"])
    plant_driver(repo_root, ok=False)


def setup_unknown_driver(repo_root):
    write_component(repo_root, ["drivers: [nodrv]"])


def setup_unprovisioned_kind(repo_root):
    write_component(repo_root, ["assets: [fake:data/table.txt]", "drivers: [fake]"])
    plant_kind(repo_root, ok=False)
    plant_driver(repo_root, ok=True)


@pytest.mark.parametrize(
    "setup, expected",
    [
        (setup_unprovisioned_driver, "fake needs fakedrv >= 3"),
        (setup_unknown_driver, "unknown test driver: nodrv"),
        (setup_unprovisioned_kind, "fake needs fakeprog >= 2"),
    ],
    ids=["unprovisioned-driver", "unknown-driver", "unprovisioned-kind"],
)
def test_failed_provisioning_ends_prepare(tmp_path, setup, expected):
    repo_root = tmp_path
    setup(repo_root)

    env = run_environment.prepare("comp-foo", repo_root)
    try:
        assert field(env, "ok") is False
        assert field(env, "failure_message") == expected
    finally:
        env.close()