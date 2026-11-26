# hotdocs-criterion: sha256:b0cfa167a732d04d67d42ab04a4455a07e80056caabf5b32e104f98d2b545ce0
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _gen_dir():
    return next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")


def _tool_root():
    return _gen_dir().parent


def _lint_clean(repo_root):
    gen = _gen_dir()
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0, [
        (f.rule_id, f.file, f.message) for f in report.findings if f.severity == "fail"
    ]


def component_files(slug, depends_on="[]", extra_frontmatter="", purpose="Foo doubles a number."):
    """The files of one fixture component, keyed by path under repo_root."""
    upper = slug.upper()
    base = f"specs/components/{slug}/"
    return {
        base + "component.md": (
            "---\n"
            f"id: comp-{slug}\n"
            f"title: {slug.capitalize()}\n"
            "status: draft\n"
            "owners: [team-a]\n"
            "sealed: true\n"
            f"source_path: legacy/{slug}/\n"
            f"depends_on: {depends_on}\n"
            + extra_frontmatter +
            "---\n"
            "\n"
            f"# {slug.capitalize()}\n"
            "\n"
            "## Purpose\n"
            "\n"
            f"{purpose}\n"
        ),
        base + f"requirements/R-{upper}-001.md": (
            f"# R-{upper}-001\n"
            "\n"
            f"**R-{upper}-001** — `foo(x)` MUST return `2 * x`.\n"
        ),
        base + f"acceptance/AC-{upper}-001.md": (
            f"# AC-{upper}-001\n"
            "\n"
            f"Covers: R-{upper}-001\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
            "```\n"
        ),
        base + "interface/library.md": "# Library\n\n```\nfoo(x: int) -> int\n```\n",
        base + "constraints.md": "# Constraints\n\nNone.\n",
    }


def write_fixture(repo_root, files):
    files = {"specs/glossary.md": "# Glossary\n\n- **Foo** — a test term.\n", **files}
    for rel, text in files.items():
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


APP_JS_MD = "# app.js\n\n```\nexport function double(x)\n```\n"


def _kind_component_files(kind):
    """The adapter component comp-kind-<kind>, built as foo with R-KJS-001/AC-KJS-001."""
    src = component_files("kjs")
    out = {}
    for rel, text in src.items():
        new_rel = rel.replace("specs/components/kjs/", "specs/components/kind-" + kind + "/")
        if rel.endswith("component.md"):
            text = (
                text.replace("id: comp-kjs\n", "id: comp-kind-" + kind + "\n")
                .replace("title: Kjs\n", "title: Kind " + kind + "\n")
                .replace("source_path: legacy/kjs/\n", "source_path: legacy/kind-" + kind + "/\n")
                .replace("# Kjs\n", "# Kind " + kind + "\n")
            )
        out[new_rel] = text
    return out


def _definition(kind):
    text = (
        "---\n"
        "id: kind-" + kind + "\n"
        "title: Asset kind " + kind + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Asset kind " + kind + "\n"
        "\n"
    )
    for name in ["Layout", "Environment", "Surface", "Running criteria",
                 "Strength check", "Test author guidance", "Generator guidance"]:
        text += "## " + name + "\n\n" + name + " text.\n\n"
    return text


def test_builtin_javascript_guidance_appended(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    files = component_files("foo", extra_frontmatter="assets: [javascript:static/app.js]\n")
    files["specs/components/foo/interface/assets/app.js.md"] = APP_JS_MD
    write_fixture(repo_root, files)
    assert not (repo_root / "gen" / "kind-javascript").exists()

    _lint_clean(repo_root)

    adapter_path = _tool_root() / "gen" / "kind-javascript" / "kind_javascript.py"
    assert adapter_path.is_file(), adapter_path
    adapter = load_module(adapter_path, "kind_javascript")
    guide = adapter.guidance()
    G = guide["generator"].strip()
    T = guide["test_author"].strip()

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    interface = field(bundle, "interface")
    assert interface.endswith("\n\n## Asset kind: javascript\n\n" + G), interface[-500:]

    cbundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    assert field(cbundle, "testing") == "\n## Asset kind: javascript\n\n" + T


def test_kind_without_adapter_raises(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    files = component_files(
        "foo",
        depends_on="[comp-kind-nokind]",
        extra_frontmatter="assets: [nokind:static/app.js]\n",
    )
    files["specs/components/foo/interface/assets/app.js.md"] = APP_JS_MD
    files["specs/architecture/asset-kind-nokind.md"] = _definition("nokind")
    files.update(_kind_component_files("nokind"))
    write_fixture(repo_root, files)

    assert not (repo_root / "gen" / "kind-nokind").exists()
    assert not (_tool_root() / "gen" / "kind-nokind").exists()

    _lint_clean(repo_root)

    with pytest.raises(Exception) as excinfo:
        spec_bundle_assembler.assemble("comp-foo", repo_root)
    exc = excinfo.value
    assert "PreconditionFailure" in [c.__name__ for c in type(exc).__mro__], type(exc)
    message = exc.args[0] if exc.args else str(exc)
    assert message == "unknown asset kind: nokind" or str(exc) == "unknown asset kind: nokind", (
        message, str(exc)
    )