# hotdocs-criterion: sha256:18df1bc195428c046d8385a19667759351a8294db66ae4cc3a4d20b4de555a95
import dataclasses
import json
from pathlib import Path

import pytest

import test_author


@dataclasses.dataclass
class FakeTestAuthoringResult:
    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: object
    model_call_error: object
    repair_attempts: int
    probe_findings: list


FIXED_BUNDLE = {
    "component_id": "comp-foo",
    "criterion_id": "AC-FOO-001",
    "covers": "R-FOO-001",
    "criterion_text": "Given x When y Then z",
    "requirement_text": "R-FOO-001 text",
    "interface": "",
    "glossary": "",
    "dependency_interfaces": {},
    "testing": "",
}


def make_root(tmp_path_factory, monkeypatch, name):
    root = tmp_path_factory.mktemp(name)
    base = root / "gen" / "spec-bundle-assembler"
    base.mkdir(parents=True)
    source = (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(" + repr(FIXED_BUNDLE) + ")\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    raise RuntimeError('not used')\n"
    )
    (base / "spec_bundle_assembler.py").write_text(source, encoding="utf-8")
    monkeypatch.chdir(root)
    return root


def install_stub(monkeypatch, model_call_error=None):
    calls = []

    def stub(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
        calls.append({"model": model, "seed": seed, "repo_root": repo_root})
        return FakeTestAuthoringResult(
            component_id="comp-foo",
            criterion_id="AC-FOO-001",
            model=model,
            seed=seed,
            prompt_version="v1",
            cache_hit=False,
            file={"path": "p.py", "content": "x"},
            model_call_error=model_call_error,
            repair_attempts=0,
            probe_findings=[],
        )

    monkeypatch.setattr(test_author, "author_test", stub)
    return calls


def valid_argv(root):
    return ["comp-foo", "AC-FOO-001", "--model", "m", "--repo-root", str(root)]


def test_text_success(tmp_path_factory, monkeypatch, capsys):
    root = make_root(tmp_path_factory, monkeypatch, "text")
    calls = install_stub(monkeypatch)
    code = test_author.main(valid_argv(root))
    out = capsys.readouterr().out
    assert code == 0
    assert out == "AC-FOO-001: wrote p.py\n"
    assert len(calls) == 1
    assert calls[0]["seed"] == 0


def test_json_success(tmp_path_factory, monkeypatch, capsys):
    root = make_root(tmp_path_factory, monkeypatch, "json")
    install_stub(monkeypatch)
    code = test_author.main(valid_argv(root) + ["--format=json"])
    out = capsys.readouterr().out
    assert code == 0
    doc = json.loads(out)
    assert doc["criterion_id"] == "AC-FOO-001"


def test_model_call_error(tmp_path_factory, monkeypatch, capsys):
    root = make_root(tmp_path_factory, monkeypatch, "err")
    install_stub(monkeypatch, {"category": "network", "message": "down"})
    code = test_author.main(valid_argv(root))
    out = capsys.readouterr().out
    assert code == 1
    assert out == "AC-FOO-001: model_call_error network: down\n"


@pytest.mark.parametrize(
    "case,cause",
    [
        ("positional", "expected <component-id> and <criterion-id>"),
        ("format", "--format must be json or text"),
        ("seed", "--seed must be an integer"),
        ("bogus", "unknown argument --bogus"),
        ("model_last", "--model requires a value"),
    ],
)
def test_usage_errors(tmp_path_factory, monkeypatch, capsys, case, cause):
    root = make_root(tmp_path_factory, monkeypatch, "usage_" + case)
    install_stub(monkeypatch)
    if case == "positional":
        argv = ["comp-foo"]
    elif case == "format":
        argv = valid_argv(root) + ["--format=xml"]
    elif case == "seed":
        argv = valid_argv(root) + ["--seed=x"]
    elif case == "bogus":
        argv = valid_argv(root) + ["--bogus"]
    else:
        argv = valid_argv(root) + ["--model"]
    code = test_author.main(argv)
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("usage error: " + cause)