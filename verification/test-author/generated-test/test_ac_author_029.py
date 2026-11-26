# hotdocs-criterion: sha256:f06fd9f5e8e678fb912d1b0a6a2ce0fe4836784cb44e42c7ed9fe1f0abb945df
import dataclasses
import json
from pathlib import Path

import pytest

import test_author


@dataclasses.dataclass
class FakeResult:
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
    "requirement_text": "R-FOO-001 MUST do z",
    "interface": "foo() -> int",
    "glossary": "",
    "dependency_interfaces": {},
    "testing": "",
}


def make_root(tmp_path, name):
    root = tmp_path / name
    base = root / "gen" / "spec-bundle-assembler"
    base.mkdir(parents=True)
    source = (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(" + repr(FIXED_BUNDLE) + ")\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    raise RuntimeError('not used')\n"
    )
    (base / "spec_bundle_assembler.py").write_text(source, encoding="utf-8")
    return root


def install_stub(monkeypatch, log_path, model_call_error):
    def stub(bundle, model, seed=0, *args, repo_root=None, llm_backend=None, **kwargs):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"seed": seed, "model": model}) + "\n")
        file = None
        if model_call_error is None:
            file = {"path": "p.py", "content": "x"}
        return FakeResult(
            component_id="comp-foo",
            criterion_id="AC-FOO-001",
            model=model,
            seed=seed,
            prompt_version="v1",
            cache_hit=False,
            file=file,
            model_call_error=model_call_error,
            repair_attempts=0,
            probe_findings=[],
        )

    monkeypatch.setattr(test_author, "author_test", stub)


def valid_argv(root):
    return ["comp-foo", "AC-FOO-001", "--model", "m", "--repo-root", str(root)]


def read_log(log_path):
    return [json.loads(line) for line in Path(log_path).read_text(encoding="utf-8").splitlines() if line.strip()]


def test_text_success(tmp_path, monkeypatch, capsys):
    root = make_root(tmp_path, "r_text")
    monkeypatch.chdir(root)
    log = tmp_path / "log_text.txt"
    install_stub(monkeypatch, log, None)
    code = test_author.main(valid_argv(root))
    out, err = capsys.readouterr()
    assert code == 0
    assert out == "AC-FOO-001: wrote p.py\n"
    calls = read_log(log)
    assert len(calls) == 1
    assert calls[0]["seed"] == 0


def test_json_success(tmp_path, monkeypatch, capsys):
    root = make_root(tmp_path, "r_json")
    monkeypatch.chdir(root)
    log = tmp_path / "log_json.txt"
    install_stub(monkeypatch, log, None)
    code = test_author.main(valid_argv(root) + ["--format=json"])
    out, err = capsys.readouterr()
    assert code == 0
    doc = json.loads(out)
    assert doc["criterion_id"] == "AC-FOO-001"


def test_model_call_error(tmp_path, monkeypatch, capsys):
    root = make_root(tmp_path, "r_err")
    monkeypatch.chdir(root)
    log = tmp_path / "log_err.txt"
    install_stub(monkeypatch, log, {"category": "network", "message": "down"})
    code = test_author.main(valid_argv(root))
    out, err = capsys.readouterr()
    assert code == 1
    assert out == "AC-FOO-001: model_call_error network: down\n"


@pytest.mark.parametrize(
    "case, cause",
    [
        ("only_component", "expected <component-id> and <criterion-id>"),
        ("format_xml", "--format must be json or text"),
        ("seed_x", "--seed must be an integer"),
        ("bogus", "unknown argument --bogus"),
        ("final_model", "--model requires a value"),
    ],
)
def test_usage_errors(tmp_path, monkeypatch, capsys, case, cause):
    root = make_root(tmp_path, "r_usage_" + case)
    monkeypatch.chdir(root)
    log = tmp_path / ("log_usage_" + case + ".txt")
    install_stub(monkeypatch, log, None)
    if case == "only_component":
        argv = ["comp-foo"]
    elif case == "format_xml":
        argv = valid_argv(root) + ["--format=xml"]
    elif case == "seed_x":
        argv = valid_argv(root) + ["--seed=x"]
    elif case == "bogus":
        argv = valid_argv(root) + ["--bogus"]
    else:
        argv = valid_argv(root) + ["--model"]
    code = test_author.main(argv)
    out, err = capsys.readouterr()
    assert code == 2
    assert out == ""
    assert err.startswith("usage error: " + cause)