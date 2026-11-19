# hotdocs-criterion: sha256:cb7f16467bb9804a167106355e6f3c7c0e5a8ddd09bffe92e75f13dd6eb5f715
import hashlib
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
CRITERION_TEXT = (
    "Given x = 2\n"
    "When double(x) is called\n"
    "Then it returns 4"
)
REQUIREMENT_TEXT = "**R-WIDGET-001** — `double(x)` MUST return `2 * x`."

PASSING_BODY = (
    "import widget\n"
    "\n"
    "\n"
    "def test_double_two():\n"
    "    assert widget.double(2) == 4\n"
)

FAILING_BODY = (
    "import widget\n"
    "\n"
    "\n"
    "def test_double_two():\n"
    "    assert widget.double(2) == 5\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def correct_header():
    digest = hashlib.sha256(
        (CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")
    ).hexdigest()
    return "# hotdocs-criterion: sha256:" + digest


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    repo_root.mkdir(parents=True, exist_ok=True)

    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )

    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubling numbers.\n",
    )

    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-WIDGET]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget doubles a number.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n" + REQUIREMENT_TEXT + "\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        + CRITERION_TEXT
        + "\n```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        repo_root / "gen" / SLUG / "widget.py",
        "def double(x):\n    return 2 * x\n",
    )

    assembler_source = (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-WIDGET-001',\n"
        "        'criterion_text': " + repr(CRITERION_TEXT) + ",\n"
        "        'requirement_text': " + repr(REQUIREMENT_TEXT) + ",\n"
        "        'interface': " + repr("# Library\n\n```\ndouble(x: int) -> int\n```") + ",\n"
        "        'glossary': " + repr("# Glossary\n\n- **Widget** — a test term.") + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )
    return repo_root


def cached_path(repo_root):
    return (
        repo_root
        / "verification"
        / SLUG
        / "generated-test"
        / "test_ac_widget_001.py"
    )


def make_stand_in(log_path):
    content = correct_header() + "\n" + PASSING_BODY

    def stand_in(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "stand-in-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": content,
            },
            "model_call_error": None,
        }

    return stand_in


def call_count(log_path):
    if not log_path.exists():
        return 0
    return len([ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()])


def criterion_entry(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return matches[0]


def test_zero_hash_header_is_stale_and_reauthored(tmp_path):
    repo_root = build_fixture(tmp_path / "repo")
    write(
        cached_path(repo_root),
        "# hotdocs-criterion: sha256:" + "0" * 64 + "\n"
        "def test_stale():\n    assert False\n",
    )
    log_path = tmp_path / "author_calls.log"
    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_stand_in(log_path)
    )
    assert call_count(log_path) == 1
    assert field(criterion_entry(report), "result") == "pass"


def test_missing_header_is_stale_and_reauthored(tmp_path):
    repo_root = build_fixture(tmp_path / "repo")
    write(
        cached_path(repo_root),
        "def test_stale():\n    assert False\n",
    )
    log_path = tmp_path / "author_calls.log"
    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_stand_in(log_path)
    )
    assert call_count(log_path) == 1
    assert field(criterion_entry(report), "result") == "pass"


def test_correct_header_cache_is_used_without_authoring(tmp_path):
    repo_root = build_fixture(tmp_path / "repo")
    write(cached_path(repo_root), correct_header() + "\n" + PASSING_BODY)
    log_path = tmp_path / "author_calls.log"
    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_stand_in(log_path)
    )
    assert call_count(log_path) == 0
    assert field(criterion_entry(report), "result") == "pass"


def test_correct_header_failing_cache_fails_with_implementation_origin(tmp_path):
    repo_root = build_fixture(tmp_path / "repo")
    write(cached_path(repo_root), correct_header() + "\n" + FAILING_BODY)
    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)
    entry = criterion_entry(report)
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "implementation"