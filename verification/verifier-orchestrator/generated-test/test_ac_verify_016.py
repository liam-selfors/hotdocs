# hotdocs-criterion: sha256:28a28a52450b45cf17b67d5fedb72a2d80312e367dff5c4ea1190482a116b5bd
import threading
import time
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
    "---\n"
    "id: comp-looper\n"
    "title: Looper\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "realizes: [P-LOOP]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Looper\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Looper counts up to a number.\n"
)

PRODUCT_MD = (
    "---\n"
    "id: P-LOOP\n"
    "title: Loop\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Loop\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Counting up.\n"
)

GLOSSARY_MD = "# Glossary\n\n- **Looper** — a test term.\n"

REQUIREMENT_TEXT = (
    "# R-LOOPER-001\n"
    "\n"
    "**R-LOOPER-001** — `count_up(x)` MUST return `x` for a non-negative `x`.\n"
)

CRITERION_TEXT = (
    "# AC-LOOPER-001\n"
    "\n"
    "Covers: R-LOOPER-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 3\n"
    "When count_up(x) is called\n"
    "Then it returns 3\n"
    "```\n"
)

LIBRARY_MD = "# Library\n\n```\ncount_up(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

LOOPER_SOURCE = (
    "def count_up(x):\n"
    "    i = 0\n"
    "    while i < x:\n"
    "        i = i + 1\n"
    "    return i\n"
)

GENERATED_TEST = (
    "import looper\n"
    "\n"
    "\n"
    "def test_count_up_reaches_three():\n"
    "    assert looper.count_up(3) == 3\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def assembler_source():
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-LOOPER-001',\n"
        "        'criterion_text': " + repr(CRITERION_TEXT) + ",\n"
        "        'requirement_text': " + repr(REQUIREMENT_TEXT) + ",\n"
        "        'interface': " + repr(LIBRARY_MD) + ",\n"
        "        'glossary': " + repr(GLOSSARY_MD) + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    write(repo_root / "specs" / "product" / "loop.md", PRODUCT_MD)
    comp = repo_root / "specs" / "components" / "looper"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-LOOPER-001.md", REQUIREMENT_TEXT)
    write(comp / "acceptance" / "AC-LOOPER-001.md", CRITERION_TEXT)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)
    write(repo_root / "gen" / "looper" / "looper.py", LOOPER_SOURCE)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )


def test_nonterminating_mutant_is_killed_within_ten_seconds(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author_calls.log"

    def fake_test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": "comp-looper",
            "criterion_id": "AC-LOOPER-001",
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/looper/generated-test/test_ac_looper_001.py",
                "content": GENERATED_TEST,
            },
            "model_call_error": None,
        }

    outcome = {}

    def run():
        try:
            outcome["report"] = verifier_orchestrator.verify(
                "comp-looper", repo_root, test_author=fake_test_author
            )
        except BaseException as exc:  # surfaced below
            outcome["error"] = exc

    start = time.monotonic()
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(15.0)
    elapsed = time.monotonic() - start

    assert not worker.is_alive(), "verify did not return (non-terminating mutant hung it)"
    if "error" in outcome:
        raise outcome["error"]
    assert elapsed < 10.0, "verify took " + repr(elapsed) + " seconds"

    report = outcome["report"]

    assert log_path.is_file() and log_path.read_text(encoding="utf-8").strip() != ""

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-LOOPER-001"]
    assert len(matching) == 1
    assert field(matching[0], "result") == "pass"

    assert field(report, "mutation_error") is None
    # Both mutants (`i < x` -> `i >= x`, and the non-terminating
    # `i + 1` -> `i - 1`) must be killed; the hanging one by its timeout.
    assert field(report, "mutation_score") == 1.0