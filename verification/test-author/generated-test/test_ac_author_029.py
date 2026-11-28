# hotdocs-criterion: sha256:2df1f9bd0743621e2b632fd2360e9ced809452da7996c5f4d3b7d500685a912f
import dataclasses
import json

import pytest

import test_author


@dataclasses.dataclass
class StubResult:
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


def make_root(tmp_path, name, monkeypatch):
    root = tmp_path / name
    base = root / "gen" / "spec-bundle-assembler"
    base.mkdir(parents=True)
    source = (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(" + repr(FIXED_BUNDLE) + ")\n"
    )
    (base / "spec_bundle_assembler.py").write_text(source, encoding="utf-8")
    monkeypatch.chdir(root)
    return root


def install_stub(monkeypatch, model_call_error=None):
    calls = []

    def stub(bundle, model, seed=0, *args, repo_root=None, llm_backend=None, **kwargs):
        calls.append({"bundle": bundle, "model": model, "seed": seed, "repo_root": repo_root})
        return StubResult(
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


def test_text_success(tmp_path, monkeypatch, capsys):
    root = make_root(tmp_path, "text_ok", monkeypatch)
    calls = install_stub(monkeypatch)
    capsys.readouterr()
    code = test_author.main(valid_argv(root))
    out = capsys.readouterr().out
    assert code == 0
    assert out == "AC-FOO-001: wrote p.py\n"
    assert len(calls) == 1
    assert calls[0]["seed"] == 0
    assert isinstance(calls[0]["seed"], int)


def test_json_success(tmp_path, monkeypatch, capsys):
    root = make_root(tmp_path, "json_ok", monkeypatch)
    install_stub(monkeypatch)
    capsys.readouterr()
    code = test_author.main(valid_argv(root) + ["--format=json"])
    out = capsys.readouterr().out
    assert code == 0
    doc = json.loads(out)
    assert doc["criterion_id"] == "AC-FOO-001"


def test_model_call_error(tmp_path, monkeypatch, capsys):
    root = make_root(tmp_path, "err", monkeypatch)
    install_stub(monkeypatch, model_call_error={"category": "network", "message": "down"})
    capsys.readouterr()
    code = test_author.main(valid_argv(root))
    out = capsys.readouterr().out
    assert code == 1
    assert out == "AC-FOO-001: model_call_error network: down\n"


@pytest.mark.parametrize(
    "case, extra, cause",
    [
        ("positional", None, "expected <component-id> and <criterion-id>"),
        ("format", ["--format=xml"], "--format must be json or text"),
        ("seed", ["--seed=x"], "--seed must be an integer"),
        ("bogus", ["--bogus"], "unknown argument --bogus"),
        ("final_model", ["--model"], "--model requires a value"),
    ],
)
def test_usage_errors(tmp_path, monkeypatch, capsys, case, extra, cause):
    root = make_root(tmp_path, "usage_" + case, monkeypatch)
    install_stub(monkeypatch)
    if extra is None:
        argv = ["comp-foo"]
    else:
        argv = valid_argv(root) + extra
    capsys.readouterr()
    code = test_author.main(argv)
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("usage error: " + cause)