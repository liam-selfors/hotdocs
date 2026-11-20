# hotdocs-criterion: sha256:87a8a74400115dfadf570aa923f65992a8e96b84ad19eeb9634d84c39ca2f032
import importlib.util
import sys
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _load_linter():
    gen = next(
        (p for p in Path(spec_linter.__file__).resolve().parents if p.name == "gen"),
        None,
    )
    if gen is None:
        return spec_linter
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    if not path.is_file():
        return spec_linter
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    return module


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _var_doc(var_id, bullets):
    return (
        "---\n"
        + "id: " + var_id + "\n"
        + "title: Secret token " + var_id + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# " + var_id + "\n"
        + "\n"
        + bullets
    )


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Token** — a credential used for testing.\n",
    )

    var_files = {
        "specs/vars/VAR-ALPHA-TOKEN.md": _var_doc(
            "VAR-ALPHA-TOKEN",
            "- name: VAR-ALPHA-TOKEN\n"
            "- required\n"
            "- type: secret-ref\n"
            "- description: A token used to authenticate to the alpha service.\n"
            "- sensitivity: secret\n"
            "- default: hunter2\n",
        ),
        "specs/vars/VAR-BETA-TOKEN.md": _var_doc(
            "VAR-BETA-TOKEN",
            "- **name**: `VAR-BETA-TOKEN`\n"
            "- **required**\n"
            "- **type**: `secret-ref`\n"
            "- **description**: A token used to authenticate to the beta service.\n"
            "- **sensitivity**: `secret`\n"
            "- **default**: `hunter2`\n",
        ),
        "specs/vars/VAR-GAMMA-TOKEN.md": _var_doc(
            "VAR-GAMMA-TOKEN",
            "- `name`: `VAR-GAMMA-TOKEN`\n"
            "- `required`\n"
            "- `type`: `secret-ref`\n"
            "- `description`: A token used to authenticate to the gamma service.\n"
            "- `sensitivity`: `secret`\n"
            "- `default`: `hunter2`\n",
        ),
    }
    for rel, text in var_files.items():
        _write(repo_root / rel, text)
    return set(var_files)


def test_ac_lint_013_secret_var_with_default_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    var_rel_paths = _build_fixture(repo_root)

    linter = _load_linter()
    report = linter.lint(None, repo_root)

    findings = list(field(report, "findings"))
    matching = []
    for finding in findings:
        if field(finding, "rule_id") != "R-LINT-013":
            continue
        if field(finding, "severity") != "fail":
            continue
        file_value = str(field(finding, "file")).replace("\\", "/")
        if any(file_value.endswith(rel) for rel in var_rel_paths):
            matching.append(finding)

    summary = [
        (field(f, "rule_id"), field(f, "severity"), field(f, "file"), field(f, "message"))
        for f in findings
    ]
    assert matching, (
        "expected a fail-severity R-LINT-013 finding for a secret var "
        "declaration carrying a default field; got: " + repr(summary)
    )
    assert field(report, "hard_failures") >= 1