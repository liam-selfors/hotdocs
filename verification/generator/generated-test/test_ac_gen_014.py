# hotdocs-criterion: sha256:f5e04eb5c26b9c20fabb6de5037beb8fb9910f1363156f8b634e12d5595f8950
import re
from pathlib import Path

import generator


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: false\n"
    "depends_on: [comp-bar]\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number using bar.\n"
)

BAR_COMPONENT_MD = (
    "---\n"
    "id: comp-bar\n"
    "title: Bar\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: false\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Bar\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Bar stores values.\n"
)

INTERFACE_TEXT = "# Library\n\nINTERFACE_MARKER_BAR bar_lookup(key: str) -> Entry"
USAGE_TEXT = (
    "module: bar\n"
    "\n"
    "def bar_get(key: str) -> dict\n"
    "    USAGE_MARKER_BAR Return the stored entry for key."
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next(
        (i for i in range(start, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return "\n".join(lines[start:end]).rstrip("\n")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    for slug, md in (("foo", COMPONENT_MD), ("bar", BAR_COMPONENT_MD)):
        base = repo_root / "specs" / "components" / slug
        upper = slug.upper()
        write(base / "component.md", md)
        write(
            base / "requirements" / ("R-" + upper + "-001.md"),
            "# R-" + upper + "-001\n\n**R-" + upper + "-001** — `" + slug
            + "(x)` MUST return `2 * x`.\n",
        )
        write(
            base / "acceptance" / ("AC-" + upper + "-001.md"),
            "# AC-" + upper + "-001\n\nCovers: R-" + upper + "-001\n"
            "Kind: generated-test\n\n```gherkin\nGiven x = 2\nWhen " + slug
            + "(x) is called\nThen it returns 4\n```\n",
        )
        write(base / "interface" / "library.md", "# Library\n\n```\n" + slug + "(x: int) -> int\n```\n")
        write(base / "constraints.md", "# Constraints\n\nNone.\n")


def test_dependency_usage_is_distinct_labeled_section(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path
    build_fixture(repo_root)

    bundle = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "# Foo\n\nFoo doubles a number using bar.\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\nfoo(x: int) -> int",
        "constraints": "# Constraints\n\nNone.",
        "dependency_interfaces": {"comp-bar": INTERFACE_TEXT},
        "dependency_context": {"comp-bar": "Bar stores values."},
        "dependency_usage": {"comp-bar": USAGE_TEXT},
        "vars": {},
        "glossary": "# Glossary\n\n- **Foo** — a test term.",
        "hint_code": None,
    }

    log_path = tmp_path / "mock_calls.log"
    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
        if m is None:
            m = re.search(r"\b([0-9a-f]{32})\b", prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert field(result, "refused") is None
    assert log_path.is_file()
    assert recorded, "mock model was never called"
    prompt = recorded[0]
    lines = prompt.split("\n")

    assert "## DEPENDENCY USAGE" in lines
    assert "## DEPENDENCY INTERFACES" in lines

    usage = section(prompt, "## DEPENDENCY USAGE")
    interfaces = section(prompt, "## DEPENDENCY INTERFACES")

    # dependency_usage content lives in its own section, labeled per dependency
    assert "### comp-bar" in usage.split("\n")
    assert "USAGE_MARKER_BAR" in usage
    assert "def bar_get(key: str) -> dict" in usage

    # never merged with dependency_interfaces
    assert "USAGE_MARKER_BAR" not in interfaces
    assert "bar_get" not in interfaces
    assert "INTERFACE_MARKER_BAR" in interfaces
    assert "INTERFACE_MARKER_BAR" not in usage

    # the two sections are separate headings at different positions
    assert lines.index("## DEPENDENCY USAGE") != lines.index("## DEPENDENCY INTERFACES")