# hotdocs-criterion: sha256:299e5ce5aaf366b4fde5f4a9b8fd059fb9b5826647d34a63b64336a1b828c791
import importlib.util
import re
import sys
from pathlib import Path

import test_author


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _MappingBundle(dict):
    """Fallback bundle that reads both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


CRITERION_TEXT = (
    "Given x = 2 ZQXCRITERIONMARKER\n"
    "When foo(x) is called\n"
    "Then it returns 4"
)
REQUIREMENT_TEXT = (
    "# R-FOO-001\n\n"
    "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`. ZQXREQUIREMENTMARKER"
)
INTERFACE_TEXT = (
    "# Library\n\n"
    "```\n"
    "foo(x: int) -> int  # ZQXINTERFACEMARKER\n"
    "```"
)
GLOSSARY_TEXT = (
    "# Glossary\n\n"
    "- **Foo** \u2014 a test term. ZQXGLOSSARYMARKER"
)


def _bundle_fields():
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
    }


def _make_bundle():
    fields = _bundle_fields()
    try:
        gen = next(
            p for p in Path(test_author.__file__).resolve().parents if p.name == "gen"
        )
        base = gen / "spec-bundle-assembler"
        flat = base / "spec_bundle_assembler.py"
        path = flat if flat.is_file() else base / "spec_bundle_assembler" / "__init__.py"
        if path.is_file():
            sba = load_module(path, "spec_bundle_assembler")
            cls = getattr(sba, "CriterionBundle", None)
            if cls is not None:
                try:
                    return cls(module_names=["foo"], **fields)
                except TypeError:
                    return cls(**fields)
    except StopIteration:
        pass
    except Exception:
        pass
    fields["module_names"] = ["foo"]
    return _MappingBundle(fields)


def test_author_test_sends_criterion_requirement_interface_and_glossary(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "prompts"
    log_dir.mkdir()

    reply_body = "import foo\n\n\ndef test_placeholder():\n    assert True\n"

    def mock_backend(prompt, model, **params):
        index = len(list(log_dir.iterdir()))
        (log_dir / ("prompt_" + str(index).zfill(4) + ".txt")).write_text(
            prompt, encoding="utf-8"
        )
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = nonces[-1] if nonces else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + reply_body
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = _make_bundle()
    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )
    assert result is not None

    prompt_files = sorted(log_dir.iterdir())
    assert prompt_files, "the mock model was never called"
    first_prompt = prompt_files[0].read_text(encoding="utf-8")

    assert CRITERION_TEXT in first_prompt
    assert REQUIREMENT_TEXT in first_prompt
    assert INTERFACE_TEXT in first_prompt
    assert GLOSSARY_TEXT in first_prompt