import generator

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_root():
    gen = next(
        p for p in Path(generator.__file__).resolve().parents if p.name == "gen"
    )
    return gen.parent


def _load_from_tool_root(slug, module_name):
    base = _tool_root() / "gen" / slug
    flat = base / f"{module_name}.py"
    path = flat if flat.is_file() else base / module_name / "__init__.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

REQUIREMENT = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

ACCEPTANCE = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

LIBRARY = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS = "# Constraints\n\nNone.\n"


def _build_corpus(root: Path):
    _write(root / "specs" / "glossary.md", GLOSSARY)
    comp = root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)


def _cold_bundle(corpus_root: Path):
    spec_bundle_assembler = _load_from_tool_root(
        "spec-bundle-assembler", "spec_bundle_assembler"
    )
    spec_linter = _load_from_tool_root("spec-linter", "spec_linter")
    report = spec_linter.lint(None, corpus_root)
    hard = (
        report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    )
    assert hard == 0
    bundle = spec_bundle_assembler.assemble("comp-foo", corpus_root, mode="cold")
    assert field(bundle, "hint_code") is None
    return bundle


def _make_backend(log_path: Path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "Here is the candidate.\n"
            f"-----BEGIN FILE {nonce}: foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            f"-----END FILE {nonce}-----\n"
            f"-----END REPLY {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _read_log(log_path: Path):
    if not log_path.is_file():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    corpus = tmp_path / "corpus"
    _build_corpus(corpus)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.jsonl"
    return corpus, repo_root, log_path


def test_prompt_instructs_dependency_loads_resolve_from_repo_root(env):
    corpus, repo_root, log_path = env
    bundle = _cold_bundle(corpus)

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=_make_backend(log_path),
    )

    calls = _read_log(log_path)
    assert len(calls) >= 1, "mock model was never called"
    prompt = calls[0]["prompt"]
    lower = prompt.lower()

    # The bundle's own text contains none of these; they must come from
    # the prompt's instructions about dynamic dependency loading.
    assert "repo_root" in prompt
    assert "sys.modules" in prompt
    assert "__file__" in prompt
    assert "import" in lower
    assert "tool root" in lower
    assert "never" in lower or "must not" in lower

    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None


def test_generate_completes_with_no_gen_directory_in_repo_root(env):
    corpus, repo_root, log_path = env
    assert not (repo_root / "gen").exists()
    bundle = _cold_bundle(corpus)

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=_make_backend(log_path),
    )

    assert len(_read_log(log_path)) == 1
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False
    files = field(result, "files")
    assert files
    assert "foo.py" in files
    assert "return 2 * x" in files["foo.py"]
    assert field(result, "component_id") == "comp-foo"
    assert field(result, "spec_bundle_hash") == field(bundle, "spec_bundle_hash")
    assert (repo_root / "gen" / "foo" / "foo.py").is_file()