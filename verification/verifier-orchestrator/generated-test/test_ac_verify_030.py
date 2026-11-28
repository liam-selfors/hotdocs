# hotdocs-criterion: sha256:f1ea6fcf2f7c286f0e1a72a828c2ffc170e7da7bf524b64258591e5fe445f05b
"""AC-VERIFY-030: an unprovisioned run environment fails every generated-test
criterion with failure_origin "environment", without calling test_author."""

from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-qux"
SLUG = "qux"
CRITERION_ID = "AC-QUX-001"
REQUIREMENT_ID = "R-QUX-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fake_kind_source(provision_ok):
    if provision_ok:
        provision_result = {"ok": True, "reason": "", "versions": {"fake": "1.0"}, "lockfile_sha256": None}
    else:
        provision_result = {
            "ok": False,
            "reason": "fake needs fakeprog >= 2",
            "versions": {},
            "lockfile_sha256": None,
        }
    return (
        "import re\n"
        "from pathlib import Path\n"
        "\n"
        "KIND = " + repr("fake") + "\n"
        "\n"
        "def layout_errors(*args, **kwargs):\n"
        "    return []\n"
        "\n"
        "def surface(*args, **kwargs):\n"
        "    return {'names': []}\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "Fake generator text.", "test_author": "Fake test text."}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return dict(" + repr(provision_result) + ")\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    def run(entry, args):\n"
        "        for line in Path(asset_file).read_text().splitlines():\n"
        "            if line.startswith(entry + '='):\n"
        "                return int(line[len(entry) + 1:])\n"
        "        raise KeyError(entry)\n"
        "    return run\n"
        "\n"
        "def strength_sites(asset_file):\n"
        "    return [{'description': '1: a'}, {'description': '2: b'}]\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    path = Path(asset_file)\n"
        "    lines = path.read_text().splitlines()\n"
        "    index = int(site['description'].split(':')[0]) - 1\n"
        "    key, value = lines[index].split('=')\n"
        "    lines[index] = key + '=' + str(int(value) + 1)\n"
        "    path.write_text('\\n'.join(lines) + '\\n')\n"
    )


def assembler_source():
    bundle = {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": "Given a table When read Then a is 1",
        "requirement_text": "Qux MUST read its table.",
        "interface": "# Library\n\nread_table() -> dict\n",
        "glossary": "",
        "dependency_interfaces": {},
        "testing": "",
    }
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    bundle = dict(" + repr(bundle) + ")\n"
        "    bundle['component_id'] = component_id\n"
        "    bundle['criterion_id'] = criterion_id\n"
        "    return bundle\n"
    )


def probe_source():
    return (
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings)}\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    return _Report()\n"
    )


def build_fixture(repo_root, asset_decl, plant_fake_kind):
    comp_dir = repo_root / "specs" / "components" / SLUG
    write(
        comp_dir / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [qux-team]\n"
        "depends_on: []\n"
        "realizes: [P-QUX]\n"
        "assets: [" + asset_decl + "]\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Qux reads a small table.\n",
    )
    write(
        comp_dir / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n"
        "\n"
        "**" + REQUIREMENT_ID + "** — Qux MUST read its table.\n",
    )
    write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "read_table() -> dict\n"
        "```\n",
    )
    write(
        comp_dir / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the table data/table.txt\n"
        "When the entry a is read\n"
        "Then it is 1\n"
        "```\n",
    )
    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [qux-team]\n"
        "---\n"
        "\n"
        "# P-QUX\n"
        "\n"
        "Qux reads tables.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Table** — a file of lines.\n")

    write(repo_root / "gen" / SLUG / (SLUG + ".py"), "")
    write(repo_root / "gen" / SLUG / "data" / "table.txt", "a=1\nb=2\n")

    if plant_fake_kind:
        write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", "# Fake asset kind\n\nA fake kind.\n")
        write(repo_root / "gen" / "kind-fake" / "kind_fake.py", fake_kind_source(provision_ok=False))

    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", assembler_source())
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())


def make_test_author(log_path):
    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/qux/generated-test/test_ac_qux_001.py",
                "content": "def test_ok():\n    assert True\n",
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return author


def find_criterion(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return matches[0]


def test_unprovisioned_fake_kind_fails_criterion_without_authoring(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, "fake:data/table.txt", plant_fake_kind=True)
    log_path = tmp_path / "test_author.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_test_author(log_path)
    )

    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert calls == [], "test_author must never be called"

    criterion = find_criterion(report)
    assert field(criterion, "result") == "fail"
    assert field(criterion, "failure_origin") == "environment"
    assert field(field(criterion, "failure_detail"), "message") == "fake needs fakeprog >= 2"

    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"


def test_unknown_asset_kind_fails_criterion_as_environment(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, "nokind:data/table.txt", plant_fake_kind=False)
    log_path = tmp_path / "test_author.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_test_author(log_path)
    )

    criterion = find_criterion(report)
    assert field(field(criterion, "failure_detail"), "message") == "unknown asset kind: nokind"
    assert field(criterion, "failure_origin") == "environment"