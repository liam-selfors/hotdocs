# hotdocs-criterion: sha256:6e4479befd6ad396cf5817ebcafa11d789b4cb685c273508285840069ca10343
import json
import threading
import time
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FENCE = "`" * 3

MODULE_SOURCE = "\n".join([
    "def count_up(x):",
    "    i = 0",
    "    while i < x:",
    "        i = i + 1",
    "    return i",
    "",
])

GENERATED_TEST_SOURCE = "\n".join([
    "import loopy",
    "",
    "",
    "def test_count_up_reaches_x():",
    "    assert loopy.count_up(3) == 3",
    "",
])

CRITERION_TEXT = "\n".join([
    "# AC-LOOPY-001",
    "",
    "Covers: R-LOOPY-001",
    "Kind: generated-test",
    "",
    FENCE + "gherkin",
    "Given a number is 3",
    "When count_up is invoked with 3",
    "Then result equals 3",
    FENCE,
    "",
])

REQUIREMENT_TEXT = "\n".join([
    "# R-LOOPY-001",
    "",
    "**R-LOOPY-001** - `count_up(x)` MUST return `x` for a non-negative integer `x`.",
    "",
])

INTERFACE_TEXT = "\n".join([
    "# Library",
    "",
    FENCE,
    "count_up(x: int) -> int",
    FENCE,
    "",
])


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, log_path):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Thing** - a thing.\n")
    write(
        repo_root / "specs" / "product" / "loopy.md",
        "\n".join([
            "---",
            "id: P-LOOPY",
            "title: Loopy capability",
            "status: draft",
            "owners: [test-team]",
            "---",
            "",
            "# Loopy",
            "",
            "## Purpose",
            "",
            "Counts up.",
            "",
            "## Scope",
            "",
            "- Counting.",
            "",
        ]),
    )
    comp = repo_root / "specs" / "components" / "loopy"
    write(
        comp / "component.md",
        "\n".join([
            "---",
            "id: comp-loopy",
            "title: Loopy",
            "status: draft",
            "owners: [test-team]",
            "realizes: [P-LOOPY]",
            "---",
            "",
            "# Loopy",
            "",
            "## Purpose",
            "",
            "Counts up to a number with a loop.",
            "",
            "## Scope",
            "",
            "- In scope: counting.",
            "",
            "## Definitions",
            "",
            "None.",
            "",
            "## Behavior",
            "",
            "See `requirements/`.",
            "",
            "## Interfaces",
            "",
            "See `interface/`.",
            "",
            "## Data",
            "",
            "See `interface/data/`.",
            "",
            "## Acceptance criteria",
            "",
            "See `acceptance/`.",
            "",
            "## Non-functional constraints",
            "",
            "See `constraints.md`.",
            "",
            "## Open questions",
            "",
            "## Change log",
            "",
            "- Initial.",
            "",
        ]),
    )
    write(comp / "requirements" / "R-LOOPY-001.md", REQUIREMENT_TEXT)
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "acceptance" / "AC-LOOPY-001.md", CRITERION_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(repo_root / "gen" / "loopy" / "loopy.py", MODULE_SOURCE)

    bundle = {
        "component_id": "comp-loopy",
        "criterion_id": "AC-LOOPY-001",
        "covers": "R-LOOPY-001",
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE_TEXT,
        "glossary": "- **Thing** - a thing.",
        "dependency_interfaces": {},
        "testing": "",
    }
    assembler_source = (
        "import json\n"
        "\n"
        "_BUNDLE = json.loads(" + repr(json.dumps(bundle)) + ")\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(_BUNDLE)\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )

    probe_source = (
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
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
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return ProbeReport()\n"
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source)


def make_test_author(log_path):
    def test_author_stand_in(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("author\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/loopy/generated-test/test_ac_loopy_001.py",
                "content": GENERATED_TEST_SOURCE,
            },
        }

    return test_author_stand_in


def test_non_terminating_mutant_is_killed_within_ten_seconds(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    build_fixture(repo_root, log_path)

    outcome = {}

    def run_verify():
        try:
            outcome["report"] = verifier_orchestrator.verify(
                "comp-loopy", repo_root, test_author=make_test_author(log_path)
            )
        except BaseException as exc:  # surfaced below
            outcome["error"] = exc

    start = time.monotonic()
    worker = threading.Thread(target=run_verify, daemon=True)
    worker.start()
    worker.join(120)
    elapsed = time.monotonic() - start

    assert not worker.is_alive(), "verify did not return (non-terminating mutant not timed out)"
    if "error" in outcome:
        raise outcome["error"]
    assert elapsed < 10.0, "verify took " + repr(elapsed) + " seconds"

    report = outcome["report"]
    log_lines = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert "author" in log_lines

    criteria = field(report, "criteria")
    entry = next(c for c in criteria if field(c, "id") == "AC-LOOPY-001")
    assert field(entry, "result") == "pass"

    assert field(report, "mutation_error") is None
    # Both mutants (the comparison swap and the non-terminating `i - 1`) are killed.
    assert field(report, "mutation_score") == 1.0