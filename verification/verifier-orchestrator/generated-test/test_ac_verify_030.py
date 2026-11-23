# hotdocs-criterion: sha256:ceb47c9b6a473bec2e67f66b433a970b969b5b252c2b2e7950ec583ea97e107e
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FENCE = "`" * 3


FAKE_ADAPTER_SOURCE = (
    "from pathlib import Path\n"
    "\n"
    "KIND = 'fake'\n"
    "\n"
    "\n"
    "def layout_errors(asset_file):\n"
    "    return []\n"
    "\n"
    "\n"
    "def surface(asset_file):\n"
    "    return {'names': []}\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return {'generator': 'Fake generator text.', 'test_author': 'Fake test text.'}\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {'ok': False, 'reason': 'fake needs fakeprog >= 2', 'versions': {}, 'lockfile_sha256': None}\n"
    "\n"
    "\n"
    "def asset_runner(asset_file):\n"
    "    def run(entry, args):\n"
    "        for line in Path(asset_file).read_text().splitlines():\n"
    "            if line.startswith(entry + '='):\n"
    "                return int(line[len(entry) + 1:])\n"
    "        raise KeyError(entry)\n"
    "    return run\n"
    "\n"
    "\n"
    "def strength_sites(asset_file):\n"
    "    return [{'description': '1: a'}, {'description': '2: b'}]\n"
    "\n"
    "\n"
    "def apply_site(asset_file, site):\n"
    "    path = Path(asset_file)\n"
    "    lines = path.read_text().splitlines()\n"
    "    index = int(site['description'].split(':')[0]) - 1\n"
    "    key, value = lines[index].split('=', 1)\n"
    "    lines[index] = key + '=' + str(int(value) + 1)\n"
    "    path.write_text('\\n'.join(lines) + '\\n')\n"
)


PROBE_SOURCE = (
    "class _Report:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "        self.tests_run = 0\n"
    "        self.tests_reached = 0\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'ok': self.ok, 'findings': list(self.findings),\n"
    "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
    "\n"
    "\n"
    "GATE_VERSION = 'test-probe@1.4.0'\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
    "          interpreter=None, assets=None):\n"
    "    return _Report()\n"
)


ASSEMBLER_SOURCE = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': 'R-QUX-001',\n"
    "        'criterion_text': 'Given the table When read Then a is 1',\n"
    "        'requirement_text': 'The table asset MUST map a to 1.',\n"
    "        'interface': 'qux_table() -> None',\n"
    "        'glossary': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
)


def build_fixture(repo_root, assets_value, plant_fake):
    write(
        repo_root / "specs" / "components" / "qux" / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-QUX]\n"
        "assets: [" + assets_value + "]\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides a small lookup table.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the table.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial.\n",
    )
    write(
        repo_root / "specs" / "components" / "qux" / "requirements" / "R-QUX-001.md",
        "# R-QUX-001\n\n**R-QUX-001** — The table asset MUST map `a` to 1.\n",
    )
    write(
        repo_root / "specs" / "components" / "qux" / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n"
        "\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n"
        "\n"
        + FENCE + "gherkin\n"
        "Given the table asset data/table.txt\n"
        "When its entry a is read\n"
        "Then the value is 1\n"
        + FENCE + "\n",
    )
    write(
        repo_root / "specs" / "components" / "qux" / "interface" / "library.md",
        "# Library\n\n" + FENCE + "\nqux_table() -> None\n" + FENCE + "\n",
    )
    write(
        repo_root / "specs" / "components" / "qux" / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Qux capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A table.\n",
    )
    write(repo_root / "gen" / "qux" / "qux.py", "")
    write(repo_root / "gen" / "qux" / "data" / "table.txt", "a=1\nb=2\n")

    if plant_fake:
        sections = [
            "Layout",
            "Environment",
            "Surface",
            "Running criteria",
            "Strength check",
            "Test author guidance",
            "Generator guidance",
        ]
        body = ""
        for name in sections:
            body += "\n## " + name + "\n\nFake " + name.lower() + " text.\n"
        write(
            repo_root / "specs" / "architecture" / "asset-kind-fake.md",
            "---\n"
            "id: arch-asset-kind-fake\n"
            "title: Asset kind fake\n"
            "status: draft\n"
            "owners: [test-team]\n"
            "---\n"
            "\n"
            "# Asset kind fake\n" + body,
        )
        write(repo_root / "gen" / "kind-fake" / "kind_fake.py", FAKE_ADAPTER_SOURCE)

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_SOURCE,
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)


def make_author(log_path):
    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "ignored.py",
                "content": "# hotdocs-criterion: sha256:" + "0" * 64 + "\n"
                "def test_ok():\n    assert True\n",
            },
        }

    return author


def author_calls(log_path):
    if not log_path.exists():
        return 0
    return len([l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()])


def only_criterion(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == "AC-QUX-001"]
    assert len(matches) == 1, criteria
    return matches[0]


def test_unprovisioned_fake_kind_fails_environment(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, "fake:data/table.txt", plant_fake=True)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        "comp-qux", repo_root, test_author=make_author(log_path)
    )

    assert author_calls(log_path) == 0
    criterion = only_criterion(report)
    assert field(criterion, "result") == "fail"
    assert field(criterion, "failure_origin") == "environment"
    detail = field(criterion, "failure_detail")
    assert field(detail, "message") == "fake needs fakeprog >= 2"
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"


def test_unknown_kind_fails_environment(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, "nokind:data/table.txt", plant_fake=False)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        "comp-qux", repo_root, test_author=make_author(log_path)
    )

    criterion = only_criterion(report)
    detail = field(criterion, "failure_detail")
    assert field(detail, "message") == "unknown asset kind: nokind"
    assert field(criterion, "failure_origin") == "environment"