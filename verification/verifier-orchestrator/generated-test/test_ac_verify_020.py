# hotdocs-criterion: sha256:31024a6f3107c6e304ec59020429cc8f99e214c4ac45286d19ee5f303d0af8f2
import hashlib
import json
import shutil
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-mutfix"
SLUG = "mutfix"
MODULE = "mutfix"
CRITERION_ID = "AC-MUTFIX-001"
REQUIREMENT_ID = "R-MUTFIX-001"

BUNDLE_TEXTS = {
    "criterion_text": "Given a mutfix module\nWhen g is called with 1 and 2\nThen it returns True",
    "requirement_text": "R-MUTFIX-001 g(a, b) MUST return whether a is less than b.",
    "interface": "g(a, b) -> bool\nh(a, b) -> int\nm(k, d) -> bool\ndo_the_thing(x) -> object",
    "glossary": "Fixture glossary.",
    "testing": "",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def header_hex():
    keys = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    payload = json.dumps(
        {k: BUNDLE_TEXTS[k] for k in keys},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cached_test_source():
    return (
        "# hotdocs-criterion: sha256:" + header_hex() + "\n"
        "import mutfix\n"
        "\n"
        "\n"
        "def test_g_is_less_than():\n"
        "    assert mutfix.g(1, 2) is True\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, log_path):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Mutation fixture\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
        "realizes: [P-MUTFIX]\n"
        "---\n"
        "\n"
        "# Mutation fixture\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component for mutation scoring.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: g, h, m, do_the_thing.\n"
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
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "**" + REQUIREMENT_ID + "** g(a, b) MUST return whether a is less than b.\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a mutfix module\n"
        "When g is called with 1 and 2\n"
        "Then it returns True\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "g(a, b) -> bool\n"
        "h(a, b) -> int\n"
        "m(k, d) -> bool\n"
        "do_the_thing(x) -> object\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "P-MUTFIX.md",
        "---\n"
        "id: P-MUTFIX\n"
        "title: Mutation fixture capability\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
        "---\n"
        "\n"
        "# Mutation fixture capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Fixture.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Fixture** - a fixture.\n")

    # The component's only module: three mutation sites, one per function g, h, m.
    write(
        repo_root / "gen" / SLUG / (MODULE + ".py"),
        "def g(a, b):\n"
        "    return a < b\n"
        "\n"
        "\n"
        "def h(a, b):\n"
        "    return a // b\n"
        "\n"
        "\n"
        "def m(k, d):\n"
        "    return k in d\n"
        "\n"
        "\n"
        "def do_the_thing(x):\n"
        "    return x\n",
    )

    # spec-bundle-assembler stand-in.
    bundle = dict(BUNDLE_TEXTS)
    bundle["component_id"] = COMPONENT_ID
    bundle["criterion_id"] = CRITERION_ID
    bundle["covers"] = REQUIREMENT_ID
    bundle["dependency_interfaces"] = {}
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(bundle) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )

    # test-probe stand-in: always ok, no findings.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "from dataclasses import dataclass, field\n"
        "\n"
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class ProbeReport:\n"
        "    ok: bool = True\n"
        "    findings: list = field(default_factory=list)\n"
        "    tests_run: int = 0\n"
        "    tests_reached: int = 0\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return ProbeReport(ok=True, findings=[], tests_run=1, tests_reached=1)\n",
    )

    # Real criterion-compiler copied in, never relying on the tool-root fallback.
    live = (
        Path(verifier_orchestrator.__file__).resolve().parents[1] / "spec-bundle-assembler"
    ).resolve().parents[1]
    src = live / "pipeline" / "criterion-compiler"
    if src.is_dir():
        shutil.copytree(
            src,
            repo_root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    # The cached, current generated test: kills only the mutant of "a < b".
    cached = repo_root / "verification" / SLUG / "generated-test" / "test_ac_mutfix_001.py"
    write(cached, cached_test_source())
    return cached


def make_test_author(log_path):
    content = cached_test_source()

    def test_author_standin(bundle):
        with open(log_path, "a") as fh:
            fh.write("test_author\n")
        return {
            "model": "fixture-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/mutfix/generated-test/test_ac_mutfix_001.py",
                "content": content,
            },
        }

    return test_author_standin


def test_mutation_score_is_one_third(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    build_fixture(repo_root, log_path)

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=None, test_author=make_test_author(log_path)
    )

    criteria = field(report, "criteria")
    entry = next(c for c in criteria if field(c, "id") == CRITERION_ID)
    assert field(entry, "result") == "pass", entry

    assert field(report, "mutation_error") is None
    score = field(report, "mutation_score")
    assert score is not None
    # Three sites (a < b, a // b, k in d), one killed.
    assert abs(score - 1 / 3) < 1e-9, score
    # Below the 0.8 bar, so the overall verdict fails.
    assert field(report, "overall") == "fail"